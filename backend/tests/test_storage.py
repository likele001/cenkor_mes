"""存储驱动与附件 URL 单元测试"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest

from app.crud.attachment import create_attachment
from app.services.attachment_media import attachment_play_url
from app.storage.factory import build_storage, get_storage_for, load_storage_config
from app.storage.local import LocalStorage


@pytest.fixture
def local_root(tmp_path: Path) -> Path:
    root = tmp_path / "storage"
    root.mkdir()
    return root


def test_local_storage_save_delete(local_root: Path):
    storage = LocalStorage(str(local_root))
    data = b"hello cenkormes"
    bio = BytesIO(data)
    stored = storage.save(
        tenant_id=1,
        filename="test.txt",
        content_type="text/plain",
        stream=bio,
        max_size=1024,
    )
    assert stored.driver == "local"
    assert stored.key.startswith("1/")
    assert stored.size == len(data)
    assert stored.sha256 == hashlib.sha256(data).hexdigest()
    path = storage.resolve_path(key=stored.key)
    assert path.exists()
    storage.delete(key=stored.key)
    assert not path.exists()


def test_load_storage_config_defaults_without_db():
    cfg = load_storage_config(None)
    assert cfg.driver == "local"


def test_get_storage_for_attachment_driver(session, tenant, test_user, local_root: Path, monkeypatch):
    monkeypatch.setattr("app.storage.factory.settings.STORAGE_LOCAL_ROOT", str(local_root))
    storage = get_storage_for("local", session)
    assert storage.driver == "local"


def test_attachment_play_url_local(session, tenant, test_user):
    att = create_attachment(
        session,
        tenant_id=tenant.id,
        uploader_id=test_user.id,
        storage_driver="local",
        storage_key="1/x/y/z.jpg",
        original_filename="z.jpg",
        content_type="image/jpeg",
        size=100,
        sha256="deadbeef",
    )
    url = attachment_play_url(att, db=session)
    assert url == f"/api/files/{att.id}"


def test_build_storage_unknown_raises():
    from app.storage.config import CloudDriverConfig, StorageConfig

    empty = CloudDriverConfig()
    cfg = StorageConfig(enabled=False, driver="local", local_root="/tmp", aliyun_oss=empty, tencent_cos=empty, qiniu=empty)
    with pytest.raises(ValueError):
        build_storage("unknown_driver", cfg)
