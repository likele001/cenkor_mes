# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储配置服务 单元测试：密文入库 / 脱敏读取 / 激活校验。"""
import pytest
from sqlalchemy import select

from app.models.cloud_storage import CloudStorageConfig
from app.services import cloud_storage_config as svc


CREDS = {
    "endpoint": "oss-cn-hangzhou.aliyuncs.com",
    "region": "cn-hangzhou",
    "bucket": "my-bucket",
    "access_key": "AKID1234567890abcd",
    "secret_key": "SUPERSECRETVALUE123",
}


def test_get_or_create_singleton(session):
    cfg = svc.get_or_create(session)
    assert cfg.active_provider == "local"
    # 再次获取不新建
    cfg2 = svc.get_or_create(session)
    assert cfg2.id == cfg.id
    assert len(session.scalars(select(CloudStorageConfig)).all()) == 1


def test_credentials_stored_encrypted(session):
    svc.set_credentials(session, "aliyun", CREDS)
    cfg = svc.get_or_create(session)
    raw = cfg.creds_aliyun
    assert raw and "SUPERSECRETVALUE123" not in raw
    assert "AKID1234567890abcd" not in raw  # 入库为密文
    # 解密可还原
    assert svc.get_credentials(session, "aliyun") == CREDS


def test_masked_view_hides_secrets(session):
    svc.set_credentials(session, "aliyun", CREDS)
    view = svc.get_masked_view(session)
    aliyun = view["providers"]["aliyun"]
    assert aliyun["configured"] is True
    assert aliyun["credentials"]["secret_key"] == "•" * 8
    assert aliyun["credentials"]["access_key"] == "AKI••••abcd"
    # 非敏感字段照常返回，便于回填表单
    assert aliyun["credentials"]["bucket"] == "my-bucket"
    assert aliyun["credentials"]["endpoint"] == "oss-cn-hangzhou.aliyuncs.com"
    # 明文绝不出现在视图里
    assert "SUPERSECRETVALUE123" not in repr(view)


def test_activate_requires_credentials(session):
    with pytest.raises(ValueError):
        svc.activate(session, "aliyun")  # 未配置凭据
    svc.set_credentials(session, "aliyun", CREDS)
    cfg = svc.activate(session, "aliyun")
    assert cfg.active_provider == "aliyun"


def test_activate_local_always_ok(session):
    assert svc.activate(session, "local").active_provider == "local"


def test_unknown_provider_rejected(session):
    with pytest.raises(ValueError):
        svc.set_credentials(session, "wut", {})
    with pytest.raises(ValueError):
        svc.activate(session, "wut")


def test_keep_local_backup_toggle(session):
    assert svc.set_keep_local_backup(session, True).keep_local_backup is True
    assert svc.set_keep_local_backup(session, False).keep_local_backup is False
