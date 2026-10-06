# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""看板 WebSocket 生产者链路（P1.3）

覆盖三段此前完全不存在的链路：
  1. Session 级监听把「看板表被提交」变成刷新事件（app/services/dashboard_events.py）
  2. 事件从同步线程经 run_coroutine_threadsafe 投回事件循环（ws_hub.publish）
  3. 连续提交在合并窗口内只推一次，且最后一次改动不会被吞掉
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.dashboard_events as de
from app.models.order import Order, OrderItem
from app.models.report import Report
from app.models.salary import SalaryItem
from app.models.task import Task
from app.models.user import User
from app.services.ws_hub import DashboardWSHub, dashboard_ws_hub


class FakeWS:
    """只实现 hub 用到的那几个方法。"""

    def __init__(self) -> None:
        self.accepted = False
        self.received: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        self.received.append(json.loads(text))

    async def close(self, *args, **kwargs) -> None:
        pass


@pytest.fixture
def hub():
    """在后台线程跑一个真实事件循环，模拟 uvicorn 的运行环境。"""
    hub = DashboardWSHub()
    loop = asyncio.new_event_loop()

    def _runner() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    try:
        yield hub, loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=2)
        loop.close()


def _run(loop, coro, timeout: float = 2.0):
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout)


def _settle(loop, seconds: float = 0.3) -> None:
    _run(loop, asyncio.sleep(seconds))


# ---------------------------------------------------------------- 1. 表 → channel

def test_watched_models_collect_channels(session: Session):
    """看板读的表：改到哪块就推哪块。"""
    session.add(Report(task_id=1, report_user_id=1, good_qty=5, bad_qty=1, status="submitted"))
    session.add(Order(id=9001, customer_id=1, code="SO-WS-1", status="producing"))
    session.add(Task(id=9002, work_order_id=1, task_code="T-WS-1", status="pending"))
    session.add(SalaryItem(id=9003, user_id=1, amount=100))

    de.record_dirty_channels(session)
    assert de.changed_channels(session) == {"reports", "orders", "tasks", "salary"}


def test_unwatched_model_collects_nothing(session: Session):
    """与看板无关的表不该触发大屏重载。"""
    session.add(User(id=9004, username="ws-irrelevant", full_name="无关", password_hash="x", is_active=True))
    session.add(OrderItem(id=9005, order_id=9001, line_no=1, sku_id=1, qty=1))

    de.record_dirty_channels(session)
    # OrderItem 在看板订单列表里（单价/小计），User 不在
    assert de.changed_channels(session) == {"orders"}


def test_record_accumulates_across_flushes(session: Session):
    """同一事务里先报工后建单：两次 flush 的 channel 要累积，不能只留第一条。"""
    session.add(Report(task_id=1, report_user_id=1, good_qty=1, bad_qty=0, status="submitted"))
    de.record_dirty_channels(session)
    session.add(Task(id=9006, work_order_id=1, task_code="T-WS-2", status="pending"))
    de.record_dirty_channels(session)

    assert de.changed_channels(session) == {"reports", "tasks"}


# ------------------------------------------------------- 2/3. commit → 投递

def test_commit_publishes_refresh(session: Session, monkeypatch):
    """真实 commit 才会推：监听器注册在 Session 类上，覆盖所有写入点。"""
    seen: list[tuple[frozenset, str]] = []
    monkeypatch.setattr(
        dashboard_ws_hub,
        "publish_refresh",
        lambda channels, *, reason="": (seen.append((frozenset(channels), reason)), True)[1],
    )

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Report.__table__.create(eng)
    db = sessionmaker(bind=eng)()
    try:
        db.add(Report(task_id=1, report_user_id=1, good_qty=3, bad_qty=0, status="submitted"))
        db.commit()
        assert seen and seen[0][0] == {"reports"}
        assert seen[0][1] == "commit"

        # 没有看板表变更的 commit 不该推
        db.commit()
        assert len(seen) == 1
    finally:
        db.close()
        eng.dispose()


def test_rollback_discards_pending_channels(session: Session, monkeypatch):
    """回滚后不该再补推一次刷新。"""
    calls: list[frozenset] = []
    monkeypatch.setattr(
        dashboard_ws_hub,
        "publish_refresh",
        lambda channels, *, reason="": calls.append(frozenset(channels)) or True,
    )

    session.add(Report(task_id=1, report_user_id=1, good_qty=1, bad_qty=0, status="submitted"))
    de._on_before_flush(session, None, None)
    assert de.changed_channels(session) == {"reports"}

    de._on_after_rollback(session)
    assert de.changed_channels(session) == set()
    assert de.flush_refresh(session) is False
    assert calls == []


# ----------------------------------------------------------- hub 投递与合并

def test_publish_from_sync_thread_reaches_client(hub):
    """同步代码（线程池里的端点）投递的刷新事件，必须落到事件循环里的连接上。"""
    ws_hub, loop = hub
    client = FakeWS()
    _run(loop, ws_hub.connect(client))
    assert client.accepted

    flushed = ws_hub.publish_refresh({"reports"}, reason="commit")
    assert flushed is True
    _settle(loop)

    assert len(client.received) == 1
    msg = client.received[0]
    assert msg["type"] == "refresh"
    assert msg["channel"] == "dashboard"
    assert msg["changed"] == ["reports"]
    assert msg["reason"] == "commit"


def test_publish_without_clients_is_silent(hub):
    ws_hub, loop = hub
    assert ws_hub.publish_refresh({"orders"}) is False
    _settle(loop, 0.1)
    assert ws_hub.client_count == 0


def test_coalesce_window_merges_and_still_flushes(hub):
    """窗口内多次提交只推一次，且最后那次变更必须在补发时被看到。"""
    ws_hub, loop = hub
    client = FakeWS()
    _run(loop, ws_hub.connect(client))

    assert ws_hub.publish_refresh({"reports"}, reason="commit") is True
    ws_hub.publish_refresh({"tasks"}, reason="commit")     # 落在合并窗口内
    ws_hub.publish_refresh({"salary"}, reason="commit")
    _settle(loop, 0.1)
    assert len(client.received) == 1, "窗口内的重复提交不该各推一次"
    assert ws_hub._flush_handle is not None, "必须挂上补发，否则最后一次改动大屏看不到"

    ws_hub.publish_refresh_scheduled()
    _settle(loop)

    assert len(client.received) == 2
    assert client.received[1]["changed"] == ["salary", "tasks"]
    assert ws_hub._flush_handle is None


def test_stale_handle_does_not_swallow_refresh(hub):
    """旧 handle 属于已关闭的 loop 时必须重挂，否则积压的 channel 永远发不出去。"""
    ws_hub, loop = hub
    client = FakeWS()
    _run(loop, ws_hub.connect(client))

    ws_hub._pending_channels.add("tasks")          # 上一个 loop 死掉时没发出去的
    ws_hub._last_flush_at = time.monotonic()       # 仍处在合并窗口内
    ws_hub._flush_handle = object()                # 属于已关闭 loop 的僵尸 handle

    assert ws_hub.publish_refresh({"orders"}) is False
    assert isinstance(ws_hub._flush_handle, asyncio.TimerHandle)

    ws_hub.publish_refresh_scheduled()
    _settle(loop)
    assert client.received[-1]["changed"] == ["orders", "tasks"]


def test_dead_socket_is_dropped(hub):
    ws_hub, loop = hub
    bad = FakeWS()

    async def _boom_send(_text):
        raise RuntimeError("client gone")

    _run(loop, ws_hub.connect(bad))
    bad.send_text = _boom_send

    ws_hub.publish_refresh({"orders"})
    _settle(loop)
    assert ws_hub.client_count == 0


def test_refresh_payload_matches_frontend_contract(hub):
    """前端只认 type === 'refresh'（utils/ws.ts），改名等于把这条链路又弄断。"""
    ws_hub, loop = hub
    client = FakeWS()
    _run(loop, ws_hub.connect(client))
    ws_hub.publish_refresh({"orders"})
    _settle(loop)
    assert client.received and client.received[0]["type"] == "refresh"
