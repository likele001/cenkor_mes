# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""在线升级的前端构建步骤：改动检测、临时构建、原子换入、失败清理。"""

import subprocess
from types import SimpleNamespace

import pytest

from app.services import upgrade_service as us


def _cp(rc: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


@pytest.fixture
def app_root(tmp_path, monkeypatch):
    """两个前端应用目录 + 假 npm + 静默日志。"""
    for name in ("frontend-admin-pro", "frontend-h5"):
        d = tmp_path / name
        (d / "node_modules").mkdir(parents=True)
        (d / "package.json").write_text("{}", encoding="utf-8")
        (d / "dist").mkdir()
        (d / "dist" / "index.html").write_text("old", encoding="utf-8")
    monkeypatch.setattr(us, "ROOT", tmp_path)
    monkeypatch.setattr(us, "_npm_bin", lambda: "npm")
    logs: list[str] = []
    monkeypatch.setattr(us, "_log", lambda _jid, msg: logs.append(msg))
    return tmp_path, logs


# ── 改动检测 ─────────────────────────────────────────────────────────


def test_changed_apps_empty_when_no_diff(monkeypatch):
    seen: list[list[str]] = []

    def fake(cmd, **kwargs):
        seen.append(cmd)
        return _cp(0, "")

    monkeypatch.setattr(us, "_run_cmd", fake)
    assert us._changed_frontend_apps("a", "b") == []
    assert "frontend-admin-pro" in seen[0]
    assert "frontend-h5" in seen[0]


def test_changed_apps_parses_and_orders(monkeypatch):
    out = "frontend-h5/src/pages/Home.vue\nREADME.md\nfrontend-admin-pro/src/main.ts\n"
    monkeypatch.setattr(us, "_run_cmd", lambda cmd, **kw: _cp(0, out))
    assert us._changed_frontend_apps("a", "b") == ["frontend-admin-pro", "frontend-h5"]


def test_changed_apps_all_when_ref_missing():
    assert us._changed_frontend_apps(None, "v1.0.0") == ["frontend-admin-pro", "frontend-h5"]
    assert us._changed_frontend_apps("abc", None) == ["frontend-admin-pro", "frontend-h5"]


def test_changed_apps_git_failure_raises(monkeypatch):
    monkeypatch.setattr(us, "_run_cmd", lambda cmd, **kw: _cp(128, "", "bad revision"))
    with pytest.raises(RuntimeError, match="比较前端源码改动失败"):
        us._changed_frontend_apps("a", "b")


# ── 构建 ─────────────────────────────────────────────────────────────


def _fake_build(cmd, cwd=None, **kwargs):
    out_name = cmd[cmd.index("--outDir") + 1]
    out = cwd / out_name
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text("new", encoding="utf-8")
    return _cp(0, "built")


def test_build_frontend_writes_to_temp_dir(app_root, monkeypatch):
    root, logs = app_root
    calls: list[list[str]] = []

    def fake(cmd, **kwargs):
        calls.append(cmd)
        return _fake_build(cmd, **kwargs)

    monkeypatch.setattr(us, "_run_cmd", fake)
    out = us._build_frontend("frontend-admin-pro", 7)
    assert out == root / "frontend-admin-pro" / ".dist-build-7"
    assert (out / "index.html").read_text() == "new"
    assert calls[0][:3] == ["npm", "run", "build"]
    # 线上 dist 未被触碰
    assert (root / "frontend-admin-pro" / "dist" / "index.html").read_text() == "old"
    assert any("npm run build" in m for m in logs)


def test_build_frontend_failure_cleans_temp_and_keeps_dist(app_root, monkeypatch):
    root, _ = app_root

    def fake(cmd, cwd=None, **kwargs):
        (cwd / cmd[cmd.index("--outDir") + 1]).mkdir(parents=True, exist_ok=True)
        return _cp(1, "", "vite failed")

    monkeypatch.setattr(us, "_run_cmd", fake)
    with pytest.raises(RuntimeError, match="构建失败"):
        us._build_frontend("frontend-h5", 8)
    assert not (root / "frontend-h5" / ".dist-build-8").exists()
    assert (root / "frontend-h5" / "dist" / "index.html").read_text() == "old"


def test_build_frontend_missing_index_is_failure(app_root, monkeypatch):
    monkeypatch.setattr(us, "_run_cmd", lambda cmd, **kw: _cp(0, "no output"))
    with pytest.raises(RuntimeError, match="构建失败"):
        us._build_frontend("frontend-h5", 9)


# ── 换入 ─────────────────────────────────────────────────────────────


def test_promote_swaps_and_keeps_backup(app_root):
    root, logs = app_root
    out = root / "frontend-admin-pro" / ".dist-build-1"
    out.mkdir()
    (out / "index.html").write_text("new", encoding="utf-8")

    us._promote_frontend("frontend-admin-pro", out, 1)

    assert (root / "frontend-admin-pro" / "dist" / "index.html").read_text() == "new"
    assert (root / "frontend-admin-pro" / "dist.__bak" / "index.html").read_text() == "old"
    assert any("换入 dist" in m for m in logs)


# ── 编排：skip / strict / 降级 ───────────────────────────────────────


def test_prepare_skips_when_flag(app_root, monkeypatch):
    _, logs = app_root
    monkeypatch.setattr(us, "_build_frontend", lambda app, jid: pytest.fail("不应构建"))
    job = SimpleNamespace(id=1)
    assert us._prepare_frontends(job, "a", "b", skip=True, strict=True) == []
    assert any("已跳过前端构建" in m for m in logs)


def test_prepare_returns_empty_when_no_source_change(app_root, monkeypatch):
    _, logs = app_root
    monkeypatch.setattr(us, "_changed_frontend_apps", lambda a, b: [])
    job = SimpleNamespace(id=1)
    assert us._prepare_frontends(job, "a", "b", skip=False, strict=True) == []
    assert any("前端源码无改动" in m for m in logs)


def test_prepare_strict_failure_cleans_built_temp(app_root, monkeypatch):
    root, _ = app_root

    def fake_build(app, jid):
        if app == "frontend-h5":
            raise RuntimeError("h5 boom")
        d = root / app / ".dist-build-1"
        d.mkdir()
        return d

    monkeypatch.setattr(us, "_changed_frontend_apps", lambda a, b: ["frontend-admin-pro", "frontend-h5"])
    monkeypatch.setattr(us, "_build_frontend", fake_build)
    job = SimpleNamespace(id=1)
    with pytest.raises(RuntimeError, match="h5 boom"):
        us._prepare_frontends(job, "a", "b", skip=False, strict=True)
    assert not (root / "frontend-admin-pro" / ".dist-build-1").exists()


def test_prepare_non_strict_logs_warning_and_returns_empty(app_root, monkeypatch):
    _, logs = app_root
    monkeypatch.setattr(us, "_changed_frontend_apps", lambda a, b: ["frontend-h5"])
    monkeypatch.setattr(us, "_build_frontend", lambda app, jid: (_ for _ in ()).throw(RuntimeError("boom")))
    job = SimpleNamespace(id=1)
    assert us._prepare_frontends(job, "a", "b", skip=False, strict=False) == []
    assert any("[警告]" in m for m in logs)


# ── 工作区守卫 ───────────────────────────────────────────────────────


def test_working_tree_dirty_detects_tracked_changes(monkeypatch):
    monkeypatch.setattr(us, "_run_cmd", lambda cmd, **kw: _cp(0, " M backend/app/main.py\n"))
    assert us.working_tree_dirty() is True
    monkeypatch.setattr(us, "_run_cmd", lambda cmd, **kw: _cp(0, "   \n"))
    assert us.working_tree_dirty() is False


def test_working_tree_dirty_git_failure_raises(monkeypatch):
    monkeypatch.setattr(us, "_run_cmd", lambda cmd, **kw: _cp(128, "", "not a repo"))
    with pytest.raises(RuntimeError, match="git status 失败"):
        us.working_tree_dirty()


def test_assert_clean_tree_blocks_dirty(monkeypatch):
    monkeypatch.setattr(us, "working_tree_dirty", lambda: True)
    with pytest.raises(RuntimeError, match="未提交改动"):
        us._assert_clean_tree("回滚")


def test_create_job_rejects_dirty_tree_before_db(monkeypatch):
    monkeypatch.setattr(us, "working_tree_dirty", lambda: True)
    with pytest.raises(ValueError, match="未提交改动"):
        us.create_job(None, "upgrade", "v9.9.9")


def test_check_update_reports_dirty_flag(monkeypatch):
    monkeypatch.setattr(us, "read_local_version", lambda: "v1.0.0")
    monkeypatch.setattr(us, "list_remote_tags", lambda: ["v1.1.0"])
    monkeypatch.setattr(us, "_disk_free_gb", lambda: 10.0)
    monkeypatch.setattr(us, "working_tree_dirty", lambda: True)
    out = us.check_update()
    assert out["has_update"] is True
    assert out["working_tree_dirty"] is True
    monkeypatch.setattr(us, "working_tree_dirty", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert us.check_update()["working_tree_dirty"] is False
