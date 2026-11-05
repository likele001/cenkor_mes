# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""产物包升级：不依赖 git / SSH / node 的安装路径。

覆盖三件事：
  1. 现场资产（.env、backend/data、node_modules）绝不被覆盖或删除；
  2. 前端 dist 走原子换入，不是逐文件覆盖；
  3. 上游删除的文件按清单精确清理，清单缺失时宁可留着。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import upgrade_service as us

PROTECTED_CUSTOMER_FILE = "backend/data/storage/客户上传.txt"


@pytest.fixture
def project(tmp_path, monkeypatch):
    """假的项目根，带现场资产与待清理的旧文件。"""
    root = tmp_path / "proj"
    (root / "backend/app").mkdir(parents=True)
    (root / "VERSION").write_text("v2.2.0\n", encoding="utf-8")
    (root / "backend/app/main.py").write_text("old", encoding="utf-8")
    (root / "backend/requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (root / "backend/.env").write_text("DB_URL=mysql://live\n", encoding="utf-8")
    (root / "backend/data/storage").mkdir(parents=True)
    (root / PROTECTED_CUSTOMER_FILE).write_text("keep", encoding="utf-8")
    for app in ("frontend-admin-pro", "frontend-h5"):
        (root / app / "dist").mkdir(parents=True)
        (root / app / "dist/index.html").write_text("old-dist", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts/removed-in-new.sh").write_text("bye", encoding="utf-8")

    monkeypatch.setattr(us, "ROOT", root)
    monkeypatch.setattr(us, "VERSION_FILE", root / "VERSION")
    monkeypatch.setattr(us, "BACKEND_DIR", root / "backend")
    monkeypatch.setattr(us, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(us, "_log", lambda _jid, _msg: None)
    return root


def _make_pkg(tmp_path: Path, version: str = "v2.2.1") -> Path:
    """造一个产物包目录，故意塞进不该落地的文件。"""
    pkg = tmp_path / "pkg" / f"cenkormes-{version}"
    (pkg / "backend/app").mkdir(parents=True)
    (pkg / "VERSION").write_text(version + "\n", encoding="utf-8")
    (pkg / "backend/app/main.py").write_text("new", encoding="utf-8")
    (pkg / "backend/requirements.txt").write_text("fastapi\nhttpx\n", encoding="utf-8")
    for app in ("frontend-admin-pro", "frontend-h5"):
        (pkg / app / "dist").mkdir(parents=True)
        (pkg / app / "dist/index.html").write_text("new-dist", encoding="utf-8")
    # 受保护内容：正常打不出来，这里刻意模拟「打包脚本有 bug」的情况
    (pkg / "backend/.env").write_text("DB_URL=hacked\n", encoding="utf-8")
    (pkg / "backend/data").mkdir(parents=True, exist_ok=True)
    (pkg / "backend/data/evil.txt").write_text("x", encoding="utf-8")
    return pkg


# ── 模式与保护规则 ────────────────────────────────────────────────────


def test_mode_defaults_to_artifact_without_git(project, monkeypatch):
    monkeypatch.setattr(us, "UPGRADE_MODE_ENV", "artifact")
    assert us.upgrade_mode() == "artifact"


def test_git_mode_without_repo_raises(project, monkeypatch):
    monkeypatch.setattr(us, "UPGRADE_MODE_ENV", "git")
    with pytest.raises(RuntimeError, match="不是 git 仓库"):
        us.upgrade_mode()


def test_auto_mode_picks_git_when_repo_exists(project, monkeypatch):
    (project / ".git").mkdir()
    monkeypatch.setattr(us, "UPGRADE_MODE_ENV", "auto")
    assert us.upgrade_mode() == "git"


@pytest.mark.parametrize(
    ("rel", "protected"),
    [
        ("backend/.env", True),
        (".env", True),
        ("backend/.env.production", True),
        ("backend/data/backups/a.sql.gz", True),
        ("backend/data/storage/x.png", True),
        ("node_modules/x/index.js", True),
        (".git/config", True),
        (".release-manifest.txt", True),
        ("frontend-h5/dist/index.html", True),
        ("frontend-h5/dist.__bak/index.html", True),
        ("backend/app/main.py", False),
        ("scripts/upgrade.sh", False),
        ("frontend-h5/src/App.vue", False),
    ],
)
def test_is_protected(rel, protected):
    assert us._is_protected(rel) is protected


# ── 覆盖与清理 ────────────────────────────────────────────────────────


def test_apply_package_keeps_live_assets_and_replaces_code(project):
    pkg = _make_pkg(project.parent)

    us._apply_package(pkg, 7)

    assert (project / "backend/app/main.py").read_text() == "new"
    assert (project / "backend/requirements.txt").read_text() == "fastapi\nhttpx\n"
    # 现场配置与客户数据必须原样
    assert (project / "backend/.env").read_text() == "DB_URL=mysql://live\n"
    assert (project / PROTECTED_CUSTOMER_FILE).read_text() == "keep"
    assert not (project / "backend/data/evil.txt").exists()
    # 前端走原子换入，旧产物挪到 dist.__bak
    assert (project / "frontend-h5/dist/index.html").read_text() == "new-dist"
    assert (project / "frontend-h5/dist.__bak/index.html").read_text() == "old-dist"


def test_apply_package_removes_files_deleted_upstream(project):
    (project / us.MANIFEST_NAME).write_text(
        "backend/app/main.py\nscripts/removed-in-new.sh\n" + PROTECTED_CUSTOMER_FILE + "\n",
        encoding="utf-8",
    )

    us._apply_package(_make_pkg(project.parent), 7)

    assert not (project / "scripts/removed-in-new.sh").exists(), "上游删掉的文件应被清理"
    assert (project / PROTECTED_CUSTOMER_FILE).exists(), "受保护路径不能被清理"


def test_apply_package_skips_cleanup_without_manifest(project):
    us._apply_package(_make_pkg(project.parent), 7)

    # 无清单时宁可留垃圾，也不能删无法确认归属的文件
    assert (project / "scripts/removed-in-new.sh").exists()


def test_apply_package_writes_manifest(project):
    us._apply_package(_make_pkg(project.parent), 7)

    rows = set((project / us.MANIFEST_NAME).read_text(encoding="utf-8").split())
    assert "backend/app/main.py" in rows
    assert "frontend-h5/dist/index.html" in rows
    # 受保护路径不该进清单
    assert "backend/.env" not in rows
    assert "backend/data/evil.txt" not in rows


def test_apply_package_without_dist_keeps_live_frontend(project):
    pkg = _make_pkg(project.parent)
    for app in ("frontend-admin-pro", "frontend-h5"):
        for f in (pkg / app / "dist").iterdir():
            f.unlink()
        (pkg / app / "dist").rmdir()

    us._apply_package(pkg, 7)

    assert (project / "frontend-h5/dist/index.html").read_text() == "old-dist"


def test_prune_refuses_paths_outside_root(project, tmp_path):
    # 清单被篡改成 ../outside.txt 这类路径时不能真删
    outside = tmp_path / "outside.txt"
    outside.write_text("safe", encoding="utf-8")

    us._prune_removed_files({"../outside.txt"}, set(), 7)

    assert outside.read_text() == "safe"


# ── 包校验 ────────────────────────────────────────────────────────────


def test_verify_package_rejects_version_mismatch(project):
    root = _make_pkg(project.parent, version="v2.2.1")
    with pytest.raises(RuntimeError, match="不一致"):
        us._verify_package(root, "v2.2.2", 7)


def test_verify_package_requires_core_files(project):
    root = _make_pkg(project.parent)
    (root / "backend/app/main.py").unlink()
    with pytest.raises(RuntimeError, match="缺少关键文件"):
        us._verify_package(root, "v2.2.1", 7)


def test_package_root_accepts_flat_and_nested(project, tmp_path):
    nested = tmp_path / "n" / "cenkormes-v1.0.0"
    (nested).mkdir(parents=True)
    (nested / "VERSION").write_text("v1.0.0\n", encoding="utf-8")
    assert us._package_root(tmp_path / "n") == nested

    flat = tmp_path / "f"
    flat.mkdir()
    (flat / "VERSION").write_text("v1.0.0\n", encoding="utf-8")
    assert us._package_root(flat) == flat


def test_package_root_rejects_garbage(tmp_path):
    junk = tmp_path / "junk"
    junk.mkdir()
    with pytest.raises(RuntimeError, match="结构异常"):
        us._package_root(junk)


# ── 摘要校验 ──────────────────────────────────────────────────────────


def test_asset_sha256_prefers_digest():
    rel = {"version": "v2.2.1", "assets": []}
    digest = "sha256:" + "a" * 64
    assert us._asset_sha256(rel, {"name": "x.tar.gz", "digest": digest}) == "a" * 64


def test_asset_sha256_refuses_when_missing(monkeypatch):
    monkeypatch.setattr(us, "ALLOW_UNVERIFIED", False)
    with pytest.raises(RuntimeError, match="没有可用的 SHA256"):
        us._asset_sha256({"version": "v2.2.1", "assets": []}, {"name": "x.tar.gz", "digest": ""})


def test_asset_sha256_allows_skip_when_configured(monkeypatch):
    monkeypatch.setattr(us, "ALLOW_UNVERIFIED", True)
    assert us._asset_sha256({"assets": []}, {"name": "x.tar.gz", "digest": ""}) == ""


# ── 主流程 ────────────────────────────────────────────────────────────


def test_upgrade_aborts_before_touching_files_when_release_missing(project, monkeypatch):
    job = _job()

    def boom(_version):
        raise RuntimeError("远端没有 v2.2.1 的正式 Release")

    monkeypatch.setattr(us, "_find_release", boom)
    monkeypatch.setattr(us, "_check_disk_space", lambda _jid: None)
    monkeypatch.setattr(us, "_backup_database", lambda _job: "/tmp/b.sql.gz")
    monkeypatch.setattr(us, "_set", lambda _db, _job, **_kw: None)

    with pytest.raises(RuntimeError, match="没有 v2.2.1"):
        us._do_upgrade_artifact(_FakeDB(), job)

    assert (project / "backend/app/main.py").read_text() == "old"


def _job():
    from types import SimpleNamespace

    return SimpleNamespace(
        id=7,
        from_version="v2.2.0",
        to_version="v2.2.1",
        backup_path=None,
        status="pending",
        stage="backup",
    )


class _FakeDB:
    def commit(self) -> None:
        pass
