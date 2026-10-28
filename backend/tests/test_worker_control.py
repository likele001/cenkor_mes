# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""定时任务页的 Worker / Beat 运维测试。

celery 控制通道、systemctl 与 Redis 全部 mock，不依赖本机是否真的跑着
worker/beat，也不向 broker 发真实 shutdown、不写真实 Redis 信号。
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.admin import cron_jobs as api
from app.core.config import settings
from app.crud.platform_setting import set_setting
from app.schedulers.database import RELOAD_KEY, SHUTDOWN_KEY, check_control_signals
from app.services import worker_control as wc


@pytest.fixture(autouse=True)
def _worker_settings(monkeypatch):
    monkeypatch.setattr(settings, "CELERY_WORKER_PREFIX", "cenkormes_worker@")
    monkeypatch.setattr(settings, "CELERY_WORKER_SERVICE", "cenkormes-celery")
    monkeypatch.setattr(settings, "BEAT_SERVICE_NAME", "cenkormes-beat")


class _Inspect:
    def __init__(self, hosts: list[str], active: dict | None = None, error: Exception | None = None):
        self._hosts = hosts
        self._active = active or {}
        self._error = error

    def ping(self):
        if self._error:
            raise self._error
        return {h: {"ok": "pong"} for h in self._hosts}

    def active(self):
        return self._active


class _Control:
    def __init__(self, hosts: list[str], active: dict | None = None, error: Exception | None = None):
        self._hosts = hosts
        self._active = active
        self._error = error
        self.broadcasts: list[dict] = []

    def inspect(self, timeout=None):
        return _Inspect(self._hosts, self._active, self._error)

    def broadcast(self, command, destination=None, reply=True):
        self.broadcasts.append({"command": command, "destination": destination, "reply": reply})


def _fake_systemd(stdout: str, returncode: int = 0, stderr: str = ""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class _FakeRedis:
    def __init__(self, data: dict | None = None, error: Exception | None = None):
        self.data = dict(data or {})
        self.error = error
        self.sets: list[tuple] = []
        self.deleted: list[str] = []

    def get(self, key):
        if self.error:
            raise self.error
        return self.data.get(key)

    def delete(self, key):
        self.deleted.append(key)
        self.data.pop(key, None)

    def set(self, key, value, ex=None):
        self.sets.append((key, value))
        self.data[key] = value

    def close(self):
        pass


# ── Worker ──

def test_worker_status_filters_prefix(monkeypatch):
    control = _Control(
        hosts=["other_worker@host-b", "cenkormes_worker@host-a"],
        active={"cenkormes_worker@host-a": [{"name": "stock_safety.scan", "time_start": 1.0}]},
    )
    monkeypatch.setattr(wc.celery, "control", control)

    out = wc.get_worker_status()

    assert out["ok"] is True
    assert out["configured"] is True
    assert out["prefix"] == "cenkormes_worker@"
    assert [w["hostname"] for w in out["workers"]] == ["cenkormes_worker@host-a"]
    assert out["workers"][0]["active_count"] == 1
    assert out["workers"][0]["active_tasks"][0]["name"] == "stock_safety.scan"


def test_worker_status_broker_error(monkeypatch):
    monkeypatch.setattr(wc.celery, "control", _Control([], error=RuntimeError("broker down")))

    out = wc.get_worker_status()

    assert out["ok"] is False
    assert "无法连接消息队列" in out["error"]
    assert out["workers"] == []


def test_worker_status_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "CELERY_WORKER_PREFIX", "")
    monkeypatch.setattr(wc.celery, "control", _Control(["cenkormes_worker@host-a"]))

    out = wc.get_worker_status()

    assert out["ok"] is True
    assert out["configured"] is False
    assert out["workers"] == []


def test_worker_restart_broadcasts_to_managed_only(monkeypatch):
    control = _Control(hosts=["cenkormes_worker@host-a", "other_worker@host-b"])
    monkeypatch.setattr(wc.celery, "control", control)

    out = wc.request_worker_restart()

    assert out["ok"] is True
    assert out["hosts"] == ["cenkormes_worker@host-a"]
    assert control.broadcasts == [
        {"command": "shutdown", "destination": ["cenkormes_worker@host-a"], "reply": False}
    ]


def test_worker_restart_offline(monkeypatch):
    monkeypatch.setattr(wc.celery, "control", _Control(hosts=[]))

    out = wc.request_worker_restart()

    assert out["ok"] is False
    assert "cenkormes-celery" in out["error"]
    assert "cenkormes_worker@" in out["error"]


def test_worker_restart_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "CELERY_WORKER_PREFIX", "")

    out = wc.request_worker_restart()

    assert out["ok"] is False
    assert "CELERY_WORKER_PREFIX" in out["error"]


# ── Beat ──

def test_beat_status_active(monkeypatch):
    captured: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return _fake_systemd(
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "SubState=running\n"
            "UnitFileState=enabled\n"
            "ActiveEnterTimestamp=Tue 2026-10-20 08:00:00 CST\n"
        )

    monkeypatch.setattr(wc.subprocess, "run", fake_run)

    out = wc.get_beat_status()

    assert out["configured"] is True
    assert out["installed"] is True
    assert out["active"] is True
    assert out["state"] == "active"
    assert out["unit"] == "cenkormes-beat"
    assert out["started_at"] == "2026-10-20T08:00:00"
    assert out["uptime_seconds"] is not None and out["uptime_seconds"] >= 0
    assert captured[0][:3] == ["systemctl", "show", "cenkormes-beat"]
    assert "--no-pager" in captured[0]


def test_beat_status_not_installed(monkeypatch):
    monkeypatch.setattr(
        wc.subprocess,
        "run",
        lambda cmd, **kwargs: _fake_systemd(
            "LoadState=not-found\nActiveState=inactive\nSubState=dead\n"
            "UnitFileState=\nActiveEnterTimestamp=\n"
        ),
    )

    out = wc.get_beat_status()

    assert out["active"] is False
    assert out["installed"] is False
    assert out["state"] == "inactive"
    assert out["load_state"] == "not-found"


def test_beat_status_systemctl_unavailable(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("systemctl")

    monkeypatch.setattr(wc.subprocess, "run", fake_run)

    out = wc.get_beat_status()

    assert out["active"] is False
    assert out["state"] == "unknown"
    assert out["installed"] is None


def test_beat_status_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "BEAT_SERVICE_NAME", "")

    out = wc.get_beat_status()

    assert out["active"] is False
    assert out["state"] == "disabled"
    assert out["configured"] is False


def test_beat_restart_success_signal_and_poll(monkeypatch):
    statuses = iter([
        {"active": True, "state": "active", "started_at": "2026-10-26T15:54:32",
         "installed": True, "unit": "cenkormes-beat"},
        {"active": True, "state": "active", "started_at": "2026-10-26T16:10:00",
         "installed": True, "unit": "cenkormes-beat"},
    ])
    monkeypatch.setattr(wc, "get_beat_status", lambda: next(statuses))
    monkeypatch.setattr(wc.time, "sleep", lambda _s: None)
    fake = _FakeRedis()
    monkeypatch.setattr(wc.redis_lib, "from_url", lambda *a, **k: fake)

    out = wc.request_beat_restart()

    assert out == {"ok": True, "unit": "cenkormes-beat", "started_at": "2026-10-26T16:10:00"}
    assert fake.sets == [(SHUTDOWN_KEY, "1")]
    assert fake.deleted == []


def test_beat_restart_inactive_rejected(monkeypatch):
    monkeypatch.setattr(
        wc,
        "get_beat_status",
        lambda: {"active": False, "state": "inactive", "started_at": None,
                 "installed": True, "unit": "cenkormes-beat"},
    )
    fake = _FakeRedis()
    monkeypatch.setattr(wc.redis_lib, "from_url", lambda *a, **k: fake)

    out = wc.request_beat_restart()

    assert out["ok"] is False
    assert "未运行" in out["error"]
    assert "手动启动" in out["error"]
    assert fake.sets == []


def test_beat_restart_not_installed(monkeypatch):
    monkeypatch.setattr(
        wc,
        "get_beat_status",
        lambda: {"active": False, "state": "inactive", "started_at": None,
                 "installed": False, "unit": "cenkormes-beat"},
    )

    out = wc.request_beat_restart()

    assert out["ok"] is False
    assert "未安装" in out["error"]


def test_beat_restart_redis_error(monkeypatch):
    monkeypatch.setattr(
        wc,
        "get_beat_status",
        lambda: {"active": True, "state": "active", "started_at": "2026-10-26T15:54:32",
                 "installed": True, "unit": "cenkormes-beat"},
    )
    monkeypatch.setattr(
        wc.redis_lib,
        "from_url",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )

    out = wc.request_beat_restart()

    assert out["ok"] is False
    assert "Redis" in out["error"]


def test_beat_restart_timeout(monkeypatch):
    monkeypatch.setattr(
        wc,
        "get_beat_status",
        lambda: {"active": True, "state": "active", "started_at": "2026-10-26T15:54:32",
                 "installed": True, "unit": "cenkormes-beat"},
    )
    monkeypatch.setattr(wc.time, "sleep", lambda _s: None)
    ticks = iter([0.0, 10.0, 100.0])
    monkeypatch.setattr(wc.time, "monotonic", lambda: next(ticks))
    fake = _FakeRedis()
    monkeypatch.setattr(wc.redis_lib, "from_url", lambda *a, **k: fake)

    out = wc.request_beat_restart()

    assert out["ok"] is False
    assert "未检测到" in out["error"]
    assert fake.sets == [(SHUTDOWN_KEY, "1")]
    assert fake.deleted == [SHUTDOWN_KEY], "超时后应清理残留退出信号，防止新 Beat 起来立刻再退"


def test_beat_restart_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "BEAT_SERVICE_NAME", "")

    out = wc.request_beat_restart()

    assert out["ok"] is False
    assert "BEAT_SERVICE_NAME" in out["error"]


# ── Beat 调度器控制信号 ──

def test_control_signals_shutdown_consumed():
    r = _FakeRedis({SHUTDOWN_KEY: "1"})

    assert check_control_signals(r) == "shutdown"
    assert r.data == {}
    assert r.deleted == [SHUTDOWN_KEY]


def test_control_signals_reload_consumed():
    r = _FakeRedis({RELOAD_KEY: "1"})

    assert check_control_signals(r) == "reload"
    assert r.data == {}


def test_control_signals_shutdown_priority():
    r = _FakeRedis({SHUTDOWN_KEY: "1", RELOAD_KEY: "1"})

    assert check_control_signals(r) == "shutdown"
    assert RELOAD_KEY in r.data  # 退出优先，重载键留给新进程


def test_control_signals_none():
    assert check_control_signals(_FakeRedis()) is None


# ── API 层 ──

def test_cron_router_registers_worker_and_beat_paths():
    paths = {r.path for r in api.router.routes}
    assert {
        "/worker/status",
        "/worker/restart",
        "/beat/status",
        "/beat/restart",
    }.issubset(paths)


def test_list_cron_jobs_exposes_saas_mode(session):
    set_setting(session, "saas_mode_enabled", "true")

    resp = api.list_cron_jobs(db=session)

    assert resp["code"] == 200
    assert resp["data"]["saas_mode"] is True
    assert resp["data"]["items"] == []


def test_worker_restart_ok(session, monkeypatch):
    monkeypatch.setattr(api, "request_worker_restart", lambda: {"ok": True, "hosts": ["cenkormes_worker@h"]})

    resp = api.worker_restart_api(db=session)

    assert resp["code"] == 200
    assert resp["data"]["hosts"] == ["cenkormes_worker@h"]


def test_worker_restart_saas_blocked(session, monkeypatch):
    set_setting(session, "saas_mode_enabled", "true")
    called = []
    monkeypatch.setattr(api, "request_worker_restart", lambda: called.append(True))

    with pytest.raises(HTTPException) as exc:
        api.worker_restart_api(db=session)

    assert exc.value.status_code == 403
    assert called == []


def test_worker_restart_failure_maps_503(session, monkeypatch):
    monkeypatch.setattr(api, "request_worker_restart", lambda: {"ok": False, "error": "离线"})

    with pytest.raises(HTTPException) as exc:
        api.worker_restart_api(db=session)

    assert exc.value.status_code == 503
    assert exc.value.detail == "离线"


def test_beat_restart_saas_blocked(session, monkeypatch):
    set_setting(session, "saas_mode_enabled", "true")
    called = []
    monkeypatch.setattr(api, "request_beat_restart", lambda: called.append(True))

    with pytest.raises(HTTPException) as exc:
        api.beat_restart_api(db=session)

    assert exc.value.status_code == 403
    assert called == []


def test_beat_restart_failure_maps_503(session, monkeypatch):
    monkeypatch.setattr(api, "request_beat_restart", lambda: {"ok": False, "error": "单元不存在"})

    with pytest.raises(HTTPException) as exc:
        api.beat_restart_api(db=session)

    assert exc.value.status_code == 503
    assert exc.value.detail == "单元不存在"
