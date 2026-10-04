# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""历史附件迁移(CS-6) 测试。

策略：
- create_migration_job / _migrate_one 均接受显式 db 与 storage 参数，直接注入测试替身；
- run_migration 内部使用 SessionLocal()，测试必须 monkeypatch 成测试会话，
  绝不能连真实数据库；build_storage 同样 monkeypatch，用内存 FakeStorage 扮演目标云。
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from app.api.admin.system import cloud_storage as api
from app.models.attachment import Attachment
from app.models.cloud_storage import CloudStorageMigrationJob
from app.schemas.cloud_storage import MigrationIn
from app.services import cloud_storage_config as cfg_svc
from app.services import cloud_storage_migration as mig
from app.storage.base import StoredObject
from app.storage.local import LocalStorage

CREDS = {
    "endpoint": "oss-cn-hangzhou.aliyuncs.com",
    "region": "cn-hangzhou",
    "bucket": "my-bucket",
    "access_key": "AKID1234567890abcd",
    "secret_key": "SUPERSECRETVALUE123",
}


def _fake_request():
    return SimpleNamespace(
        client=None,
        headers={},
        method="POST",
        url=SimpleNamespace(path="/admin/system/cloud-storage/migration"),
    )


@pytest.fixture(autouse=True)
def _noop_op_log(monkeypatch):
    """屏蔽操作日志写入：operation_logs.id 在 SQLite 测试库下非自增，与迁移业务无关。"""
    monkeypatch.setattr(api, "write_op_log", lambda *a, **k: None)


class FakeCloud:
    """内存版云驱动替身：save 存入 dict，delete 移除；driver 固定为目标名。"""

    def __init__(self, driver: str = "aliyun"):
        self.driver = driver
        self.blobs: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def save(self, *, filename: str, content_type: str, stream, max_size: int) -> StoredObject:
        data = stream.read(max_size + 1)
        key = f"{self.driver}/{filename}"
        self.blobs[key] = data
        return StoredObject(
            driver=self.driver, key=key, size=len(data), sha256=hashlib.sha256(data).hexdigest()
        )

    def delete(self, *, key: str) -> None:
        self.blobs.pop(key, None)
        self.deleted.append(key)

    def resolve_path(self, *, key: str):
        raise NotImplementedError

    def signed_url(self, *, key: str, content_type: str, expires: int = 3600, filename: str | None = None) -> str:
        return f"https://fake/{key}"


def _make_local_attachment(session, test_user, tmp_path, *, content: bytes = b"hello-world"):
    """在 tmp 源目录落一个真实文件并建对应的 local 附件记录。"""
    src = LocalStorage(root=tmp_path / "src")
    key = "2026/01/01/abc123.txt"
    fp = src.root / key
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(content)
    att = Attachment(
        uploader_id=test_user.id,
        storage_driver="local",
        storage_key=key,
        original_filename="abc123.txt",
        content_type="text/plain",
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
    session.add(att)
    session.commit()
    return att, src, content


# ── create_migration_job 校验 ──

def test_create_rejects_non_local_source(session, test_user):
    with pytest.raises(mig.MigrationError):
        mig.create_migration_job(session, target="aliyun", source="tencent")


def test_create_rejects_local_as_target(session, test_user):
    # local 不在 CLOUD_PROVIDERS
    with pytest.raises(mig.MigrationError):
        mig.create_migration_job(session, target="local", source="local")


def test_create_rejects_unconfigured_target(session, test_user):
    # 合法云 provider 但未配置凭据
    with pytest.raises(mig.MigrationError):
        mig.create_migration_job(session, target="tencent", source="local")


def test_create_ok_when_configured(session, test_user):
    cfg_svc.update_credentials(session, "aliyun", CREDS, user_id=test_user.id)
    session.commit()
    job = mig.create_migration_job(session, target="aliyun", source="local")
    assert job.status == "pending"
    assert job.target == "aliyun"
    assert job.source == "local"


def test_create_rejects_when_running(session, test_user):
    cfg_svc.update_credentials(session, "aliyun", CREDS, user_id=test_user.id)
    running = CloudStorageMigrationJob(source="local", target="aliyun", status="running", total=0)
    session.add(running)
    session.commit()
    with pytest.raises(mig.MigrationError):
        mig.create_migration_job(session, target="aliyun", source="local")


# ── _migrate_one 单元 ──

def test_migrate_one_success(session, test_user, tmp_path):
    att, src, content = _make_local_attachment(session, test_user, tmp_path)
    cloud = FakeCloud(driver="aliyun")
    ok, err = mig._migrate_one(session, att, cloud, src)
    assert ok is True and err is None
    assert att.storage_driver == "aliyun"
    assert att.storage_key in cloud.blobs
    assert cloud.blobs[att.storage_key] == content


def test_migrate_one_missing_source(session, test_user, tmp_path):
    _att, src, _c = _make_local_attachment(session, test_user, tmp_path)
    # 造一条源文件不存在的附件
    att = Attachment(
        uploader_id=_att.uploader_id, storage_driver="local", storage_key="no/such.txt",
        original_filename="no.txt", content_type="text/plain", size=1,
        sha256=hashlib.sha256(b"x").hexdigest(),
    )
    session.add(att)
    session.commit()
    cloud = FakeCloud()
    ok, err = mig._migrate_one(session, att, cloud, src)
    assert ok is False
    assert "不存在" in err


def test_migrate_one_sha_mismatch_rolls_back(session, test_user, tmp_path):
    att, src, _content = _make_local_attachment(session, test_user, tmp_path)
    att.sha256 = "0" * 64  # 篡改记录 sha，制造与上传内容不符
    session.commit()
    cloud = FakeCloud()
    ok, err = mig._migrate_one(session, att, cloud, src)
    assert ok is False
    assert "sha256" in err
    # 已上传对象应被回删，记录指向不变
    assert cloud.deleted and not cloud.blobs
    assert att.storage_driver == "local"


# ── run_migration 端到端 ──

def test_run_migration_end_to_end(session, test_user, tmp_path, monkeypatch):
    att, src, _content = _make_local_attachment(session, test_user, tmp_path)
    cfg_svc.update_credentials(session, "aliyun", CREDS, user_id=test_user.id)
    session.commit()
    job = mig.create_migration_job(session, target="aliyun", source="local")

    cloud = FakeCloud(driver="aliyun")
    # 让内部会话指向测试 session，build_storage 返回替身/local
    monkeypatch.setattr(mig, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        mig,
        "build_storage",
        lambda driver=None, cfg=None, db=None: cloud if driver == "aliyun" else src,
    )

    job_id, att_id = job.id, att.id  # 先取 id：run_migration 会 close 会话使实例脱附
    mig.run_migration(job_id)
    # run_migration 内部会 close 会话（脱附实例），按 id 重新取回最新状态
    job_fresh = session.get(CloudStorageMigrationJob, job_id)
    att_fresh = session.get(Attachment, att_id)
    assert job_fresh.status == "done"
    assert job_fresh.done == 1 and job_fresh.failed == 0
    assert att_fresh.storage_driver == "aliyun"
    assert att_fresh.storage_key in cloud.blobs


def test_run_migration_marks_failed_on_degrade(session, test_user, tmp_path, monkeypatch):
    att, src, _content = _make_local_attachment(session, test_user, tmp_path)
    cfg_svc.update_credentials(session, "aliyun", CREDS, user_id=test_user.id)
    session.commit()
    job = mig.create_migration_job(session, target="aliyun", source="local")

    # 目标驱动降级为 local（driver 名 != 目标）：任务应判失败，附件不动
    monkeypatch.setattr(mig, "SessionLocal", lambda: session)
    monkeypatch.setattr(mig, "build_storage", lambda driver=None, cfg=None, db=None: src)

    job_id, att_id = job.id, att.id
    mig.run_migration(job_id)
    job_fresh = session.get(CloudStorageMigrationJob, job_id)
    att_fresh = session.get(Attachment, att_id)
    assert job_fresh.status == "failed"
    assert att_fresh.storage_driver == "local"


# ── API 端点 ──

def test_api_migration_latest_none(session, test_user):
    res = api.get_latest_migration(db=session, user=test_user)
    assert res["data"] is None


def test_api_start_migration_validation(session, test_user):
    from app.core.errors import BizError

    # 未配置凭据的目标 → 400
    with pytest.raises(BizError) as exc:
        api.start_migration(
            MigrationIn(target="tencent", source="local"), _fake_request(), db=session, user=test_user
        )
    assert exc.value.code == 400
