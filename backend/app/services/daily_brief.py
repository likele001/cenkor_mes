"""每日厂长简报（规则 / LLM）"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.dashboard import get_dashboard_summary
from app.crud.notification import notify_users_with_permission
from app.models.order import Order

from app.services.production_automation_settings import get_automation_settings


def _aggregate_brief_data(db: Session) -> dict:
    dash = get_dashboard_summary(db)
    overdue_orders = db.scalar(
        select(func.count(Order.id)).where(
            Order.status.in_(["confirmed", "producing"]),
            Order.due_date.isnot(None),
            Order.due_date < datetime.utcnow().date(),
        )
    )
    today = dash.get("today") or {}
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "today": today,
        "pending_audit": int((dash.get("reports") or {}).get("pending_audit") or 0),
        "overdue_orders": int(overdue_orders or 0),
        "orders": dash.get("orders") or {},
        "tasks": dash.get("tasks") or {},
    }


def build_rule_brief(data: dict) -> str:
    today = data.get("today") or {}
    lines = [
        f"【{data.get('date')} 生产简报】",
        f"今日合格产量：{today.get('good_qty', 0)}",
        f"待审核报工：{data.get('pending_audit', 0)} 条",
        f"逾期订单：{data.get('overdue_orders', 0)} 单",
    ]
    orders = data.get("orders") or {}
    if orders.get("confirmed"):
        lines.append(f"已确认订单：{orders.get('confirmed')} 单")
    tasks = data.get("tasks") or {}
    if tasks.get("pending"):
        lines.append(f"待开工任务：{tasks.get('pending')} 个")
    return "\n".join(lines)


def build_llm_brief(db: Session, data: dict) -> str:
    try:
        from app.services.ai.client import chat_completion

        text, _, _ = chat_completion(
            db,
            messages=[
                {
                    "role": "user",
                    "content": "你是工厂生产顾问，请根据以下数据写一段不超过200字的厂长早报，语气简洁：\n" + str(data),
                }
            ],
            max_tokens=400,
        )
        return text or build_rule_brief(data)
    except Exception:
        return build_rule_brief(data)


def get_live_brief(db: Session, tenant_id_or_uid: int = 0, user_id: int = 0) -> dict:
    settings = get_automation_settings(db, tenant_id_or_uid or 1)
    data = _aggregate_brief_data(db)
    mode = (settings.get("briefing") or {}).get("mode") or "rule"
    if mode == "llm":
        content = build_llm_brief(db, data)
    else:
        content = build_rule_brief(data)
    return {"mode": mode, "content": content, "data": data}


def send_daily_brief(db: Session, tenant_id: int = 1, *, current_hour: int = 20) -> int:
    settings = get_automation_settings(db, tenant_id or 1)
    briefing = settings.get("briefing") or {}
    if not briefing.get("daily_enabled"):
        return 0
    # beat 已在 20:00 触发，current_hour 用于兜底校验（如 0-23 范围）
    # 注：daily_hour 配置已废弃，统一走 celery beat 20:00
    target_hour = 20
    if current_hour != target_hour:
        return 0

    data = _aggregate_brief_data(db)
    mode = briefing.get("mode") or "rule"
    if mode == "llm":
        content = build_llm_brief(db, data)
    else:
        content = build_rule_brief(data)

    title = f"今日生产简报 {data.get('date')}"

    notify_users_with_permission(
        db,
        permission_code="ai.use",
        title=title,
        content=content[:2000],
        level="info",
        biz_type="daily_brief",
        biz_id=0,
    )
    try:
        from app.services.notify_dispatcher import dispatch

        dispatch(
            db,
            "brief.daily",
            title=title,
            content=content[:2000],
            level="info",
            biz_type="daily_brief",
            biz_id=0,
        )
    except Exception:
        pass
    db.commit()
    return 1


def send_daily_briefs(db: Session, *, current_hour: int) -> dict:
    sent = 0
    try:
        sent += send_daily_brief(db, current_hour=current_hour)
    except Exception:
        db.rollback()
    return {"sent": sent, "hour": current_hour}
