# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""v2.2.4 两项加固的单测：覆盖前可写性预检 + 重启健康判定纠偏。

背景：2026-11-05 v2.2.3 端到端验证暴露两个真缺陷——
  P1 任务 #4：root 属主文件导致覆盖第 1 个文件就 PermissionError，回灌同样被挡；
  P0 任务 #5/#6：宝塔自愈 3m36s > 守护脚本 180s 窗口，健康服务被标 failed。
"""
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import upgrade_service as us

FAKE_UID = 1000  # 模拟 www：与测试文件属主 root 不同，走 other 权限位


@pytest.fixture(autouse=True)
def _isolate_upgrade_log_dir(tmp_path, monkeypatch):
    """把 LOG_DIR 指到临时目录，避免磁盘残留影响宽限计算。

    ``_restart_started_at()`` 会读 ``restart_{id}.sh`` 的 mtime 当计时起点。
    测试机上的 ``backend/data/upgrade_logs`` 可能真留着 id=7 的旧脚本，那样
    宽限就从「刚刚」算起，本该判 failed 的用例会退化成本「暂缓判定」——
    测出来的绿色是假的。所有用例统一隔离，别靠单个用例自觉。
    """
    monkeypatch.setattr(us, "LOG_DIR", tmp_path)


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


# ── P0：守护脚本自验健康、只写终态 ──────────────────────────────────────

def test_restart_script_polls_health_and_writes_terminal_state_only():
    """守护脚本自己验健康，结果文件**只写终态** ok=1 / ok=0。

    为什么不能写中间态：回滚会把代码换回旧版本，重启后是【旧代码】在跑
    reconcile。v2.2.3 及更早的判定是 ``if ok == "1"`` 否则一律 failed，
    于是 v2.2.5 写的 ``ok=pending`` 被旧代码判成失败——服务明明健康，任务却
    记 failed。终态是唯一能跨版本互认的协议。

    为什么现在可以等健康：脚本以 start_new_session + cwd=/tmp 运行，不在项目
    进程树内，宝塔不会把它当成主进程写进 pid 文件（这一点另有用例锁死，
    见 test_guard_spawns_outside_project_root）。
    """
    body = us._build_restart_script(
        job_id=9, target_version="v2.2.6", pid=12345, py=Path("/usr/bin/python3"), custom=""
    )

    # 自验健康：探测函数 + 截止时间 + 双通道（curl 优先、python 兜底）
    assert "probe() {" in body
    assert "DEADLINE" in body
    assert "curl -fsS" in body
    assert "urllib.request" in body

    # 只写终态
    assert 'echo "ok=$OK"' in body
    assert "ok=pending" not in body

    # 绝不自己拉起进程：手动 nohup 会抢端口、让宝塔自愈报 address already in use
    for forbidden in ("nohup", "setsid", '"$PY" -m uvicorn'):
        assert forbidden not in body, forbidden


def test_restart_script_window_comes_from_constants(monkeypatch):
    """窗口与轮询间隔由常量注入，不写死在脚本里，便于按现场调整。"""
    monkeypatch.setattr(us, "RESTART_GRACE_SECONDS", 120)
    monkeypatch.setattr(us, "RESTART_POLL_INTERVAL", 5)

    body = us._build_restart_script(
        job_id=1, target_version="v2.0.0", pid=None, py=Path("/p"), custom=""
    )

    assert "WAIT='120'" in body
    assert "STEP='5'" in body


def test_restart_script_is_valid_bash(tmp_path):
    """生成的脚本必须能通过 ``bash -n``。

    f-string 里写 bash 时 ``{}`` 容易漏转义，那是运行时才炸的错误，
    语法检查是成本最低的拦截点。
    """
    body = us._build_restart_script(
        job_id=2, target_version="v2.2.6", pid=1, py=Path("/usr/bin/python3"), custom=""
    )
    script = tmp_path / "guard.sh"
    script.write_text(body, encoding="utf-8")

    res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


# ── P0：重启宽限的计时起点 ──────────────────────────────────────────────

def test_restart_started_at_prefers_script_mtime(tmp_path, monkeypatch):
    """宽限从守护脚本 mtime 算起，而不是任务创建时刻。

    否则备份 + 装依赖 + 迁移的耗时会整段吃掉等待窗口（lightmes 上实测到
    「服务起来 13 秒后任务才判失败」的账实不符）。
    """
    monkeypatch.setattr(us, "LOG_DIR", tmp_path)
    script = tmp_path / "restart_7.sh"
    script.write_text("", encoding="utf-8")
    stamp = time.time() - 30
    os.utime(script, (stamp, stamp))

    job = _job(id=7, started_at=datetime.now() - timedelta(seconds=1800))
    started = us._restart_started_at(job)

    assert started is not None
    assert 25 < (datetime.now() - started).total_seconds() < 35


def test_restart_started_at_falls_back_to_job_started_at(tmp_path, monkeypatch):
    """脚本文件不存在时回退到 job.started_at，不能因此返回 None 卡死任务。"""
    monkeypatch.setattr(us, "LOG_DIR", tmp_path)
    stamp = datetime.now() - timedelta(seconds=120)

    assert us._restart_started_at(_job(id=8, started_at=stamp)) == stamp


def test_guard_spawns_outside_project_root(monkeypatch, tmp_path):
    """守护脚本必须以 /tmp 为 cwd 启动，避免被宝塔当成项目主进程。"""
    captured: dict = {}
    monkeypatch.setattr(us, "LOG_DIR", tmp_path)
    monkeypatch.setattr(us, "_listener_pid", lambda: 12345)
    monkeypatch.setattr(us, "_venv_python", lambda: Path("/usr/bin/python3"))
    monkeypatch.setattr(us, "_log", lambda *a, **k: None)
    monkeypatch.setattr(us, "RESTART_CMD", "")

    class _FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured.update(kwargs)

    monkeypatch.setattr(us.subprocess, "Popen", _FakePopen)
    us._spawn_restart_guard(1, "v2.2.5")

    assert captured["cwd"] == "/tmp"
    assert captured["start_new_session"] is True


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


def test_reconcile_resolves_pending_when_service_is_healthy(monkeypatch):
    """v2.2.5 旧脚本残留的 ok=pending，reconcile 仍要能实测定终态。

    v2.2.6 起脚本只写终态，但历史任务的结果文件还躺在 /tmp 里；保留这条
    向后兼容路径，避免升级完重启时把「其实已经成功」的旧任务留在 running。
    """
    job = _job()
    db = _FakeDB(job)
    monkeypatch.setattr(us, "_read_restart_result", lambda _p: {"ok": "pending", "version": "", "finished_at": "x"})
    monkeypatch.setattr(us, "_probe_health", lambda: {"version": job.to_version, "db": "up"})

    us._reconcile_restart_jobs(db)

    assert job.status == "success"
    assert job.stage == "done"
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
