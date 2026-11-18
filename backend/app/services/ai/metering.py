# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""AI 用量计量与按月配额（单租户）。

为什么需要这一层
----------------
AI 能力在 cenkormes 里是以「付费扩展」为单位卖的：客户买一个 license，AI 想用多少
用多少。但 LLM 的 token 成本是按次计费的，license 收入固定、成本随用量线性上升，
卖得越好亏得越多。所以必须在调用边界上记一次账，并且能按「扩展 / 模型 / 天」聚合，
才能回答三个问题：哪个扩展在烧钱、这个月烧了多少、要不要在超配额时拦下来。

三层职责
--------
1. 归属（attribution）：中间件把请求路径解析成 (scope, scope_key) 写进 contextvar，
   核心内置调用记 ``core``，``/api/extensions/<key>/...`` 记该扩展 key。服务层只读
   contextvar，不依赖调用方显式传参——45 个扩展不必逐个改造。
2. 记账（record）：独立事务落 ``platform_ai_usage``，**不跟随业务事务回滚**，
   且任何异常都被吞掉，绝不让计量失败拖垮一次正常对话。
3. 配额（check_quota）：按自然月汇总，extension 级配额优先于 global；
   ``policy=block`` 由 client 抛 ``AiQuotaExceededError``，``warn`` 只打标放行。

缓存
----
配额检查在同一次对话里会被调多轮（tool-calling 每轮一次），所以「本月已用量」
按 (scope_key, 月份) 做 30 秒 TTL 缓存；配额变更与记账都会失效缓存。
"""
from __future__ import annotations

import logging
import threading
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.ai import PlatformAiQuota, PlatformAiUsage

logger = logging.getLogger("app.ai.metering")

# ── 归属上下文（由 AiUsageContextMiddleware 写入）──────────────────────

AI_SCOPE: ContextVar[str] = ContextVar("ai_scope", default="core")
AI_SCOPE_KEY: ContextVar[str] = ContextVar("ai_scope_key", default="")
AI_PATH: ContextVar[str] = ContextVar("ai_path", default="")

_USAGE_CACHE_TTL = 30.0
_usage_cache: dict[tuple[str, str], tuple[float, int]] = {}
_cache_lock = threading.Lock()


def split_scope(path: str) -> tuple[str, str]:
    """把请求路径解析成 (scope, scope_key)。

    ``/api/extensions/ai_assistant/chat`` → ("extension", "ai_assistant")
    其余（``/api/ai/...``、``/api/h5/...``）→ ("core", "")
    """
    parts = [p for p in (path or "").split("/") if p]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "extensions":
        return "extension", parts[2]
    return "core", ""


class AiUsageContextMiddleware:
    """纯 ASGI 中间件：把请求路径折算成计量归属，供服务层读取。"""

    def __init__(self, app) -> None:  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        scope_name, scope_key = split_scope(path)
        t1 = AI_SCOPE.set(scope_name)
        t2 = AI_SCOPE_KEY.set(scope_key)
        t3 = AI_PATH.set(path)
        try:
            await self.app(scope, receive, send)
        finally:
            AI_SCOPE.reset(t1)
            AI_SCOPE_KEY.reset(t2)
            AI_PATH.reset(t3)


def current_scope() -> tuple[str, str]:
    return AI_SCOPE.get(), AI_SCOPE_KEY.get()


def _request_id() -> str | None:
    try:
        from app.core.observability import REQUEST_ID

        value = REQUEST_ID.get()
        return None if value in (None, "", "-") else str(value)
    except Exception:  # noqa: BLE001 - 观测层缺失不该影响记账
        return None


# ── 记账 ─────────────────────────────────────────────────────────────


def record(
    *,
    source: str,
    model_code: str | None = None,
    gateway_code: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: int | None = None,
    ok: bool = True,
    error: str | None = None,
    over_quota: bool = False,
    db: Session | None = None,
) -> None:
    """记一条用量流水。绝不抛异常：计量失败不能影响业务链路。

    ``db`` 仅用于测试（写入调用方事务）；生产路径一律走独立 SessionLocal 并自行提交，
    这样业务事务回滚也不会丢账。
    """
    scope, scope_key = current_scope()
    tin = int(tokens_in or 0)
    tout = int(tokens_out or 0)
    row = PlatformAiUsage(
        created_at=datetime.now(),
        scope=scope,
        scope_key=scope_key,
        source=(source or "chat")[:16],
        model_code=(model_code or None) and str(model_code)[:64],
        gateway_code=(gateway_code or None) and str(gateway_code)[:64],
        tokens_in=tin,
        tokens_out=tout,
        total_tokens=tin + tout,
        latency_ms=latency_ms,
        ok=bool(ok),
        error=(error or None) and str(error)[:200],
        over_quota=bool(over_quota),
        request_id=_request_id(),
        path=(AI_PATH.get() or None) and str(AI_PATH.get())[:200],
    )
    try:
        if db is not None:
            db.add(row)
            db.flush()
        else:
            session = SessionLocal()
            try:
                session.add(row)
                session.commit()
            finally:
                session.close()
        invalidate_usage_cache()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_usage_record_failed: %s", exc)


def invalidate_usage_cache() -> None:
    with _cache_lock:
        _usage_cache.clear()


# ── 配额 ─────────────────────────────────────────────────────────────


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    return datetime(now.year, now.month, 1)


def _effective_quota(db: Session, scope: str, scope_key: str) -> tuple[PlatformAiQuota | None, bool]:
    """返回 (生效配额, 是否按全量统计)。

    扩展配额优先；没有则回落到 global（此时统计口径为全部调用）。
    """
    if scope == "extension" and scope_key:
        row = db.scalar(
            select(PlatformAiQuota).where(
                PlatformAiQuota.scope == "extension",
                PlatformAiQuota.scope_key == scope_key,
                PlatformAiQuota.enabled.is_(True),
            )
        )
        if row and int(row.limit_tokens or 0) > 0:
            return row, False
    row = db.scalar(
        select(PlatformAiQuota).where(
            PlatformAiQuota.scope == "global",
            PlatformAiQuota.scope_key == "",
            PlatformAiQuota.enabled.is_(True),
        )
    )
    if row and int(row.limit_tokens or 0) > 0:
        return row, True
    return None, True


def month_usage(db: Session, *, scope: str | None = None, scope_key: str | None = None) -> int:
    """本月已用 token（带 30 秒缓存）。给 scope_key 时只统计该扩展。"""
    cache_key = (scope_key or "*", month_start().strftime("%Y-%m"))
    with _cache_lock:
        hit = _usage_cache.get(cache_key)
        if hit and (time.monotonic() - hit[0]) < _USAGE_CACHE_TTL:
            return hit[1]

    stmt = select(func.coalesce(func.sum(PlatformAiUsage.total_tokens), 0)).where(
        PlatformAiUsage.created_at >= month_start()
    )
    if scope_key:
        stmt = stmt.where(PlatformAiUsage.scope_key == scope_key)
    if scope:
        stmt = stmt.where(PlatformAiUsage.scope == scope)
    used = int(db.scalar(stmt) or 0)

    with _cache_lock:
        _usage_cache[cache_key] = (time.monotonic(), used)
    return used


def check_quota(db: Session, *, scope: str | None = None, scope_key: str | None = None) -> dict[str, Any]:
    """计算当前调用是否还能继续。

    allowed=False 时由 client 决定抛错（policy=block），或仅打标放行（policy=warn）。
    """
    scope = scope or AI_SCOPE.get()
    scope_key = scope_key if scope_key is not None else AI_SCOPE_KEY.get()

    quota, count_all = _effective_quota(db, scope, scope_key)
    if not quota:
        used = month_usage(db, scope_key=scope_key if scope == "extension" else None)
        return {
            "scope": scope,
            "scope_key": scope_key,
            "used": used,
            "limit": 0,
            "remaining": -1,
            "policy": "none",
            "allowed": True,
            "enforced": False,
        }

    used = month_usage(db, scope_key=None if count_all else scope_key)
    limit = int(quota.limit_tokens or 0)
    remaining = max(0, limit - used)
    return {
        "scope": quota.scope,
        "scope_key": quota.scope_key,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "policy": quota.policy or "warn",
        "allowed": used < limit,
        "enforced": True,
    }


def quota_exceeded_message(state: dict[str, Any]) -> str:
    scope_key = state.get("scope_key") or ""
    who = f"扩展「{scope_key}」" if scope_key else "本实例"
    return (
        f"本月 AI 用量已达{who}的配额（已用 {state.get('used', 0)} / 上限 {state.get('limit', 0)} tokens）。"
        "请在「AI 网关 → 用量与配额」中调高上限或切换为仅告警策略，或等待下月重置。"
    )


# ── 汇总（供 API 与前端用）──────────────────────────────────────────


def summary(db: Session, *, days: int = 7) -> dict[str, Any]:
    """按最近 N 天聚合：总量、按扩展、按来源、按模型、按天。"""
    from datetime import timedelta

    days = max(1, min(int(days or 7), 90))
    since = datetime.now() - timedelta(days=days)
    base = [PlatformAiUsage.created_at >= since, PlatformAiUsage.ok.is_(True)]

    totals = db.execute(
        select(
            func.count(PlatformAiUsage.id),
            func.coalesce(func.sum(PlatformAiUsage.tokens_in), 0),
            func.coalesce(func.sum(PlatformAiUsage.tokens_out), 0),
            func.coalesce(func.sum(PlatformAiUsage.total_tokens), 0),
            func.coalesce(func.avg(PlatformAiUsage.latency_ms), 0),
        ).where(*base)
    ).one()

    by_key = db.execute(
        select(
            PlatformAiUsage.scope,
            PlatformAiUsage.scope_key,
            func.count(PlatformAiUsage.id),
            func.coalesce(func.sum(PlatformAiUsage.total_tokens), 0),
        )
        .where(*base)
        .group_by(PlatformAiUsage.scope, PlatformAiUsage.scope_key)
        .order_by(func.coalesce(func.sum(PlatformAiUsage.total_tokens), 0).desc())
    ).all()

    by_source = db.execute(
        select(
            PlatformAiUsage.source,
            func.count(PlatformAiUsage.id),
            func.coalesce(func.sum(PlatformAiUsage.total_tokens), 0),
        )
        .where(*base)
        .group_by(PlatformAiUsage.source)
    ).all()

    by_model = db.execute(
        select(
            PlatformAiUsage.model_code,
            func.count(PlatformAiUsage.id),
            func.coalesce(func.sum(PlatformAiUsage.total_tokens), 0),
        )
        .where(*base)
        .group_by(PlatformAiUsage.model_code)
        .order_by(func.coalesce(func.sum(PlatformAiUsage.total_tokens), 0).desc())
        .limit(10)
    ).all()

    by_day = db.execute(
        select(
            func.date(PlatformAiUsage.created_at),
            func.count(PlatformAiUsage.id),
            func.coalesce(func.sum(PlatformAiUsage.total_tokens), 0),
        )
        .where(*base)
        .group_by(func.date(PlatformAiUsage.created_at))
        .order_by(func.date(PlatformAiUsage.created_at))
    ).all()

    failed = db.scalar(
        select(func.count(PlatformAiUsage.id)).where(
            PlatformAiUsage.created_at >= since, PlatformAiUsage.ok.is_(False)
        )
    )

    return {
        "days": days,
        "totals": {
            "calls": int(totals[0] or 0),
            "tokens_in": int(totals[1] or 0),
            "tokens_out": int(totals[2] or 0),
            "tokens": int(totals[3] or 0),
            "avg_latency_ms": int(totals[4] or 0),
            "failed_calls": int(failed or 0),
        },
        "by_scope": [
            {
                "scope": r[0],
                "key": r[1] or "",
                "calls": int(r[2] or 0),
                "tokens": int(r[3] or 0),
            }
            for r in by_key
        ],
        "by_source": [{"source": r[0], "calls": int(r[1] or 0), "tokens": int(r[2] or 0)} for r in by_source],
        "by_model": [
            {"model_code": r[0] or "", "calls": int(r[1] or 0), "tokens": int(r[2] or 0)} for r in by_model
        ],
        "by_day": [
            {"date": str(r[0]), "calls": int(r[1] or 0), "tokens": int(r[2] or 0)} for r in by_day
        ],
    }


def recent(db: Session, *, limit: int = 30, offset: int = 0, scope_key: str | None = None) -> list[dict[str, Any]]:
    stmt = (
        select(PlatformAiUsage)
        .order_by(PlatformAiUsage.id.desc())
        .limit(max(1, min(int(limit or 30), 200)))
        .offset(max(0, int(offset or 0)))
    )
    if scope_key:
        stmt = stmt.where(PlatformAiUsage.scope_key == scope_key)
    rows = list(db.scalars(stmt).all())
    return [
        {
            "id": r.id,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            "scope": r.scope,
            "scope_key": r.scope_key or "",
            "source": r.source,
            "model_code": r.model_code or "",
            "gateway_code": r.gateway_code or "",
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "total_tokens": r.total_tokens,
            "latency_ms": r.latency_ms,
            "ok": bool(r.ok),
            "over_quota": bool(r.over_quota),
            "error": r.error or "",
        }
        for r in rows
    ]
