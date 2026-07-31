from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.crud.report_unit import (
    assignment_has_non_draft_units,
    count_user_reported_units,
    sync_assignment_units,
)
from app.models.report import Report
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.user import User
from app.crud.process_flow import ensure_work_order_piece_pool, is_first_process_task
from app.models.work_order import WorkOrder
from app.services.report_mode_settings import use_unit_report_mode


def _assignment_load_options():
    from app.models.work_order import WorkOrder

    return (
        selectinload(TaskAssignment.user),
        selectinload(TaskAssignment.task).options(
            selectinload(Task.process),
            selectinload(Task.work_order).options(
                selectinload(WorkOrder.order),
                selectinload(WorkOrder.sku),
                selectinload(WorkOrder.product),
            ),
        ),
    )


def get_assignment_by_id(db: Session, assignment_id: int) -> TaskAssignment | None:
    return db.scalar(
        select(TaskAssignment)
        .where(TaskAssignment.id == assignment_id)
        .options(*_assignment_load_options())
    )


def list_assignments(
    db: Session,
    *,
    keyword: str | None = None,
    order_id: int | None = None,
    user_id: int | None = None,
    process_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[TaskAssignment], int]:
    from app.models.order import Order
    from app.models.process import Process
    from app.models.work_order import WorkOrder

    base = select(TaskAssignment)
    if order_id is not None or keyword:
        base = base.join(Task, Task.id == TaskAssignment.task_id).join(
            WorkOrder, WorkOrder.id == Task.work_order_id
        )
        if order_id is not None:
            base = base.where(WorkOrder.order_id == order_id)
    elif user_id is not None or process_id is not None:
        base = base.join(Task, Task.id == TaskAssignment.task_id)
    if user_id is not None:
        base = base.where(TaskAssignment.user_id == user_id)
    if process_id is not None:
        base = base.where(Task.process_id == process_id)
    if keyword:
        kw = f"%{keyword}%"
        base = base.outerjoin(Order, Order.id == WorkOrder.order_id).where(
            (Task.task_code.like(kw))
            | (Order.code.like(kw))
        )

    count_stmt = select(func.count(TaskAssignment.id))
    if order_id is not None or keyword:
        count_stmt = count_stmt.select_from(TaskAssignment).join(Task).join(WorkOrder)
    elif user_id is not None or process_id is not None:
        count_stmt = count_stmt.select_from(TaskAssignment).join(Task)
    else:
        count_stmt = count_stmt.select_from(TaskAssignment)

    if user_id is not None:
        count_stmt = count_stmt.where(TaskAssignment.user_id == user_id)
    if process_id is not None:
        count_stmt = count_stmt.where(Task.process_id == process_id)
    if order_id is not None:
        count_stmt = count_stmt.where(WorkOrder.order_id == order_id)
    if keyword:
        kw = f"%{keyword}%"
        count_stmt = count_stmt.outerjoin(Order, Order.id == WorkOrder.order_id).where(
            (Task.task_code.like(kw)) | (Order.code.like(kw))
        )
    total = int(db.scalar(count_stmt) or 0)

    stmt = (
        base.options(*_assignment_load_options())
        .order_by(TaskAssignment.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all(), total


def remove_assignment_by_id(db: Session, assignment_id: int, dispatcher_user_id: int) -> None:
    a = get_assignment_by_id(db, assignment_id)
    if not a:
        raise ValueError("派工记录不存在")
    task = db.get(Task, a.task_id)
    if not task:
        raise ValueError("任务不存在")
    if assignment_has_non_draft_units(db, a.id):
        raise ValueError("该派工已有报工记录，不能删除")
    rows = list_assignments_for_task(db, task.id)
    items = [{"user_id": r.user_id, "assigned_qty": int(r.assigned_qty)} for r in rows if r.id != assignment_id]
    replace_task_assignments(db, task=task, items=items, dispatcher_user_id=dispatcher_user_id)


def list_assignments_for_task(db: Session, task_id: int) -> list[TaskAssignment]:
    stmt = (
        select(TaskAssignment)
        .where(TaskAssignment.task_id == task_id)
        .options(selectinload(TaskAssignment.user))
        .order_by(TaskAssignment.id.asc())
    )
    return db.scalars(stmt).all()


def get_assignment(db: Session, task_id: int, user_id: int) -> TaskAssignment | None:
    return db.scalar(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.user_id == user_id,
        )
    )


def task_has_assignments(db: Session, task_id: int) -> bool:
    n = db.scalar(
        select(func.count(TaskAssignment.id)).where(
            TaskAssignment.task_id == task_id,
        )
    )
    return int(n or 0) > 0


def sum_assigned_qty(db: Session, task_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(TaskAssignment.assigned_qty), 0)).where(
                TaskAssignment.task_id == task_id,
            )
        )
        or 0
    )


def sum_user_reported_qty(db: Session, task_id: int, user_id: int) -> int:
    unit_count = count_user_reported_units(db, task_id, user_id)
    legacy = int(
        db.scalar(
            select(func.coalesce(func.sum(Report.good_qty + Report.bad_qty), 0)).where(
                Report.task_id == task_id,
                Report.report_user_id == user_id,
                Report.status != "rejected",
            )
        )
        or 0
    )
    return unit_count + legacy


def sync_task_legacy_assign_fields(db: Session, task: Task) -> Task:
    first = db.scalar(
        select(TaskAssignment)
        .where(TaskAssignment.task_id == task.id)
        .order_by(TaskAssignment.id.asc())
        .limit(1)
    )
    if first:
        task.assigned_user_id = first.user_id
        task.assigned_at = first.assigned_at
        task.assigned_by = first.assigned_by
    else:
        task.assigned_user_id = None
        task.assigned_at = None
        task.assigned_by = None
    db.flush()
    return task


def replace_task_assignments(
    db: Session,
    *,
    task: Task,
    items: list[dict],
    dispatcher_user_id: int,
) -> list[TaskAssignment]:
    seen_users: set[int] = set()
    total_qty = 0
    for it in items:
        uid = int(it["user_id"])
        qty = int(it["assigned_qty"])
        if uid in seen_users:
            raise ValueError("同一员工不能重复派工")
        if qty <= 0:
            raise ValueError("派工数量必须大于0")
        seen_users.add(uid)
        total_qty += qty

    if total_qty > int(task.planned_qty):
        raise ValueError(f"派工数量合计({total_qty})不能超过任务计划数({task.planned_qty})")

    current = list_assignments_for_task(db, task.id)
    current_by_user = {a.user_id: a for a in current}
    new_user_ids = seen_users

    for it in items:
        uid = int(it["user_id"])
        qty = int(it["assigned_qty"])
        reported = sum_user_reported_qty(db, task.id, uid)
        if qty < reported:
            raise ValueError(f"员工#{uid}派工数不能小于已报工数({reported})")

    for a in current:
        if a.user_id not in new_user_ids:
            if assignment_has_non_draft_units(db, a.id):
                raise ValueError(f"员工#{a.user_id}已有报工件次，不能取消派工")
            db.execute(
                delete(TaskAssignment).where(
                    TaskAssignment.id == a.id,
                )
            )

    now = datetime.now()
    result: list[TaskAssignment] = []
    for it in items:
        uid = int(it["user_id"])
        qty = int(it["assigned_qty"])
        existing = current_by_user.get(uid)
        if existing:
            existing.assigned_qty = qty
            existing.assigned_by = dispatcher_user_id
            row = existing
        else:
            row = TaskAssignment(
                task_id=task.id,
                user_id=uid,
                assigned_qty=qty,
                assigned_at=now,
                assigned_by=dispatcher_user_id,
            )
            db.add(row)
        db.flush()
        sync_assignment_units(db, row)
        result.append(row)

    db.flush()
    sync_task_legacy_assign_fields(db, task)
    if use_unit_report_mode(db) and is_first_process_task(db, task):
        wo = db.get(WorkOrder, task.work_order_id)
        if wo:
            ensure_work_order_piece_pool(db, wo.id, wo.qty)

    new_user_ids = [int(it["user_id"]) for it in items if int(it["user_id"]) not in current_by_user]
    if new_user_ids:
        try:
            from app.models.process import Process
            from app.services.feishu.notify import notify_dispatch_assigned

            proc = db.get(Process, task.process_id)
            proc_name = proc.name if proc else ""
            notify_dispatch_assigned(
                db,
                user_ids=new_user_ids,
                title="新任务派工",
                content=f"任务 {task.task_code} 工序 {proc_name or '-'} 已派工，请至手机端查看",
                biz_type="task",
                biz_id=task.id,
                task_code=task.task_code,
            )
        except Exception:
            pass
        try:
            from app.services.wecom.notify import notify_dispatch_assigned as wecom_notify_dispatch

            wecom_notify_dispatch(
                db,
                user_ids=new_user_ids,
                title="新任务派工",
                content=f"任务 {task.task_code} 已派工，请至手机端查看",
                biz_type="task",
                biz_id=task.id,
                task_code=task.task_code,
            )
        except Exception:
            pass
        try:
            from app.services.dingtalk.notify import notify_dispatch_assigned as dingtalk_notify_dispatch

            dingtalk_notify_dispatch(
                db,
                user_ids=new_user_ids,
                title="新任务派工",
                content=f"任务 {task.task_code} 已派工，请至手机端查看",
                biz_type="task",
                biz_id=task.id,
                task_code=task.task_code,
            )
        except Exception:
            pass
    return result


def validate_report_qty_limit(
    db: Session,
    *,
    task: Task,
    user_id: int,
    good_qty: int,
    bad_qty: int,
) -> TaskAssignment:
    assignment = get_assignment(db, task.id, user_id)
    if not assignment:
        raise ValueError("您未被派工到此任务")
    reported = sum_user_reported_qty(db, task.id, user_id)
    new_total = reported + good_qty + bad_qty
    if new_total > assignment.assigned_qty:
        remain = max(0, assignment.assigned_qty - reported)
        raise ValueError(f"报工数量超出派工上限，最多还可报 {remain} 件")
    return assignment


def ensure_users_exist(db: Session, user_ids: list[int]) -> None:
    for uid in user_ids:
        u = db.get(User, uid)
        if not u or not u.is_active:
            raise ValueError(f"派工人员不存在: {uid}")
