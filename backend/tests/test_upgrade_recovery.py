# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""升级失败时把代码与已换入的前端产物退回升级前。"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from app.services import upgrade_service as us


def _cp(rc: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


class _FakeDB:
    def __init__(self, job):
        self.job = job

    def add(self, obj):
        pass

    def commit(self):
        pass

    def get(self, model, pk):
        return self.job if pk == self.job.id else None


@pytest.fixture
def upgrade_env(monkeypatch):
    job = SimpleNamespace(
        id=7,
        from_ref="oldsha",
        from_version="v2.2.0",
        to_version="v2.2.1",
        backup_path="/tmp/backup.sql.gz",
        status="pending",
        stage="backup",
    )
    db = _FakeDB(job)
    logs: list[str] = []
    calls: list[list[str]] = []

    monkeypatch.setattr(us, "_log", lambda _jid, msg: logs.append(msg))
    monkeypatch.setattr(us, "_set", lambda db, job, **kw: None)
    monkeypatch.setattr(us, "_backup_database", lambda j: "/tmp/backup.sql.gz")
    monkeypatch.setattr(us, "_venv_python", lambda: "python")
    monkeypatch.setattr(us, "read_local_version", lambda: "v2.2.1")
    monkeypatch.setattr(us, "working_tree_dirty", lambda: False)

    return SimpleNamespace(db=db, job=job, logs=logs, calls=calls, monkeypatch=monkeypatch)


@pytest.fixture
def env(upgrade_env):
    return upgrade_env


def _install_run_cmd(env, *, alembic_rc=0):
    def fake(cmd, cwd=None, timeout=600, proc_env=None):
        env.calls.append(list(cmd))
        if cmd[:2] == ["git", "-C"]:
            if "fetch" in cmd:
                return _cp(0)
            if "checkout" in cmd:
                return _cp(0)
            return _cp(0)
        if "-c" in cmd and "alembic" in " ".join(cmd):
            return _cp(alembic_rc, "", "migration failed" if alembic_rc else "")
        return _cp(0, "ok")

    env.monkeypatch.setattr(us, "_run_cmd", fake)


def _restore_calls(env) -> list[list[str]]:
    return [c for c in env.calls if "checkout" in c and "-f" in c]


def test_build_failure_restores_code(env):
    _install_run_cmd(env)
    env.monkeypatch.setattr(
        us, "_prepare_frontends",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("build boom")),
    )

    with pytest.raises(RuntimeError, match="build boom"):
        us._do_upgrade(env.db, env.job)

    restores = _restore_calls(env)
    assert restores, "构建失败后必须退回 from_ref"
    assert restores[-1][-1] == "oldsha"
    assert any("代码已恢复到 oldsha" in m for m in env.logs)


def test_migration_failure_restores_code(env):
    _install_run_cmd(env, alembic_rc=1)
    env.monkeypatch.setattr(us, "_prepare_frontends", lambda *a, **kw: [])

    with pytest.raises(RuntimeError, match="数据库迁移失败"):
        us._do_upgrade(env.db, env.job)

    restores = _restore_calls(env)
    assert restores and restores[-1][-1] == "oldsha"
    assert any("数据库迁移未回滚" in m for m in env.logs)


def test_successful_migration_does_not_restore(env):
    _install_run_cmd(env, alembic_rc=0)
    env.monkeypatch.setattr(us, "_prepare_frontends", lambda *a, **kw: [])
    env.monkeypatch.setattr(us, "_spawn_restart_guard", lambda *a, **kw: False)

    us._do_upgrade(env.db, env.job)

    assert not _restore_calls(env)
    assert any("重启脚本启动失败" in m for m in env.logs)


def test_restore_code_without_ref_logs_warning(monkeypatch):
    logs: list[str] = []
    monkeypatch.setattr(us, "_log", lambda _jid, msg: logs.append(msg))
    job = SimpleNamespace(from_ref=None, backup_path=None)
    us._restore_code(job, 1)
    assert any("未记录回滚点" in m for m in logs)


def test_restore_code_reports_git_failure(monkeypatch):
    logs: list[str] = []
    monkeypatch.setattr(us, "_log", lambda _jid, msg: logs.append(msg))
    monkeypatch.setattr(us, "_run_cmd", lambda *a, **kw: _cp(1, "", "boom"))
    job = SimpleNamespace(from_ref="oldsha", backup_path="/tmp/b.sql.gz")
    us._restore_code(job, 1)
    assert any("代码自动恢复失败" in m for m in logs)


# ── 前端产物回退 ─────────────────────────────────────────────────────


@pytest.fixture
def app_root(tmp_path, monkeypatch):
    d = tmp_path / "frontend-h5"
    d.mkdir()
    (d / "dist").mkdir()
    (d / "dist" / "index.html").write_text("old", encoding="utf-8")
    monkeypatch.setattr(us, "ROOT", tmp_path)
    return tmp_path


def test_restore_frontend_swaps_backup_back(app_root):
    app = "frontend-h5"
    out = app_root / app / ".dist-build-7"
    out.mkdir()
    (out / "index.html").write_text("new", encoding="utf-8")
    us._promote_frontend(app, out, 7)

    us._restore_frontend(app, 7)

    assert (app_root / app / "dist" / "index.html").read_text() == "old"
    assert not (app_root / app / "dist.__bak").exists()


def test_promote_frontends_strict_failure_stops_at_first_error(app_root, monkeypatch):
    built = []
    for name in ("frontend-h5", "frontend-admin-pro"):
        d = app_root / name
        (d / "dist").mkdir(parents=True, exist_ok=True)
        (d / "dist" / "index.html").write_text("old", encoding="utf-8")
        out = d / ".dist-build-7"
        out.mkdir()
        (out / "index.html").write_text("new", encoding="utf-8")
        built.append((name, out))

    def flaky(app, out_dir, job_id):
        if app == "frontend-admin-pro":
            raise OSError("disk full")

    monkeypatch.setattr(us, "_promote_frontend", flaky)
    with pytest.raises(OSError, match="disk full"):
        us._promote_frontends(built, 7, strict=True)


def test_promote_frontends_non_strict_reports_promoted(app_root, monkeypatch):
    built = []
    for name in ("frontend-h5", "frontend-admin-pro"):
        d = app_root / name
        (d / "dist").mkdir(parents=True, exist_ok=True)
        (d / "dist" / "index.html").write_text("old", encoding="utf-8")
        out = d / ".dist-build-7"
        out.mkdir()
        (out / "index.html").write_text("new", encoding="utf-8")
        built.append((name, out))

    original = us._promote_frontend

    def flaky(app, out_dir, job_id):
        if app == "frontend-admin-pro":
            raise OSError("disk full")
        original(app, out_dir, job_id)

    monkeypatch.setattr(us, "_promote_frontend", flaky)
    assert us._promote_frontends(built, 7, strict=False) == ["frontend-h5"]
