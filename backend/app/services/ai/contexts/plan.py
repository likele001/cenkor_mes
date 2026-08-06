from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.order import get_order_by_id
from app.crud.production_plan import get_plan_by_id
from app.crud.task_assignment import task_has_assignments
from app.models.order import Order
from app.models.task import Task
from app.models.work_order import WorkOrder
from app.services.plan_readiness import build_plan_readiness


def build_plan_context(db: Session, plan_id: int) -> dict:
    plan = get_plan_by_id(db, plan_id=plan_id)
    if not plan:
        return {}
    order = get_order_by_id(db, order_id=plan.order_id, with_items=True)
    try:
        readiness = build_plan_readiness(db, order_id=plan.order_id, plan_id=plan_id)
    except ValueError as e:
        readiness = {"ready": False, "blockers": [str(e)], "kitting": {}, "process": {}}

    task_rows = db.execute(
        select(Task.status, func.count(Task.id))
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .where(WorkOrder.order_id == plan.order_id)
        .group_by(Task.status)
    ).all()
    task_stats = {str(s): int(c) for s, c in task_rows}

    unassigned = 0
    pending_tasks = db.scalars(
        select(Task)
        .select_from(WorkOrder)
        .join(Task, Task.work_order_id == WorkOrder.id)
        .where(WorkOrder.order_id == plan.order_id, Task.status != "done")
    ).all()
    for t in pending_tasks:
        if not task_has_assignments(db, t.id):
            unassigned += 1

    today = date.today()
    overdue = False
    if order and order.due_date and plan.end_date:
        overdue = plan.end_date > order.due_date
    elif order and order.due_date and not plan.end_date:
        overdue = order.due_date < today

    return {
        "plan": {
            "id": plan.id,
            "code": plan.code,
            "status": plan.status,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
            "work_days": plan.work_days,
        },
        "order": {
            "id": order.id if order else None,
            "code": order.code if order else None,
            "due_date": order.due_date.isoformat() if order and order.due_date else None,
            "status": order.status if order else None,
        },
        "readiness": {
            "ready": readiness.get("ready"),
            "blockers": readiness.get("blockers") or [],
            "shortage_count": readiness.get("kitting", {}).get("shortage_count"),
            "missing_bom_count": readiness.get("kitting", {}).get("missing_bom_count"),
            "missing_route_count": readiness.get("process", {}).get("missing_route_count"),
            "missing_price_count": readiness.get("process", {}).get("missing_price_count"),
            "top_shortages": [
                {
                    "material_code": it.get("material_code"),
                    "material_name": it.get("material_name"),
                    "shortage_qty": it.get("shortage_qty"),
                    "demand_qty": it.get("demand_qty"),
                    "stock_qty": it.get("stock_qty"),
                }
                for it in sorted(
                    readiness.get("kitting", {}).get("items") or [],
                    key=lambda x: int(x.get("shortage_qty") or 0),
                    reverse=True,
                )
                if int(it.get("shortage_qty") or 0) > 0
            ][:8],
        },
        "tasks": task_stats,
        "unassigned_task_count": unassigned,
        "plan_end_after_due": overdue,
    }