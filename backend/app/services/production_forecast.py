# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""计划交期预测 — 用真实报工速度推算能否按期完工

只读：从工单/任务/报工/齐套算出风险等级，不写任何状态。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.order import get_order_by_id
from app.crud.production_plan import get_plan_by_id
from app.models.report import Report
from app.models.task import Task
from app.models.work_order import WorkOrder
from app.services.plan_readiness import build_order_kitting_preview

OUTPUT_WINDOW_DAYS = 7


def _approved_good_qty_by_day(db: Session, task_ids: list[int], since: date) -> dict[str, int]:
    """按天汇总已审核通过的良品产量（未审核的报工不算产能）。"""
    if not task_ids:
        return {}
    day_col = func.date(Report.created_at)
    rows = db.execute(
        select(day_col.label("d"), func.coalesce(func.sum(Report.good_qty), 0))
        .where(
            Report.task_id.in_(task_ids),
            Report.status == "qc_approved",
            Report.created_at >= datetime.combine(since, datetime.min.time()),
        )
        .group_by(day_col)
    ).all()
    return {str(r[0]): int(r[1] or 0) for r in rows}


def _risk_level(days_left: int | None, days_needed: float | None) -> str:
    if days_left is None:
        return "unknown"
    if days_left < 0:
        return "overdue"
    if days_needed is None:
        return "low" if days_left > 3 else "medium"
    if days_needed > days_left:
        return "high"
    if days_left <= 2:
        return "medium"
    return "low"


def build_plan_forecast(db: Session, plan_id: int) -> dict:
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise ValueError("计划不存在")

    order = get_order_by_id(db, plan.order_id, with_items=True)
    if not order:
        raise ValueError("计划关联的订单不存在")

    task_ids = list(db.scalars(
        select(Task.id).join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(WorkOrder.order_id == plan.order_id)
    ).all())

    remaining_tasks = int(db.scalar(
        select(func.count(Task.id))
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(WorkOrder.order_id == plan.order_id, Task.status != "done")
    ) or 0)

    remaining_qty = int(db.scalar(
        select(func.coalesce(func.sum(Task.planned_qty), 0))
        .join(WorkOrder, WorkOrder.id == Task.work_order_id)
        .where(WorkOrder.order_id == plan.order_id, Task.status != "done")
    ) or 0)

    today = date.today()
    since = today - timedelta(days=OUTPUT_WINDOW_DAYS - 1)
    by_day = _approved_good_qty_by_day(db, task_ids, since)
    produced_in_window = sum(by_day.values())
    avg_daily_output_7d = round(produced_in_window / OUTPUT_WINDOW_DAYS, 2)

    days_needed = round(remaining_qty / avg_daily_output_7d, 1) if avg_daily_output_7d > 0 and remaining_qty > 0 else None
    due_date = order.due_date
    days_left = (due_date - today).days if due_date else None

    kitting = build_order_kitting_preview(db, order.id) or {}
    shortage_count = int(kitting.get("shortage_count") or 0)
    kitting_ok = bool(kitting.get("ok"))

    risk = _risk_level(days_left, days_needed)
    if risk == "low" and shortage_count > 0:
        risk = "medium"

    return {
        "plan_id": plan.id,
        "plan_code": plan.code,
        "order_id": order.id,
        "order_code": order.code,
        "due_date": str(due_date) if due_date else None,
        "days_left": days_left,
        "remaining_tasks": remaining_tasks,
        "remaining_qty": remaining_qty,
        "avg_daily_output_7d": avg_daily_output_7d,
        "days_needed": days_needed,
        "kitting_ok": kitting_ok,
        "shortage_count": shortage_count,
        "due_risk": risk,
    }
