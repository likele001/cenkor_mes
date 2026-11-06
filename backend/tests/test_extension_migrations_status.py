"""扩展迁移成功后清理 ``broken`` 标记的单元测试。

背景：``run_migrations`` 的失败分支会写 ``status="broken"``，但成功分支原先只刷新
health、不碰 status，导致迁移修好后 registry 仍是 broken——health 说 ok、status 说坏，
运维看到自相矛盾的告警。``clear_broken_status`` 补上这一步。
"""
from __future__ import annotations

import pytest

from app.extension_host import migrations as M


@pytest.fixture()
def captured(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """拦截 registry 写入；默认 registry 里该扩展是 broken。"""
    calls: list[dict] = []
    monkeypatch.setattr(M, "load_registry", lambda: {"qcode": {"status": "broken"}})
    monkeypatch.setattr(M, "update_registry", lambda key, **kw: calls.append({"key": key, **kw}) or {})
    return calls


def test_broken_status_is_restored(captured: list[dict]) -> None:
    """失败的扩展迁移成功后，broken 恢复为 installed_enabled。"""
    assert M.clear_broken_status("qcode") is True
    assert captured == [{"key": "qcode", "status": "installed_enabled"}]


@pytest.mark.parametrize("status", ["installed_enabled", "rollback_blocked", "uninstalled_keep"])
def test_other_statuses_untouched(captured: list[dict], monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    """只有 broken 该被清理；回滚受阻 / 保留数据卸载都要保留原样。"""
    monkeypatch.setattr(M, "load_registry", lambda: {"qcode": {"status": status}})
    assert M.clear_broken_status("qcode") is False
    assert captured == []


def test_unknown_key_untouched(captured: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    """registry 里没有该扩展时不写脏数据。"""
    monkeypatch.setattr(M, "load_registry", lambda: {})
    assert M.clear_broken_status("not_installed") is False
    assert captured == []


def test_registry_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """状态恢复失败不能把一次成功的迁移判成失败。"""

    def boom() -> dict:
        raise RuntimeError("registry 损坏")

    monkeypatch.setattr(M, "load_registry", boom)
    assert M.clear_broken_status("qcode") is False


def test_success_path_calls_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_migrations 成功分支必须调用恢复逻辑（防未来重构漏掉）。"""
    from pathlib import Path

    called: list[str] = []

    class _FakeStore:
        def load(self, name: str, default=None):
            return default if default is not None else {}

        def save(self, name: str, data) -> None:
            pass

    class _FakeRuntime:
        installed = {"qcode": {"path": "/tmp/qcode"}}
        # 给定 store 可避免 run_migrations 落到真实 StateStore 去写磁盘
        store = _FakeStore()

        @staticmethod
        def is_enabled(key: str) -> bool:
            return True

    class _FakeSession:
        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    from app.core import db as core_db

    monkeypatch.setattr(M, "runtime", _FakeRuntime())
    monkeypatch.setattr(M, "apply_for_key", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(M, "write_health", lambda *a, **kw: {})
    monkeypatch.setattr(M, "clear_broken_status", lambda key: called.append(key) or True)
    monkeypatch.setattr(core_db, "SessionLocal", lambda: _FakeSession())

    M.run_migrations(Path("/tmp"), db=None)
    assert called == ["qcode"]
