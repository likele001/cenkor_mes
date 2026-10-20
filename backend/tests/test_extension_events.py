# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展事件总线测试：订阅/分发/after_commit 时机/gating/拦截 fail-open/loader 接线。

线程 × SQLite 内存库注意：conftest 的内存库对总线工作线程不可见，
因此跨线程只断言「事件送达 + payload 正确」（handler 里 append 到 list），
不跨线程断言 DB 内容；open_session 的 DB 行为在同线程单独测。
after_commit 时机用自建的真 commit 独立引擎验证（conftest session 永远在
外层事务里回滚，after_commit 不触发——见 test_notify_admin_api.py 注释）。
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.extension_host import host as ext_host
from app.extension_host.events import (
    EVENT_CATALOG,
    InterceptDecision,
    Phase,
    event_bus,
)
from app.extension_host.loader import load_extension_router, mount_extensions
from app.extension_host.state import runtime


@pytest.fixture(autouse=True)
def _isolate_runtime():
    """runtime.reset() 联动清空总线订阅（见 state.py）。"""
    runtime.reset()
    yield
    runtime.reset()


def _fake_install(*keys: str) -> None:
    """把 key 塞进 registry 以通过分发 gating（is_enabled 要求已安装）。"""
    for key in keys:
        runtime.installed[key] = {"manifest": None, "path": "."}


def _write_hook_ext(base: Path, key: str = "hook_ext", register_body: str = "") -> Path:
    """生成一个带 register_events 的最小扩展；RECEIVED 列表经 sys.modules 取回断言。"""
    ext = base / key
    ext.mkdir(parents=True, exist_ok=True)
    (ext / "manifest.json").write_text(
        json.dumps({"key": key, "name": f"钩子扩展 {key}", "version": "1.0.0"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (ext / "router.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.get('/ping')\n"
        "def ping():\n"
        "    return {'ok': True}\n\n"
        "RECEIVED = []\n\n"
        "def register_events(bus):\n"
        f"{register_body or ('    bus.subscribe(%r, %r, RECEIVED.append)' % (key, 'report.submitted'))}\n",
        encoding="utf-8",
    )
    return ext


# ── 1. 订阅 → emit_now 送达 ──


def test_subscribe_emit_now():
    _fake_install("ext_a")
    received = []
    event_bus.subscribe("ext_a", "report.submitted", received.append)

    event_bus.emit_now("report.submitted", {"report_id": 7, "good_qty": 3}, actor_id=9)
    assert event_bus.wait_pending(2)

    assert len(received) == 1
    ev = received[0]
    assert ev.name == "report.submitted"
    assert ev.phase == Phase.NOTIFY
    assert ev.payload == {"report_id": 7, "good_qty": 3}
    assert ev.actor_id == 9
    assert ev.occurred_at


# ── 2. after_commit 时机（真 commit 独立引擎）──


def test_emit_after_commit_timing():
    _fake_install("ext_a")
    received = []
    event_bus.subscribe("ext_a", "order.confirmed", received.append)

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    db = Session()
    db.execute(text("CREATE TABLE evt_t (id INTEGER PRIMARY KEY)"))
    db.commit()

    # 事务内：emit 后不分发
    db.execute(text("INSERT INTO evt_t (id) VALUES (1)"))
    event_bus.emit_after_commit(db, "order.confirmed", {"order_id": 1})
    event_bus.wait_pending(0.3)
    assert received == []

    # commit 后恰分发一次
    db.commit()
    assert event_bus.wait_pending(2)
    assert len(received) == 1

    # rollback：不发
    db.execute(text("INSERT INTO evt_t (id) VALUES (2)"))
    event_bus.emit_after_commit(db, "order.confirmed", {"order_id": 2})
    db.rollback()
    event_bus.wait_pending(0.3)
    assert len(received) == 1

    # 无事务上下文（已 commit）：立即分发
    event_bus.emit_after_commit(db, "order.confirmed", {"order_id": 3})
    assert event_bus.wait_pending(2)
    assert len(received) == 2
    db.close()


# ── 3. handler 异常完全隔离 ──


def test_notify_handler_error_isolated(caplog):
    _fake_install("ext_bad", "ext_ok")
    received = []

    def bad_handler(ev):
        raise RuntimeError("扩展炸了")

    event_bus.subscribe("ext_bad", "report.submitted", bad_handler)
    event_bus.subscribe("ext_ok", "report.submitted", received.append)

    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        event_bus.emit_now("report.submitted", {"report_id": 1})  # 不上抛
        assert event_bus.wait_pending(2)

    assert len(received) == 1
    assert "扩展炸了" in caplog.text or "handler 失败" in caplog.text


# ── 4. 禁用扩展分发时跳过（gating 即时生效）──


def test_disabled_extension_skipped():
    _fake_install("ext_a")
    received = []
    event_bus.subscribe("ext_a", "report.submitted", received.append)

    runtime.set_override("ext_a", "disabled")
    event_bus.emit_now("report.submitted", {"report_id": 1})
    event_bus.wait_pending(0.3)
    assert received == []

    runtime.set_override("ext_a", None)
    event_bus.emit_now("report.submitted", {"report_id": 2})
    assert event_bus.wait_pending(2)
    assert len(received) == 1


# ── 5. 反注册计数 + 同 handler 幂等去重 ──


def test_unsubscribe_and_dedupe():
    _fake_install("ext_a")
    received = []
    event_bus.subscribe("ext_a", "report.submitted", received.append)
    event_bus.subscribe("ext_a", "report.submitted", received.append)  # 重复注册同一 handler
    event_bus.subscribe("ext_a", "order.created", received.append)

    event_bus.emit_now("report.submitted", {"report_id": 1})
    assert event_bus.wait_pending(2)
    assert len(received) == 1  # 去重生效

    assert event_bus.unsubscribe_extension("ext_a") == 2
    assert event_bus.unsubscribe_extension("ext_a") == 0


# ── 6. 拦截：无订阅/全放行 ──


def test_intercept_allow_by_default():
    result = event_bus.intercept("report.submitting", {"report_id": 1})
    assert result.allowed is True
    assert result.rejections == []

    _fake_install("ext_a")
    event_bus.subscribe_intercept("ext_a", "report.submitting", lambda ev: None)
    event_bus.subscribe_intercept(
        "ext_a", "report.submitting", lambda ev: InterceptDecision(allow=True)
    )
    result = event_bus.intercept("report.submitting", {"report_id": 1})
    assert result.allowed is True


# ── 7. 拦截：多扩展否决合并（不短路）──


def test_intercept_reject_merges_reasons():
    _fake_install("quality_guard", "hr_ext")
    calls = []

    def reject_a(ev):
        calls.append("a")
        return InterceptDecision(allow=False, reason="今日不良率超阈值")

    def reject_b(ev):
        calls.append("b")
        return InterceptDecision(allow=False, reason="未完成安全培训")

    event_bus.subscribe_intercept("quality_guard", "report.submitting", reject_a)
    event_bus.subscribe_intercept("hr_ext", "report.submitting", reject_b)

    result = event_bus.intercept("report.submitting", {"report_id": 1})
    assert result.allowed is False
    assert calls == ["a", "b"]  # 全部跑完，不短路
    assert len(result.rejections) == 2
    detail = result.http_detail()
    assert "quality_guard" in detail and "今日不良率超阈值" in detail
    assert "hr_ext" in detail and "未完成安全培训" in detail


# ── 8. 拦截 fail-open：handler 异常放行 ──


def test_intercept_fail_open_on_exception(caplog):
    _fake_install("ext_bad")

    def boom(ev):
        raise ValueError("扩展内部错误")

    event_bus.subscribe_intercept("ext_bad", "report.submitting", boom)
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        result = event_bus.intercept("report.submitting", {"report_id": 1})

    assert result.allowed is True
    assert len(result.errors) == 1
    assert result.errors[0][0] == "ext_bad"
    assert "扩展内部错误" in result.errors[0][1]


# ── 9. 拦截 fail-open：超时放行且不阻塞 ──


def test_intercept_timeout_fail_open():
    _fake_install("ext_slow")
    event_bus.subscribe_intercept(
        "ext_slow", "report.submitting", lambda ev: time.sleep(1.5), timeout=0.1
    )

    started = time.monotonic()
    result = event_bus.intercept("report.submitting", {"report_id": 1})
    elapsed = time.monotonic() - started

    assert result.allowed is True
    assert any("超时" in err for _, err in result.errors)
    assert elapsed < 1.0  # 不被慢 handler 拖住


# ── 10. loader 接线：register_events 被调 + 热重载不双份订阅 ──


def test_loader_wires_register_events(tmp_path: Path):
    _write_hook_ext(tmp_path)
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])

    mod = sys.modules["cenkormes_ext_hook_ext"]
    event_bus.emit_now("report.submitted", {"report_id": 1})
    assert event_bus.wait_pending(2)
    assert len(mod.RECEIVED) == 1

    # 二次加载（热重载）：unsubscribe-first，不产生双份 handler
    load_extension_router(tmp_path / "hook_ext", "hook_ext")
    mod2 = sys.modules["cenkormes_ext_hook_ext"]
    event_bus.emit_now("report.submitted", {"report_id": 2})
    assert event_bus.wait_pending(2)
    assert len(mod2.RECEIVED) == 1
    assert event_bus.unsubscribe_extension("hook_ext") == 1


# ── 11. register_events 抛异常：路由不受影响 ──


def test_register_events_failure_does_not_break_mount(tmp_path: Path, caplog):
    _write_hook_ext(tmp_path, key="bad_hook", register_body="    raise RuntimeError('注册即炸')")
    app = FastAPI()
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        mount_extensions(app, tmp_path, auth_dependencies=[])
    client = TestClient(app)

    assert client.get("/api/extensions/bad_hook/ping").status_code == 200
    assert "register_events 失败" in caplog.text


# ── 12. 热卸载反注册 ──


def test_hot_teardown_unsubscribes(tmp_path: Path):
    _write_hook_ext(tmp_path)
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])
    mod = sys.modules["cenkormes_ext_hook_ext"]

    ext_host.hot_teardown_extension(app, "hook_ext")
    # registry 未清（teardown 只摘路由与钩子），若仍收到说明反注册失败
    assert "hook_ext" in runtime.installed
    event_bus.emit_now("report.submitted", {"report_id": 1})
    event_bus.wait_pending(0.3)
    assert mod.RECEIVED == []


# ── 13. runtime.reset() 连带清总线 + open_session 同线程可用 ──


def test_runtime_reset_clears_bus():
    _fake_install("ext_a")
    event_bus.subscribe("ext_a", "report.submitted", lambda ev: None)
    assert event_bus._snapshot("report.submitted", Phase.NOTIFY)

    runtime.reset()
    assert event_bus._snapshot("report.submitted", Phase.NOTIFY) == []


def test_open_session_same_thread(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
        db.commit()
    monkeypatch.setattr(event_bus, "session_factory", Session)

    with event_bus.open_session() as db:
        db.execute(text("INSERT INTO t (id) VALUES (1)"))
        db.commit()
        assert db.execute(text("SELECT COUNT(*) FROM t")).scalar() == 1


def test_event_catalog_shape():
    """契约表自检：拦截型只开报工两条路径；通知型覆盖闭环 + qcode 扩展动态注册。"""
    intercepts = {n for n, v in EVENT_CATALOG.items() if v["phase"] == Phase.INTERCEPT}
    assert intercepts == {"report.submitting", "report_unit.submitting"}
    assert len(EVENT_CATALOG) == 28
    for v in EVENT_CATALOG.values():
        assert v["payload"], "每个事件必须声明 payload 字段契约"


# ── 14-24. 事件钩子可视化：EventRecorder + 4 个管理端点 ──

from app.extension_host.events import event_recorder  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_recorder():
    """每个用例前后清空环形缓冲，避免相互污染。"""
    event_recorder.reset()
    yield
    event_recorder.reset()


def test_recorder_records_notify():
    """通知型 handler 正常返回 → 记录 ok=True, allowed=None。"""
    _fake_install("ext_a")
    event_bus.subscribe("ext_a", "report.submitted", lambda ev: None)
    event_bus.emit_now("report.submitted", {"report_id": 1}, actor_id=7)
    assert event_bus.wait_pending(2)

    records = event_recorder.snapshot()
    assert len(records) == 1
    r = records[0]
    assert r.event_name == "report.submitted"
    assert r.ext_key == "ext_a"
    assert r.phase == "notify"
    assert r.ok is True
    assert r.allowed is None
    assert r.error == ""
    assert r.actor_id == 7


def test_recorder_records_intercept_rejection():
    """拦截 handler 返回 allow=False → 记录 allowed=False + reason。"""
    _fake_install("guard")
    event_bus.subscribe_intercept(
        "guard", "report.submitting",
        lambda ev: InterceptDecision(allow=False, reason="不良率超阈值"),
    )
    result = event_bus.intercept("report.submitting", {"report_id": 1})
    assert result.allowed is False

    records = event_recorder.snapshot()
    assert len(records) == 1
    r = records[0]
    assert r.phase == "intercept"
    assert r.ok is True
    assert r.allowed is False
    assert r.reason == "不良率超阈值"


def test_recorder_records_handler_error():
    """通知型 handler 抛异常 → 记录 ok=False + error 非空。"""
    _fake_install("ext_bad")

    def boom(ev):
        raise RuntimeError("扩展炸了")

    event_bus.subscribe("ext_bad", "report.submitted", boom)
    event_bus.emit_now("report.submitted", {"report_id": 1})
    assert event_bus.wait_pending(2)

    records = event_recorder.snapshot()
    assert len(records) == 1
    r = records[0]
    assert r.ok is False
    assert "扩展炸了" in r.error


def test_recorder_capacity():
    """环形缓冲 200 上限：塞 250 条只保留最新 200 条。"""
    _fake_install("ext_a")
    event_bus.subscribe("ext_a", "report.submitted", lambda ev: None)
    for i in range(250):
        event_bus.emit_now("report.submitted", {"report_id": i})
    assert event_bus.wait_pending(5)

    records = event_recorder.snapshot(limit=300)
    assert len(records) == 200
    # 最新在前：第一条应是 report_id=249
    assert records[0].event_name == "report.submitted"
    assert records[0].seq >= records[-1].seq


def test_recorder_stats_aggregation():
    """按 (event, ext) 聚合：total / errors / rejections 计数正确。"""
    _fake_install("ext_a", "ext_b")

    def ok_handler(ev):
        return None

    def bad_handler(ev):
        raise ValueError("boom")

    def reject_handler(ev):
        return InterceptDecision(allow=False, reason="no")

    event_bus.subscribe("ext_a", "report.submitted", ok_handler)
    event_bus.subscribe("ext_b", "report.submitted", bad_handler)
    event_bus.subscribe_intercept("ext_a", "report.submitting", reject_handler)

    for _ in range(3):
        event_bus.emit_now("report.submitted", {"report_id": 1})
    event_bus.intercept("report.submitting", {"report_id": 1})
    assert event_bus.wait_pending(3)

    stats = event_recorder.stats()
    a_key = "report.submitted|ext_a"
    b_key = "report.submitted|ext_b"
    rej_key = "report.submitting|ext_a"
    assert stats[a_key]["total"] == 3
    assert stats[a_key]["errors"] == 0
    assert stats[b_key]["total"] == 3
    assert stats[b_key]["errors"] == 3
    assert stats[rej_key]["rejections"] == 1


def test_snapshot_subscriptions():
    """snapshot_subscriptions 枚举全部订阅，含 in_catalog 标记。"""
    _fake_install("ext_a")
    event_bus.subscribe("ext_a", "report.submitted", lambda ev: None)
    event_bus.subscribe_intercept("ext_a", "report.submitting", lambda ev: None, timeout=2.5)
    event_bus.subscribe("ext_a", "custom.unknown_event", lambda ev: None)

    subs = event_bus.snapshot_subscriptions()
    assert len(subs) == 3
    by_event = {s["event_name"]: s for s in subs}
    assert by_event["report.submitted"]["phase"] == "notify"
    assert by_event["report.submitted"]["in_catalog"] is True
    assert by_event["report.submitting"]["phase"] == "intercept"
    assert by_event["report.submitting"]["timeout"] == 2.5
    assert by_event["custom.unknown_event"]["in_catalog"] is False


def _build_admin_app(perms: list[str] | None = None):
    """构造一个挂载 extensions router 的最小 FastAPI 应用。

    通过 dependency_overrides 把 get_current_permissions 替换为返回指定权限码的
    no-op，绕过真实鉴权；默认给 setting.manage 以通过 4 个 /events/* 端点的权限闸。
    """
    from app.api.admin.extensions.router import router as ext_router
    from app.core.deps import get_current_permissions

    app = FastAPI()
    app.include_router(ext_router, prefix="/admin/extensions")
    codes = perms if perms is not None else ["setting.manage"]
    app.dependency_overrides[get_current_permissions] = lambda: codes
    return app


def test_catalog_endpoint():
    app = _build_admin_app()
    client = TestClient(app)
    resp = client.get("/admin/extensions/events/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    items = body["data"]["items"]
    assert "report.submitted" in items
    assert items["report.submitted"]["phase"] == "notify"
    assert "report.submitting" in items
    assert items["report.submitting"]["phase"] == "intercept"


def test_subscriptions_endpoint():
    _fake_install("ext_a")
    # 给 manifest 塞一个有 name 的对象以便断言 extension_name
    class _M:
        name = "扩展 A"

    runtime.installed["ext_a"]["manifest"] = _M()
    event_bus.subscribe("ext_a", "report.submitted", lambda ev: None)

    app = _build_admin_app()
    client = TestClient(app)
    resp = client.get("/admin/extensions/events/subscriptions")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    s = items[0]
    assert s["event_name"] == "report.submitted"
    assert s["key"] == "ext_a"
    assert s["extension_name"] == "扩展 A"
    assert s["enabled"] is True


def test_recent_endpoint_filters():
    _fake_install("ext_a")
    event_bus.subscribe("ext_a", "report.submitted", lambda ev: None)
    event_bus.subscribe_intercept("ext_a", "report.submitting", lambda ev: None)
    event_bus.emit_now("report.submitted", {"report_id": 1})
    assert event_bus.wait_pending(2)
    event_bus.intercept("report.submitting", {"report_id": 2})

    app = _build_admin_app()
    client = TestClient(app)

    all_resp = client.get("/admin/extensions/events/recent")
    assert all_resp.status_code == 200
    all_items = all_resp.json()["data"]["items"]
    assert len(all_items) == 2

    intercept_only = client.get("/admin/extensions/events/recent?phase=intercept")
    items = intercept_only.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["phase"] == "intercept"

    by_event = client.get("/admin/extensions/events/recent?event_name=report.submitted")
    items = by_event.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["event_name"] == "report.submitted"


def test_stats_endpoint():
    _fake_install("ext_a")
    event_bus.subscribe("ext_a", "report.submitted", lambda ev: None)
    event_bus.emit_now("report.submitted", {"report_id": 1})
    assert event_bus.wait_pending(2)

    app = _build_admin_app()
    client = TestClient(app)
    resp = client.get("/admin/extensions/events/stats")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["event_name"] == "report.submitted"
    assert items[0]["ext_key"] == "ext_a"
    assert items[0]["total"] == 1
    assert items[0]["errors"] == 0


def test_permission_required():
    """无 setting.manage 权限 → 4 个 /events/* 端点全部 403。"""
    app = _build_admin_app(perms=["order.query"])  # 不含 setting.manage
    client = TestClient(app)
    for path in ("/events/catalog", "/events/subscriptions", "/events/recent", "/events/stats"):
        resp = client.get(f"/admin/extensions{path}")
        assert resp.status_code == 403, f"{path} 应 403，实际 {resp.status_code}"
