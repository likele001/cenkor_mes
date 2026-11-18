# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""AI 用量计量与配额（services/ai/metering.py）单测。

注意：计量在线上走独立 SessionLocal（业务事务回滚也不丢账），测试里必须用
`record(..., db=session)` 写入测试事务，否则 SQLite 内存库是另一条连接、没有表。
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.ai import PlatformAiQuota, PlatformAiUsage
from app.services.ai import metering


@pytest.fixture(autouse=True)
def _clear_usage_cache():
    """月用量有 30 秒 TTL 缓存，测试之间必须清掉，否则配额判断会串。"""
    metering.invalidate_usage_cache()
    yield
    metering.invalidate_usage_cache()


@pytest.fixture
def core_scope():
    """把计量上下文固定为「核心内置调用」。"""
    t1 = metering.AI_SCOPE.set("core")
    t2 = metering.AI_SCOPE_KEY.set("")
    t3 = metering.AI_PATH.set("/api/ai/assistant/chat")
    yield
    metering.AI_PATH.reset(t3)
    metering.AI_SCOPE_KEY.reset(t2)
    metering.AI_SCOPE.reset(t1)


def _rows(session) -> list[PlatformAiUsage]:
    return list(session.scalars(select(PlatformAiUsage).order_by(PlatformAiUsage.id)).all())


# ── 归属解析 ─────────────────────────────────────────────────────────


def test_split_scope_extension_and_core():
    assert metering.split_scope("/api/extensions/ai_assistant/chat") == ("extension", "ai_assistant")
    assert metering.split_scope("/api/extensions/stock_check/overview") == ("extension", "stock_check")
    assert metering.split_scope("/api/ai/usage/summary") == ("core", "")
    assert metering.split_scope("") == ("core", "")


# ── 记账 ─────────────────────────────────────────────────────────────


def test_record_writes_usage_row(session, core_scope):
    metering.record(source="chat", model_code="deepseek-chat", gateway_code="gw1", tokens_in=120, tokens_out=80, latency_ms=900, db=session)

    rows = _rows(session)
    assert len(rows) == 1
    row = rows[0]
    assert row.scope == "core"
    assert row.scope_key == ""
    assert row.source == "chat"
    assert row.tokens_in == 120
    assert row.tokens_out == 80
    assert row.total_tokens == 200
    assert row.ok is True
    assert row.latency_ms == 900


def test_record_uses_request_scope(session):
    t1 = metering.AI_SCOPE.set("extension")
    t2 = metering.AI_SCOPE_KEY.set("ai_assistant")
    t3 = metering.AI_PATH.set("/api/extensions/ai_assistant/chat")
    try:
        metering.record(source="stream", tokens_in=10, tokens_out=5, db=session)
    finally:
        metering.AI_PATH.reset(t3)
        metering.AI_SCOPE_KEY.reset(t2)
        metering.AI_SCOPE.reset(t1)

    row = _rows(session)[0]
    assert (row.scope, row.scope_key) == ("extension", "ai_assistant")
    assert row.path == "/api/extensions/ai_assistant/chat"


def test_record_swallows_failures(monkeypatch, session, core_scope):
    """计量写失败绝不能把一次正常对话带崩。"""

    class _Boom:
        def __init__(self, *a, **kw):
            raise RuntimeError("db down")

    monkeypatch.setattr(metering, "SessionLocal", _Boom)
    metering.record(source="chat", tokens_in=1, tokens_out=1)  # 不传 db = 走独立会话
    assert _rows(session) == []


def test_record_failed_call_keeps_zero_tokens(session, core_scope):
    metering.record(source="vision", ok=False, error="timeout", db=session)
    row = _rows(session)[0]
    assert row.ok is False
    assert row.error == "timeout"
    assert row.total_tokens == 0


# ── 配额 ─────────────────────────────────────────────────────────────


def _set_quota(session, *, scope="global", scope_key=None, limit=100, policy="block", enabled=True):
    return metering_crud_upsert(
        session, scope=scope, scope_key=scope_key, limit_tokens=limit, policy=policy, enabled=enabled
    )


def metering_crud_upsert(session, **kw):
    from app.crud import ai_platform as crud

    return crud.upsert_ai_quota(session, **kw)


def test_no_quota_means_unlimited(session, core_scope):
    metering.record(source="chat", tokens_in=10_000, tokens_out=10_000, db=session)
    state = metering.check_quota(session)
    assert state["allowed"] is True
    assert state["enforced"] is False
    assert state["limit"] == 0


def test_global_quota_blocks(session, core_scope):
    _set_quota(session, limit=100, policy="block")
    metering.record(source="chat", tokens_in=200, tokens_out=0, db=session)

    state = metering.check_quota(session)
    assert state["allowed"] is False
    assert state["used"] == 200
    assert state["limit"] == 100
    assert state["policy"] == "block"

    from app.services.ai.client import AiQuotaExceededError

    with pytest.raises(AiQuotaExceededError):
        from app.services.ai import client

        client._enforce_quota(session)


def test_global_quota_warn_only_flags(session, core_scope):
    _set_quota(session, limit=100, policy="warn")
    metering.record(source="chat", tokens_in=200, tokens_out=0, db=session)

    from app.services.ai import client

    state = client._enforce_quota(session)
    assert state["over_quota"] is True  # 放行但打标，供成本复盘

    metering.record(source="chat", tokens_in=1, tokens_out=0, over_quota=True, db=session)
    assert _rows(session)[-1].over_quota is True


def test_extension_quota_overrides_global(session):
    _set_quota(session, scope="global", limit=1000, policy="block")
    _set_quota(session, scope="extension", scope_key="ai_assistant", limit=10, policy="block")

    t1 = metering.AI_SCOPE.set("extension")
    t2 = metering.AI_SCOPE_KEY.set("ai_assistant")
    try:
        metering.record(source="chat", tokens_in=50, tokens_out=0, db=session)
        ext_state = metering.check_quota(session)
    finally:
        metering.AI_SCOPE_KEY.reset(t2)
        metering.AI_SCOPE.reset(t1)

    assert ext_state["allowed"] is False
    assert ext_state["limit"] == 10
    assert ext_state["used"] == 50  # 只算这个扩展自己的用量

    # 全局视角仍有余量：别的扩展不该被 ai_assistant 的配额连坐
    global_state = metering.check_quota(session, scope="core", scope_key="")
    assert global_state["allowed"] is True
    assert global_state["used"] == 50
    assert global_state["limit"] == 1000


def test_disabled_quota_is_ignored(session, core_scope):
    _set_quota(session, limit=10, policy="block", enabled=False)
    metering.record(source="chat", tokens_in=100, tokens_out=0, db=session)
    assert metering.check_quota(session)["allowed"] is True


def test_quota_upsert_is_idempotent(session):
    _set_quota(session, limit=100, policy="warn")
    _set_quota(session, limit=500, policy="block")
    rows = list(session.scalars(select(PlatformAiQuota).where(PlatformAiQuota.scope == "global")).all())
    assert len(rows) == 1
    assert rows[0].limit_tokens == 500
    assert rows[0].policy == "block"


def test_quota_message_mentions_extension(session):
    state = {"scope_key": "ai_assistant", "used": 120, "limit": 100}
    msg = metering.quota_exceeded_message(state)
    assert "ai_assistant" in msg
    assert "120" in msg and "100" in msg


# ── 汇总 ─────────────────────────────────────────────────────────────


def test_summary_groups_by_scope_and_source(session):
    t1 = metering.AI_SCOPE.set("extension")
    t2 = metering.AI_SCOPE_KEY.set("ai_assistant")
    try:
        metering.record(source="chat", tokens_in=100, tokens_out=50, db=session)
        metering.record(source="stream", tokens_in=50, tokens_out=50, db=session)
    finally:
        metering.AI_SCOPE_KEY.reset(t2)
        metering.AI_SCOPE.reset(t1)

    t3 = metering.AI_SCOPE.set("core")
    metering.AI_SCOPE_KEY.set("")
    try:
        metering.record(source="chat", tokens_in=10, tokens_out=10, db=session)
    finally:
        metering.AI_SCOPE.reset(t3)

    data = metering.summary(session, days=7)
    assert data["totals"]["calls"] == 3
    assert data["totals"]["tokens"] == 270
    by_scope = {item["key"]: item for item in data["by_scope"]}
    assert by_scope["ai_assistant"]["tokens"] == 250
    assert by_scope[""]["tokens"] == 20
    by_source = {item["source"]: item for item in data["by_source"]}
    assert by_source["stream"]["calls"] == 1


def test_recent_returns_newest_first(session, core_scope):
    metering.record(source="chat", tokens_in=1, db=session)
    metering.record(source="chat", tokens_in=2, db=session)
    rows = metering.recent(session, limit=10)
    assert rows[0]["tokens_in"] == 2
    assert len(rows) == 2


def test_month_usage_counts_only_current_month(session, core_scope):
    metering.record(source="chat", tokens_in=100, tokens_out=0, db=session)
    # 手工塞一条上个月的行，验证月口径
    from datetime import datetime

    from datetime import timedelta

    old = PlatformAiUsage(
        created_at=metering.month_start() - timedelta(seconds=1),
        scope="core",
        scope_key="",
        source="chat",
        tokens_in=999,
        tokens_out=0,
        total_tokens=999,
    )
    session.add(old)
    session.flush()
    metering.invalidate_usage_cache()

    used = metering.month_usage(session)
    assert used == 100
    assert session.scalar(select(func.count(PlatformAiUsage.id))) == 2
