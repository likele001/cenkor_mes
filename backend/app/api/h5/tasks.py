from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.dashboard import get_employee_dashboard_summary
from app.crud.notification import create_notification
from app.crud.report import (
    create_report,
    get_salary_items,
    get_salary_summary)
from app.crud.task import get_task_by_id, get_task_by_code
from app.crud.report_unit import count_draft_units, count_user_reported_units, sync_assignment_units
from app.crud.task_assignment import (
    get_assignment,
    sum_user_reported_qty,
    validate_report_qty_limit)
from app.models.task import Task
from app.models.task_assignment import TaskAssignment

from app.models.user import User
from app.services.report_mode_settings import get_default_report_mode, use_unit_report_mode
from app.services.task_qr import task_qr_payload

router = APIRouter()

def _ensure_employee(user: User) -> None:
    roles = {r.code for r in user.roles}
    if not ({"employee", "leader"} & roles):
        raise HTTPException(status_code=403, detail="无权限")

def _my_assignment_fields(db: Session, task: Task, user_id: int) -> dict:
    report_mode = get_default_report_mode(db)
    a = get_assignment(db, task.id, user_id)
    if not a:
        return {
            "assigned_qty": 0,
            "reported_qty": 0,
            "remaining_qty": 0,
            "use_unit_report": use_unit_report_mode(db),
            "report_mode": report_mode,
        }
    if not use_unit_report_mode(db):
        reported = sum_user_reported_qty(db, task.id, user_id)
        return {
            "assigned_qty": int(a.assigned_qty),
            "reported_qty": reported,
            "remaining_qty": max(0, int(a.assigned_qty) - reported),
            "use_unit_report": False,
            "report_mode": report_mode,
        }
    try:
        sync_assignment_units(db, a)
        db.flush()
    except ValueError:
        pass
    unit_reported = count_user_reported_units(db, task.id, user_id)
    draft = count_draft_units(db, a.id)
    if unit_reported > 0 or draft > 0:
        return {
            "assigned_qty": int(a.assigned_qty),
            "reported_qty": unit_reported,
            "remaining_qty": draft,
            "use_unit_report": True,
            "report_mode": report_mode,
        }
    reported = sum_user_reported_qty(db, task.id, user_id)
    return {
        "assigned_qty": int(a.assigned_qty),
        "reported_qty": reported,
        "remaining_qty": max(0, int(a.assigned_qty) - reported),
        "use_unit_report": False,
        "report_mode": report_mode,
    }

def _task_out(x, db: Session, user_id: int) -> dict:
    wo = x.work_order
    sku = wo.sku if wo else None
    order = wo.order if wo and getattr(wo, "order", None) else None
    extra = _my_assignment_fields(db, x, user_id)
    assigned = int(extra.get("assigned_qty") or 0)
    reported = int(extra.get("reported_qty") or 0)
    progress_pct = round(reported / assigned * 100) if assigned > 0 else 0
    return {
        "id": x.id,
        "task_code": x.task_code,
        "work_order_id": x.work_order_id,
        "process_id": x.process_id,
        "seq": x.seq,
        "planned_qty": x.planned_qty,
        "status": x.status,
        "assigned_user_id": x.assigned_user_id,
        "assigned_at": x.assigned_at,
        "assigned_by": x.assigned_by,
        "equipment_id": getattr(x, "equipment_id", None),
        **extra,
        "progress_pct": progress_pct,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
        "process": {"id": x.process.id, "code": x.process.code, "name": x.process.name} if x.process else None,
        "equipment": (
            {"id": x.equipment.id, "code": x.equipment.code, "name": x.equipment.name, "workshop": x.equipment.workshop, "status": x.equipment.status}
            if getattr(x, "equipment", None)
            else None
        ),
        "work_order": (
            {
                "id": wo.id,
                "order_id": wo.order_id,
                "order_code": order.code if order else None,
                "qty": wo.qty,
                "sku": (
                    {
                        "id": sku.id,
                        "code": sku.code,
                        "name": sku.name,
                        "color": sku.color,
                        "spec": sku.spec,
                        "display_label": f"{sku.code} - {sku.name}" if sku.name else sku.code,
                    }
                    if sku
                    else None
                ),
            }
            if wo
            else None
        ),
    }

@router.get("/tasks")
def my_tasks_api(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    stmt = (
        select(Task)
        .join(TaskAssignment, (TaskAssignment.task_id == Task.id) )
        .where(TaskAssignment.user_id == user.id)
    )
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.id.desc()).offset(offset).limit(limit)
    from sqlalchemy.orm import selectinload
    from app.models.work_order import WorkOrder

    stmt = stmt.options(
        selectinload(Task.process),
        selectinload(Task.equipment),
        selectinload(Task.work_order).selectinload(WorkOrder.sku),
        selectinload(Task.work_order).selectinload(WorkOrder.order))
    items = db.scalars(stmt).all()
    return ok({"items": [_task_out(x, db, user.id) for x in items]})

@router.get("/tasks/{task_code}")
def my_task_detail_api(
    task_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    if task_code.isdigit():
        item = get_task_by_id(db, task_id=int(task_code), with_refs=True)
    else:
        item = get_task_by_code(db, task_code=task_code, with_refs=True)
    if not item:
        raise HTTPException(status_code=400, detail="任务不存在")
    if not get_assignment(db, item.id, user.id):
        raise HTTPException(status_code=403, detail="无权限")
    return ok(_task_out(item, db, user.id))

@router.get("/tasks/{task_code}/qr")
def my_task_qr_api(
    task_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """员工查看本人任务的报工二维码（派工后在此扫码报工）。"""
    _ensure_employee(user)
    if task_code.isdigit():
        item = get_task_by_id(db, task_id=int(task_code), with_refs=False)
    else:
        item = get_task_by_code(db, task_code=task_code, with_refs=False)
    if not item:
        raise HTTPException(status_code=400, detail="任务不存在")
    if not get_assignment(db, item.id, user.id):
        raise HTTPException(status_code=403, detail="无权限")
    return ok(task_qr_payload(item.task_code, ""))

# ── 报工 ──

@router.post("/reports")
def submit_report_api(
    task_code: str = Query(min_length=1),
    good_qty: int = Query(ge=0),
    bad_qty: int = Query(default=0, ge=0),
    remark: str | None = Query(default=None, max_length=500),
    attachment_ids: str | None = Query(default=None, max_length=512),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    task = get_task_by_code(db, task_code=task_code, with_refs=False)
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在")
    assignment = get_assignment(db, task.id, user.id)
    if not assignment:
        raise HTTPException(status_code=403, detail="您未被派工到此任务")
    try:
        sync_assignment_units(db, assignment)
        db.flush()
        if count_draft_units(db, assignment.id) > 0 or count_user_reported_units(db, task.id, user.id
        ) > 0:
            raise HTTPException(status_code=400, detail="本任务已启用逐件报工，请使用逐件报工页面提交")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if task.status == "done":
        raise HTTPException(status_code=400, detail="任务已完成")
    if good_qty + bad_qty <= 0:
        raise HTTPException(status_code=400, detail="合格数+不良数必须大于0")
    try:
        validate_report_qty_limit(
            db,
            task=task,
            user_id=user.id,
            good_qty=good_qty,
            bad_qty=bad_qty)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    report = create_report(
        db,
        task_id=task.id,
        report_user_id=user.id,
        good_qty=good_qty,
        bad_qty=bad_qty,
        remark=remark,
        attachment_ids=attachment_ids)
    create_notification(
        db,
        user_id=user.id,
        title="报工已提交",
        content=f"任务 {task_code} 报工已提交：合格 {good_qty}，不良 {bad_qty}",
        level="info",
        biz_type="report",
        biz_id=report.id)
    from app.services.feishu.notify import notify_report_submitted

    notify_report_submitted(db, report_user_id=user.id,
        process_id=task.process_id,
        title="待审核报工",
        content=f"员工 {user.full_name or user.username} 提交报工：任务 {task_code}，合格 {good_qty}，不良 {bad_qty}",
        biz_type="report",
        biz_id=report.id)
    try:
        from app.services.wecom.notify import notify_report_submitted as wecom_notify_report_submitted

        wecom_notify_report_submitted(db, report_user_id=user.id,
            process_id=task.process_id,
            title="待审核报工",
            content=f"员工 {user.full_name or user.username} 提交报工：任务 {task_code}，合格 {good_qty}，不良 {bad_qty}",
            biz_type="report",
            biz_id=report.id)
    except Exception:
        pass
    try:
        from app.services.dingtalk.notify import notify_report_submitted as dingtalk_notify_report_submitted

        dingtalk_notify_report_submitted(db, report_user_id=user.id,
            process_id=task.process_id,
            title="待审核报工",
            content=f"员工 {user.full_name or user.username} 提交报工：任务 {task_code}，合格 {good_qty}，不良 {bad_qty}",
            biz_type="report",
            biz_id=report.id)
    except Exception:
        pass
    db.commit()

    return ok({
        "id": report.id,
        "status": report.status,
        "good_qty": report.good_qty,
        "bad_qty": report.bad_qty,
        "created_at": report.created_at,
    })

@router.get("/reports")
def my_reports_api(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    from app.crud.report import list_reports
    items = list_reports(db, report_user_id=user.id, offset=offset, limit=limit)
    return ok({
        "items": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "good_qty": r.good_qty,
                "bad_qty": r.bad_qty,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in items
        ]
    })

# ── 工资 ──

@router.get("/salary")
def my_salary_api(
    month: str | None = Query(default=None, max_length=7),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    from app.models.process import Process

    items = get_salary_items(db, user_id=user.id, month=month, offset=offset, limit=limit)
    proc_ids = {s.process_id for s in items}
    proc_map = {}
    if proc_ids:
        procs = db.scalars(select(Process).where(Process.id.in_(proc_ids))).all()
        proc_map = {p.id: p for p in procs}
    return ok({
        "items": [
            {
                "id": s.id,
                "report_id": s.report_id,
                "process_id": s.process_id,
                "process_name": proc_map[s.process_id].name if s.process_id in proc_map else None,
                "unit_price": float(s.unit_price),
                "good_qty": s.good_qty,
                "amount": float(s.amount),
                "month": s.month,
                "created_at": s.created_at,
            }
            for s in items
        ]
    })

@router.get("/salary/summary")
def my_salary_summary_api(
    month: str | None = Query(default=None, max_length=7),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    data = get_salary_summary(db, month=month, user_id=user.id)
    return ok({"items": data})

# ── 首页仪表盘 ──

@router.get("/dashboard/summary")
def my_dashboard_summary_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """员工个人首页仪表盘"""
    data = get_employee_dashboard_summary(db, user_id=user.id)
    return ok(data)
