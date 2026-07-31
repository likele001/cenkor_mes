"""AI 调用统计（基于 ai_messages 落库）"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai import AiConversation, AiMessage


def ai_usage_stats(db: Session, tenant_id: int, *, days: int = 30) -> dict:
    days = max(1, min(int(days), 365))
    since = datetime.utcnow() - timedelta(days=days)

    base = (
        select(
            AiConversation.scene,
            func.count(AiMessage.id),
            func.coalesce(func.sum(AiMessage.tokens_in), 0),
            func.coalesce(func.sum(AiMessage.tokens_out), 0),
        )
        .join(AiConversation, AiConversation.id == AiMessage.conversation_id)
        .where(AiConversation.tenant_id == tenant_id, AiMessage.role == "assistant", AiMessage.created_at >= since)
        .group_by(AiConversation.scene)
    )
    by_scene = []
    total_calls = 0
    total_in = 0
    total_out = 0
    for scene, cnt, tin, tout in db.execute(base).all():
        c = int(cnt or 0)
        ti = int(tin or 0)
        to = int(tout or 0)
        total_calls += c
        total_in += ti
        total_out += to
        by_scene.append({"scene": scene, "calls": c, "tokens_in": ti, "tokens_out": to})

    daily_rows = db.execute(
        select(
            func.date(AiMessage.created_at),
            func.count(AiMessage.id),
            func.coalesce(func.sum(AiMessage.tokens_in), 0),
            func.coalesce(func.sum(AiMessage.tokens_out), 0),
        )
        .join(AiConversation, AiConversation.id == AiMessage.conversation_id)
        .where(
            AiConversation.tenant_id == tenant_id,
            AiMessage.role == "assistant",
            AiMessage.created_at >= since,
        )
        .group_by(func.date(AiMessage.created_at))
        .order_by(func.date(AiMessage.created_at))
    ).all()
    daily = [
        {
            "date": (d.isoformat() if isinstance(d, date) else str(d)),
            "calls": int(c or 0),
            "tokens_in": int(ti or 0),
            "tokens_out": int(to or 0),
        }
        for d, c, ti, to in daily_rows
    ]

    return {
        "ok": True,
        "window_days": days,
        "total_calls": total_calls,
        "tokens_in": total_in,
        "tokens_out": total_out,
        "by_scene": sorted(by_scene, key=lambda x: x["calls"], reverse=True),
        "daily": daily,
    }
