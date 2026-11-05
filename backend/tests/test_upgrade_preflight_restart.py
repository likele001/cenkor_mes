# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""v2.2.4 两项加固的单测：覆盖前可写性预检 + 重启健康判定纠偏。

背景：2026-11-05 v2.2.3 端到端验证暴露两个真缺陷——
  P1 任务 #4：root 属主文件导致覆盖第 1 个文件就 PermissionError，回灌同样被挡；
  P0 任务 #5/#6：宝塔自愈 3m36s > 守护脚本 180s 窗口，健康服务被标 failed。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import upgrade_service as us

FAKE_UID = 1000  # 模拟 www：与测试文件属主 root 不同，走 other 权限位


def _chmod_tree(root: Path, *, dmode: int = 0o777, fmode: int = 0o666) -> None:
    """把整棵树对 other 放开，作为「当前身份可写」的基线。"""
    root.chmod(dmode)
    for d in root.rglob("*"):
        d.chmod(dmode if d.is_dir() else fmode)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """假项目根 + 假产物包；预检上下文全部注入 tmp_path。"""
    root = tmp_path / "proj"
    (root / "backend/app").mkdir(parents=True)
    (root / "VERSION").write_text("v2.2.3\n", encoding="utf-8")
    (root / "backend/app/main.py").write_text("old", encoding="utf-8")
    for app in ("frontend-admin-pro", "frontend-h5"):
        (root / app / "dist/assets").mkdir(parents=True)
        (root / app / "dist/index.html").write_text("old", encoding="utf-8")

    pkg = tmp_path / "pkg"
    (pkg / "backend/app").mkdir(parents=True)
    (pkg / "VERSION").write_text("v2.2.4\n", encoding="utf-8")
    (pkg / "backend/app/main.py").write_text("new", encoding="utf-8")
    for app in ("frontend-admin-pro", "frontend-h5"):
        (pkg / app / "dist").mkdir(parents=True)
        (pkg / app / "dist/index.html").write_text("new", encoding="utf-8")

    _chmod_tree(root)
    _chmod_tree(pkg)

    monkeypatch.setattr(us, "ROOT", root)
    monkeypatch.setattr(us, "VERSION_FILE", root / "VERSION")
    monkeypatch.setattr(us, "BACKEND_DIR", root / "backend")
    monkeypatch.setattr(us, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(us, "LOCK_FILE", tmp_path / "upgrade.lock")
    monkeypatch.setattr(us, "_log", lambda _jid, _msg: None)
    return root, pkg


def _job(**overrides) -> SimpleNamespace:
    base = dict(
        id=7,
        status="running",
        stage="restart",
        action="upgrade",
        to_version="v2.2.4",
        from_version="v2.2.3",
        started_at=datetime.now(),
        finished_at=None,
        error=None,
        backup_path=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeDB:
    """只实现 reconcile / verify 用到的 Session 接口，不碰任何真数据库。"""

    def __init__(self, job):
        self.job = job
        self.commits = 0

    def execute(self, _stmt):
        rows = [self.job] if self.job.status == "running" and self.job.stage == "restart" else []
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))

    def get(self, _model, _pk):
        return self.job

    def add(self, _obj):
        pass

    def commit(self):
        self.commits += 1


# ── P1：可写性预检 ──────────────────────────────────────────────────────

def test_preflight_passes_when_everything_is_writable(project):
    """全树可写时预检放行（用注入的非属主 uid，走 other 权限位）。"""
    root, pkg = project
    files, dists = us._collect_package_files(pkg)
    us._preflight_writable(files, dists, 1, uid=FAKE_UID, gids=frozenset())


def test_preflight_rejects_readonly_existing_file(project):
    """已存在文件不可写 → 报出该路径并给出 chown 修法。"""
    root, pkg = project
    (root / "LICENSE").write_text("license", encoding="utf-8")
    (root / "LICENSE").chmod(0o444)
    (pkg / "LICENSE").write_text("license new", encoding="utf-8")

    files, dists = us._collect_package_files(pkg)
    with pytest.raises(us.PreflightError) as exc:
        us._preflight_writable(files, dists, 1, uid=FAKE_UID, gids=frozenset())

    assert "LICENSE" in str(exc.value)
    assert "chown -R www:www" in str(exc.value)


def test_preflight_rejects_root_owned_dist_subdirectory(project):
    """dist 内子目录缺写位 → 旧产物 rmtree 会静默失败，必须提前拦下。"""
    root, pkg = project
    (root / "frontend-admin-pro/dist/assets").chmod(0o555)

    files, dists = us._collect_package_files(pkg)
    with pytest.raises(us.PreflightError) as exc:
        us._preflight_writable(files, dists, 1, uid=FAKE_UID, gids=frozenset())

    assert "frontend-admin-pro" in str(exc.value)


def test_preflight_rejects_unwritable_parent_for_new_file(project):
    """包内新增文件、目标父目录不可写 → 拒绝，避免 mkdir/copy2 中途炸。"""
    root, pkg = project
    (pkg / "docs/guide").mkdir(parents=True)
    (pkg / "docs/guide/new.md").write_text("new", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs").chmod(0o555)

    files, dists = us._collect_package_files(pkg)
    with pytest.raises(us.PreflightError) as exc:
        us._preflight_writable(files, dists, 1, uid=FAKE_UID, gids=frozenset())

    assert "docs/guide/new.md" in str(exc.value)


def test_apply_package_leaves_disk_untouched_when_preflight_fails(project, monkeypatch):
    """预检失败时 _apply_package 一个字节都不写（否则会留半新半旧代码）。

    测试进程是 root（真实可写一切），所以把预检包装成注入 www 身份的版本，
    复现生产里 root 属主文件对 www 不可写的场景。
    """
    root, pkg = project
    (root / "VERSION").chmod(0o444)
    real_preflight = us._preflight_writable
    monkeypatch.setattr(
        us,
        "_preflight_writable",
        lambda files, dists, jid: real_preflight(
            files, dists, jid, uid=FAKE_UID, gids=frozenset()
        ),
    )

    with pytest.raises(us.PreflightError):
        us._apply_package(pkg, 1, replace_dist=False)

    assert (root / "VERSION").read_text(encoding="utf-8") == "v2.2.3\n"
    assert (root / "backend/app/main.py").read_text(encoding="utf-8") == "old"
    assert (root / "frontend-admin-pro/dist/index.html").read_text(encoding="utf-8") == "old"


def test_do_upgrade_does_not_reinstall_on_preflight_error(monkeypatch, tmp_path):
    """预检失败必须直接中止，不能去下载旧包回灌（回灌也会被同一权限挡住）。"""
    job = _job(status="running", stage="preflight")
    db = _FakeDB(job)
    reinstalled: list[int] = []

    monkeypatch.setattr(us, "_set", lambda *a, **k: None)
    monkeypatch.setattr(us, "_log", lambda *a, **k: None)
    monkeypatch.setattr(us, "_check_disk_space", lambda _j: None)
    monkeypatch.setattr(us, "_backup_database", lambda _j: tmp_path / "backup.sql.gz")
    monkeypatch.setattr(us, "_find_release", lambda _v: {})
    monkeypatch.setattr(us, "_download_package", lambda _r, _j: tmp_path / "pkg.tar.gz")
    monkeypatch.setattr(us, "_extract_package", lambda _p, _j: tmp_path / "pkg")
    monkeypatch.setattr(us, "_verify_package", lambda *a, **k: None)
    monkeypatch.setattr(us, "_venv_python", lambda: Path("/usr/bin/python3"))
    monkeypatch.setattr(us, "_extract_dir", lambda _j: tmp_path / "extract")
    monkeypatch.setattr(us, "_restore_frontend", lambda *a, **k: None)
    monkeypatch.setattr(us, "_reinstall_version", lambda *a, **k: reinstalled.append(1))

    def _boom(*_a, **_k):
        raise us.PreflightError("模拟属主异常")

    monkeypatch.setattr(us, "_apply_package", _boom)

    with pytest.raises(us.PreflightError):
        us._do_upgrade_artifact(db, job)

    assert reinstalled == []


# ── P0：守护窗口 ────────────────────────────────────────────────────────

def test_restart_script_waits_long_enough_and_reports_two_phases():
    """窗口来自 VERIFY_TIMEOUT，旧 180s 循环必须彻底消失。"""
    body = us._build_restart_script(
        job_id=9, target_version="v2.2.4", pid=12345, py=Path("/usr/bin/python3"), custom=""
    )
    assert us.VERIFY_TIMEOUT >= 360
    assert f"MAX_WAIT='{us.VERIFY_TIMEOUT}'" in body
    assert "seq 1 60" not in body
    assert "DEADLINE=" in body
    assert "健康端点已响应" in body  # 区分「没起来」与「起来了但版本没换」


# ── P0：reconcile 实测复核 ──────────────────────────────────────────────

def test_reconcile_corrects_guard_timeout_when_service_is_healthy(monkeypatch, tmp_path):
    """守护脚本超时但实测健康且版本匹配 → 判成功，不再账实不符。"""
    job = _job()
    db = _FakeDB(job)
    monkeypatch.setattr(us, "_read_restart_result", lambda _p: {"ok": "0", "version": "", "finished_at": "x"})
    monkeypatch.setattr(us, "_probe_health", lambda: {"version": "v2.2.4", "db": "up"})

    us._reconcile_restart_jobs(db)

    assert job.status == "success"
    assert job.stage == "done"
    assert job.error is None
    assert db.commits == 1


def test_reconcile_keeps_failed_when_service_is_still_down(monkeypatch):
    """过了启动宽限期服务仍没起来 → 判 failed，不能靠复核洗白。"""
    from datetime import timedelta

    job = _job(started_at=datetime.now() - timedelta(minutes=20))
    db = _FakeDB(job)
    monkeypatch.setattr(us, "_read_restart_result", lambda _p: {"ok": "0", "version": "", "finished_at": "x"})
    monkeypatch.setattr(us, "_probe_health", lambda: None)

    us._reconcile_restart_jobs(db)

    assert job.status == "failed"
    assert "健康校验失败" in job.error


def test_reconcile_defers_while_service_is_still_starting(monkeypatch):
    """startup 钩子早于端口可用：暂缓判定，等下一次 reconcile，不误标 failed。"""
    job = _job()
    db = _FakeDB(job)
    monkeypatch.setattr(us, "_read_restart_result", lambda _p: {"ok": "0", "version": "", "finished_at": "x"})
    monkeypatch.setattr(us, "_probe_health", lambda: None)

    us._reconcile_restart_jobs(db)

    assert job.status == "running"
    assert job.stage == "restart"
    assert db.commits == 0


def test_reconcile_keeps_failed_on_version_mismatch(monkeypatch, tmp_path):
    """服务起来了但代码没换 → 判 failed，版本不匹配不能算成功。"""
    job = _job()
    db = _FakeDB(job)
    monkeypatch.setattr(us, "_read_restart_result", lambda _p: {"ok": "0", "version": "v2.2.3", "finished_at": "x"})
    monkeypatch.setattr(us, "_probe_health", lambda: {"version": "v2.2.3"})

    us._reconcile_restart_jobs(db)

    assert job.status == "failed"


# ── P0：verify 纠正 ─────────────────────────────────────────────────────

def test_verify_corrects_failed_job_with_restart_result(monkeypatch):
    """误判的 failed 可被纠正，回滚任务纠正成 rolled_back。"""
    job = _job(status="failed", stage="done", action="rollback", error="重启后健康校验失败")
    db = _FakeDB(job)
    monkeypatch.setattr(us, "_wait_healthy", lambda _v, _s: (True, "v2.2.4"))
    monkeypatch.setattr(us, "_read_restart_result", lambda _p: {"ok": "0", "finished_at": "x"})

    result = us.verify_job(db, 7)

    assert result["corrected"] is True
    assert result["status"] == "rolled_back"
    assert job.error is None


def test_verify_refuses_to_correct_failed_without_restart_result(monkeypatch):
    """失败在 checkout/备份阶段的任务没有守护结果文件，不许洗成成功。"""
    job = _job(status="failed", stage="done", error="写入 LICENSE 失败")
    db = _FakeDB(job)
    monkeypatch.setattr(us, "_wait_healthy", lambda _v, _s: (True, "v2.2.4"))
    monkeypatch.setattr(us, "_read_restart_result", lambda _p: None)

    result = us.verify_job(db, 7)

    assert result["corrected"] is False
    assert job.status == "failed"


def test_verify_refuses_to_correct_when_version_mismatch(monkeypatch):
    """实测版本不匹配时保持 failed。"""
    job = _job(status="failed", stage="done", error="重启后健康校验失败")
    db = _FakeDB(job)
    monkeypatch.setattr(us, "_wait_healthy", lambda _v, _s: (False, "v2.2.3"))
    monkeypatch.setattr(us, "_read_restart_result", lambda _p: {"ok": "0", "finished_at": "x"})

    result = us.verify_job(db, 7)

    assert result["corrected"] is False
    assert job.status == "failed"
