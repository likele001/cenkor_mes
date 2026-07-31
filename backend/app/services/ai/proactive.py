# -*- coding: utf-8 -*-
"""Proactive recommendation engine - scans business state and suggests actions."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _check_order_overdue(db: Session, tenant_id: int) -> list:
    """Find orders approaching their deadline."""
    from app.models.order import Order

    today = date.today()
    deadline = today + timedelta(days=7)
    rows = db.execute(
        select(Order).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(("confirmed", "processing", "in_production")),
            Order.due_date.isnot(None),
            Order.due_date <= deadline,
            Order.due_date >= today,
        )
    ).scalars().all()
    risky = []
    for o in rows:
        days_left = (o.due_date - today).days
        risky.append({
            "rule": "order_due_soon",
            "title": f"订单 {o.code} 临近交期",
            "content": f"预计 {o.due_date.isoformat()} 交期，还剩 {days_left} 天",
            "biz_id": o.id,
        })
    return risky


def _check_yield_drop(db: Session, tenant_id: int) -> list:
    """Detect significant yield drops."""
    from app.models.report import Report
    from app.models.task import Task
    from app.models.work_order import WorkOrder

    since_7d = date.today() - timedelta(days=7)
    since_30d = date.today() - timedelta(days=30)

    # Last 7 days vs prior 23 days
    recent = db.execute(
        select(func.sum(Report.good_qty), func.sum(Report.bad_qty))
        .join(Task, Task.id == Report.task_id)
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(WorkOrder.tenant_id == tenant_id, func.date(Report.created_at) >= since_7d)
    ).first()

    prior = db.execute(
        select(func.sum(Report.good_qty), func.sum(Report.bad_qty))
        .join(Task, Task.id == Report.task_id)
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(
            WorkOrder.tenant_id == tenant_id,
            func.date(Report.created_at) >= since_30d,
            func.date(Report.created_at) < since_7d,
        )
    ).first()

    def _rate(row):
        if not row: return None
        g, b = row[0] or 0, row[1] or 0
        total = g + b
        return g / total if total > 0 else None

    recent_rate = _rate(recent)
    prior_rate = _rate(prior)

    if recent_rate is not None and prior_rate is not None and prior_rate > 0:
        drop = prior_rate - recent_rate
        if drop > 0.05:  # > 5% drop
            return [{
                "rule": "yield_drop",
                "title": f"良率下降 {round(drop*100, 1)}%",
                "content": f"近7天良率 {round(recent_rate*100, 1)}%，前23天 {round(prior_rate*100, 1)}%，建议核查质量问题",
                "biz_id": None,
            }]
    return []


def _check_equipment_risk(db: Session, tenant_id: int) -> list:
    """Check equipment health alerts."""
    try:
        from app.services.ai.predict.equipment_predictor import equipment_health_scores_enhanced
        result = equipment_health_scores_enhanced(db, tenant_id)
        risky_items = [item for item in result.get("items", [])
                       if item.get("health_score", 100) < 50 or item.get("trend") == "declining"]
        suggestions = []
        for item in risky_items[:3]:
            suggestions.append({
                "rule": "equipment_risk",
                "title": f"设备 {item.get('code','')} 健康分偏低",
                "content": f"健康分 {item.get('health_score', 0)}，趋势 {item.get('trend','unknown')}，建议安排点检保养",
                "biz_id": item.get("equipment_id"),
            })
        return suggestions
    except Exception as e:
        logger.warning("Equipment risk check failed: %s", e)
        return []


def _check_pending_dispatch(db: Session, tenant_id: int) -> list:
    """Check for pending tasks waiting for dispatch."""
    from app.models.task import Task

    count = db.scalar(
        select(func.count(Task.id)).where(Task.tenant_id == tenant_id, Task.status == "pending")
    ) or 0
    if count >= 10:
        return [{
            "rule": "pending_dispatch",
            "title": f"待派工任务 {count} 个",
            "content": f"当前有 {count} 个任务待派工，建议及时分配员工",
            "biz_id": None,
        }]
    return []


def check_and_recommend(db: Session, tenant_id: int) -> dict:
    """Scan all business state and generate recommendations."""
    all_recs = []
    all_recs.extend(_check_order_overdue(db, tenant_id))
    all_recs.extend(_check_yield_drop(db, tenant_id))
    all_recs.extend(_check_equipment_risk(db, tenant_id))
    all_recs.extend(_check_pending_dispatch(db, tenant_id))
    return {
        "ok": True,
        "count": len(all_recs),
        "recommendations": all_recs,
    }


def get_recommendations(db: Session, tenant_id: int, *, limit: int = 20) -> dict:
    """Get current recommendations (live scan)."""
    return check_and_recommend(db, tenant_id)
