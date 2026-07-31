from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.report import Report
from app.models.task import Task
from app.models.work_order import WorkOrder


def _due_fields(due_date: date | None) -> tuple[int | None, str]:
    if not due_date:
        return None, "ok"
    due_days = (due_date - date.today()).days
    if due_days < 0:
        return due_days, "overdue"
    if due_days <= 3:
        return due_days, "warn"
    return due_days, "ok"


def list_kanban_orders(
    db: Session,
    status: str | None = None,
    customer_id: int | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[dict]:
    task_done_sq = (
        select(
            Task.id.label("task_id"),
            Task.work_order_id.label("work_order_id"),
            func.coalesce(func.sum(Report.good_qty), 0).label("done_qty"),
        )
        .select_from(Task)
        .join(Report, and_(Report.task_id == Task.id, Report.status == "qc_approved"), isouter=True)
        .group_by(Task.id)
        .subquery()
    )

    wo_done_sq = (
        select(
            task_done_sq.c.work_order_id.label("work_order_id"),
            func.min(task_done_sq.c.done_qty).label("done_qty"),
        )
        .group_by(task_done_sq.c.work_order_id)
        .subquery()
    )

    order_sq = (
        select(
            WorkOrder.order_id.label("order_id"),
            func.coalesce(func.sum(WorkOrder.qty), 0).label("total_qty"),
            func.coalesce(func.sum(func.coalesce(wo_done_sq.c.done_qty, 0)), 0).label("done_qty"),
        )
        .select_from(WorkOrder)
        .join(wo_done_sq, wo_done_sq.c.work_order_id == WorkOrder.id, isouter=True)
        .group_by(WorkOrder.order_id)
        .subquery()
    )

    stmt = (
        select(
            Order,
            order_sq.c.total_qty,
            order_sq.c.done_qty,
        )
        .join(order_sq, order_sq.c.order_id == Order.id, isouter=True)
        .options(selectinload(Order.customer))
        .order_by(Order.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Order.status == status)
    if customer_id is not None:
        stmt = stmt.where(Order.customer_id == customer_id)
    if due_from is not None:
        stmt = stmt.where(Order.due_date >= due_from)
    if due_to is not None:
        stmt = stmt.where(Order.due_date <= due_to)

    rows = db.execute(stmt).all()
    items: list[dict] = []
    for order, total_qty, done_qty in rows:
        total = int(total_qty or 0)
        done = int(done_qty or 0)
        progress = round(done / total, 6) if total > 0 else None
        customer: Customer | None = order.customer
        due_days, warning_level = _due_fields(order.due_date)
        items.append(
            {
                "id": order.id,
                "code": order.code,
                "status": order.status,
                "due_date": str(order.due_date) if order.due_date else None,
                "due_days": due_days,
                "warning_level": warning_level,
                "total_qty": total,
                "done_qty": done,
                "progress": progress,
                "customer": (
                    {"id": customer.id, "code": customer.code, "name": customer.name} if customer else None
                ),
                "created_at": order.created_at,
                "updated_at": order.updated_at,
            }
        )
    return items


def get_orders_progress_map(db: Session, order_ids: list[int]) -> dict[int, dict]:
    """批量查询订单完成数量与进度（计划列表等复用）。"""
    if not order_ids:
        return {}
    task_done_sq = (
        select(
            Task.id.label("task_id"),
            Task.work_order_id.label("work_order_id"),
            func.coalesce(func.sum(Report.good_qty), 0).label("done_qty"),
        )
        .select_from(Task)
        .join(Report, and_(Report.task_id == Task.id, Report.status == "qc_approved"), isouter=True)
        .group_by(Task.id)
        .subquery()
    )
    wo_done_sq = (
        select(
            task_done_sq.c.work_order_id.label("work_order_id"),
            func.min(task_done_sq.c.done_qty).label("done_qty"),
        )
        .group_by(task_done_sq.c.work_order_id)
        .subquery()
    )
    rows = db.execute(
        select(
            WorkOrder.order_id.label("order_id"),
            func.coalesce(func.sum(WorkOrder.qty), 0).label("total_qty"),
            func.coalesce(func.sum(func.coalesce(wo_done_sq.c.done_qty, 0)), 0).label("done_qty"),
        )
        .select_from(WorkOrder)
        .join(wo_done_sq, wo_done_sq.c.work_order_id == WorkOrder.id, isouter=True)
        .where(WorkOrder.order_id.in_(order_ids))
        .group_by(WorkOrder.order_id)
    ).all()
    out: dict[int, dict] = {}
    for order_id, total_qty, done_qty in rows:
        total = int(total_qty or 0)
        done = int(done_qty or 0)
        progress = round(done / total, 6) if total > 0 else None
        out[int(order_id)] = {"total_qty": total, "done_qty": done, "progress": progress}
    return out


def get_order_progress_summary(db: Session, order_id: int) -> dict:
    task_done_sq = (
        select(
            Task.id.label("task_id"),
            Task.work_order_id.label("work_order_id"),
            func.coalesce(func.sum(Report.good_qty), 0).label("done_qty"),
        )
        .select_from(Task)
        .join(Report, and_(Report.task_id == Task.id, Report.status == "qc_approved"), isouter=True)
        .group_by(Task.id)
        .subquery()
    )

    wo_done_sq = (
        select(
            task_done_sq.c.work_order_id.label("work_order_id"),
            func.min(task_done_sq.c.done_qty).label("done_qty"),
        )
        .group_by(task_done_sq.c.work_order_id)
        .subquery()
    )

    total_qty, done_qty = (
        db.execute(
            select(
                func.coalesce(func.sum(WorkOrder.qty), 0).label("total_qty"),
                func.coalesce(func.sum(func.coalesce(wo_done_sq.c.done_qty, 0)), 0).label("done_qty"),
            )
            .select_from(WorkOrder)
            .join(wo_done_sq, wo_done_sq.c.work_order_id == WorkOrder.id, isouter=True)
            .where(WorkOrder.order_id == order_id)
        )
        .one()
    )
    total = int(total_qty or 0)
    done = int(done_qty or 0)
    progress = round(done / total, 6) if total > 0 else None
    return {"total_qty": total, "done_qty": done, "progress": progress}


def get_kanban_order_detail(db: Session, order_id: int) -> dict | None:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.customer),
            selectinload(Order.items).selectinload(OrderItem.sku),
            selectinload(Order.work_orders).selectinload(WorkOrder.sku),
            selectinload(Order.work_orders).selectinload(WorkOrder.tasks).selectinload(Task.process),
        )
    )
    if not order:
        return None
    return _build_order_progress(db, order)


def build_order_progress_for_loaded_order(db: Session, order: Order) -> dict:
    return _build_order_progress(db, order)


def _build_order_progress(db: Session, order: Order) -> dict:
    task_ids: list[int] = []
    for wo in order.work_orders:
        for t in wo.tasks:
            task_ids.append(t.id)

    task_done: dict[int, int] = {}
    if task_ids:
        rows = db.execute(
            select(Report.task_id, func.coalesce(func.sum(Report.good_qty), 0))
            .where(
                Report.status == "qc_approved",
                Report.task_id.in_(task_ids),
            )
            .group_by(Report.task_id)
        ).all()
        task_done = {int(tid): int(qty or 0) for tid, qty in rows}

    work_orders_out: list[dict] = []
    order_total = 0
    order_done = 0

    for wo in order.work_orders:
        wo_total = int(wo.qty or 0)
        order_total += wo_total

        tasks_out: list[dict] = []
        wo_task_dones: list[int] = []
        for t in wo.tasks:
            done_qty = int(task_done.get(t.id, 0))
            planned = int(t.planned_qty or 0)
            progress = round(done_qty / planned, 6) if planned > 0 else None
            tasks_out.append(
                {
                    "id": t.id,
                    "task_code": t.task_code,
                    "seq": t.seq,
                    "process": (
                        {"id": t.process.id, "code": t.process.code, "name": t.process.name} if t.process else None
                    ),
                    "planned_qty": planned,
                    "done_qty": done_qty,
                    "progress": progress,
                    "status": t.status,
                    "assigned_user_id": t.assigned_user_id,
                    "assigned_at": t.assigned_at,
                }
            )
            wo_task_dones.append(done_qty)

        wo_done = min(wo_task_dones) if wo_task_dones else 0
        wo_progress = round(wo_done / wo_total, 6) if wo_total > 0 else None
        order_done += wo_done

        work_orders_out.append(
            {
                "id": wo.id,
                "order_item_id": wo.order_item_id,
                "product_id": wo.product_id,
                "sku": {"id": wo.sku.id, "code": wo.sku.code, "name": wo.sku.name} if wo.sku else None,
                "qty": wo_total,
                "done_qty": int(wo_done),
                "progress": wo_progress,
                "status": wo.status,
                "tasks": tasks_out,
            }
        )

    order_progress = round(order_done / order_total, 6) if order_total > 0 else None

    customer: Customer | None = order.customer
    items_out: list[dict] = []
    for it in order.items:
        sku = it.sku
        items_out.append(
            {
                "id": it.id,
                "line_no": it.line_no,
                "sku": {"id": sku.id, "code": sku.code, "name": sku.name} if sku else None,
                "qty": int(it.qty),
                "remark": it.remark,
            }
        )

    due_days, warning_level = _due_fields(order.due_date)
    return {
        "id": order.id,
        "code": order.code,
        "status": order.status,
        "due_date": str(order.due_date) if order.due_date else None,
        "due_days": due_days,
        "warning_level": warning_level,
        "remark": order.remark,
        "customer_id": order.customer_id,
        "customer": {"id": customer.id, "code": customer.code, "name": customer.name} if customer else None,
        "total_qty": int(order_total),
        "done_qty": int(order_done),
        "progress": order_progress,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": items_out,
        "work_orders": work_orders_out,
    }
