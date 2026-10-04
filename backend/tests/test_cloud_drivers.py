# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云驱动 单元测试：以 mock 替换真实 SDK，验证协议实现与工厂按凭据构造/降级。"""
import io

import pytest

from app.storage.factory import build_storage, get_active_storage
from app.storage.local import LocalStorage

OSS_CREDS = {"endpoint": "oss-cn-hangzhou.aliyuncs.com", "bucket": "b", "access_key": "ak", "secret_key": "sk"}
COS_CREDS = {"region": "ap-guangzhou", "bucket": "b", "access_key": "ak", "secret_key": "sk"}


# ── 阿里 OSS ──

def test_aliyun_save_delete_sign(monkeypatch):
    pytest.importorskip("oss2")
    from app.storage.drivers.aliyun import AliyunOSSStorage

    calls = {}

    class FakeBucket:
        def put_object(self, key, data, headers=None):
            calls["put"] = (key, data, headers)

        def delete_object(self, key):
            calls["del"] = key

        def sign_url(self, method, key, expires, params=None):
            calls["sign"] = (method, key, expires, params)
            return f"https://oss.example/{key}?e={expires}"

    monkeypatch.setattr(AliyunOSSStorage, "_bucket", lambda self: FakeBucket())
    st = AliyunOSSStorage(OSS_CREDS)
    obj = st.save(filename="a.txt", content_type="text/plain", stream=io.BytesIO(b"hello"), max_size=1024)

    assert obj.driver == "aliyun" and obj.size == 5 and obj.abs_path is None
    assert obj.key.endswith(".txt") and calls["put"][1] == b"hello"
    assert calls["put"][2] == {"Content-Type": "text/plain"}

    url = st.signed_url(key=obj.key, content_type="text/plain", expires=60, filename="a.txt")
    assert url.startswith("https://oss.example/")
    assert calls["sign"][3]["response-content-disposition"].startswith("inline;")

    st.delete(key=obj.key)
    assert calls["del"] == obj.key


def test_aliyun_missing_creds_raises():
    pytest.importorskip("oss2")
    from app.storage.drivers.aliyun import AliyunOSSStorage
    with pytest.raises(ValueError):
        AliyunOSSStorage({"bucket": "b"})  # 缺 endpoint/keys


# ── 腾讯 COS ──

def test_tencent_save(monkeypatch):
    pytest.importorskip("qcloud_cos")
    from app.storage.drivers.tencent import TencentCOSStorage

    calls = {}

    class FakeClient:
        def put_object(self, **kw):
            calls["put"] = kw

        def delete_object(self, **kw):
            calls["del"] = kw

        def get_presigned_url(self, method, **kw):
            return "https://cos.example/signed"

    monkeypatch.setattr(TencentCOSStorage, "_client", lambda self: FakeClient())
    st = TencentCOSStorage(COS_CREDS)
    obj = st.save(filename="x.png", content_type="image/png", stream=io.BytesIO(b"12345"), max_size=1024)
    assert obj.driver == "tencent" and calls["put"]["Bucket"] == "b" and calls["put"]["ContentType"] == "image/png"
    assert st.signed_url(key=obj.key, content_type="image/png") == "https://cos.example/signed"


# ── 七牛 ──

def test_qiniu_requires_domain():
    pytest.importorskip("qiniu")
    from app.storage.drivers.qiniu import QiniuStorage
    with pytest.raises(ValueError):
        QiniuStorage({"bucket": "b", "access_key": "ak", "secret_key": "sk"})  # 缺 custom_domain


def test_qiniu_upload_uses_put_data(monkeypatch):
    pytest.importorskip("qiniu")
    import app.storage.drivers.qiniu as qn

    seen = {}

    class FakeAuth:
        def upload_token(self, bucket, key):
            return "TOKEN"

        def private_download_url(self, base_url, expires=3600):
            return f"{base_url}?sign=x&e={expires}"

    def fake_put_data(token, key, data, mime_type=None):
        seen.update(token=token, key=key, data=data, mime=mime_type)
        return {}, None

    monkeypatch.setattr(qn.QiniuStorage, "_auth", lambda self: FakeAuth())
    monkeypatch.setattr(qn, "put_data", fake_put_data)
    st = qn.QiniuStorage({"bucket": "b", "access_key": "ak", "secret_key": "sk", "custom_domain": "cdn.x.com"})
    obj = st.save(filename="a.txt", content_type="text/plain", stream=io.BytesIO(b"hi"), max_size=1024)
    assert seen["token"] == "TOKEN" and seen["data"] == b"hi"
    assert st.signed_url(key=obj.key, content_type="text/plain", expires=30).endswith(f"e=30")


# ── 基类 ──

def test_cloud_resolve_path_not_implemented():
    pytest.importorskip("oss2")
    from app.storage.drivers.aliyun import AliyunOSSStorage
    st = AliyunOSSStorage(OSS_CREDS)
    with pytest.raises(NotImplementedError):
        st.resolve_path(key="k")


# ── 工厂集成 ──

def test_factory_builds_aliyun_with_creds(session):
    pytest.importorskip("oss2")
    from app.services import cloud_storage_config as svc
    from app.storage.drivers.aliyun import AliyunOSSStorage

    svc.set_credentials(session, "aliyun", OSS_CREDS)
    st = build_storage("aliyun", db=session)
    assert isinstance(st, AliyunOSSStorage)


def test_factory_falls_back_local_without_creds(session):
    # 未配置凭据 → 构造校验失败 → 降级 local（不抛异常）
    assert isinstance(build_storage("aliyun", db=session), LocalStorage)


def test_get_active_storage_uses_activated_provider(session):
    pytest.importorskip("oss2")
    from app.services import cloud_storage_config as svc
    from app.storage.drivers.aliyun import AliyunOSSStorage

    assert isinstance(get_active_storage(session), LocalStorage)  # 默认 local
    svc.set_credentials(session, "aliyun", OSS_CREDS)
    svc.activate(session, "aliyun")
    assert isinstance(get_active_storage(session), AliyunOSSStorage)
