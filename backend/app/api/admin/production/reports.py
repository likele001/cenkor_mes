from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.notification import create_notification
from app.crud.report import (
    calc_and_create_salary,
    create_audit,
    get_report_by_id,
    get_salary_items,
    get_salary_summary,
    list_reports,
    update_report_status,
)
from app.crud.task import get_task_by_id
from app.crud.trace import generate_trace_code
from app.models.task import Task
from app.models.work_order import WorkOrder
from app.models.user import User
from app.schemas.salary import SalaryAllowanceCreateIn
from app.services.mold_shot_tracker import increment_mold_shots_for_task


router = APIRouter(dependencies=[Depends(require_permissions(["report.audit"]))])


def _report_out(x) -> dict:
    return {
        "id": x.id,
        "task_id": x.task_id,
        "report_user_id": x.report_user_id,
        "good_qty": x.good_qty,
        "bad_qty": x.bad_qty,
        "remark": x.remark,
        "attachment_ids": x.attachment_ids,
        "status": x.status,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
        "task": (
            {
                "id": x.task.id,
                "task_code": x.task.task_code,
                "process_id": x.task.process_id,
            }
            if hasattr(x, "task") and x.task
            else None
        ),
        "report_user": (
            {"id": x.report_user.id, "full_name": x.report_user.full_name}
            if hasattr(x, "report_user") and x.report_user
            else None
        ),
    }


@router.get("")
def list_api(
    task_id: int | None = Query(default=None, ge=1),
    report_user_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    pending_audit: bool = Query(default=False, description="仅返回待审（submitted/leader_approved）"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_reports(
        db,
        task_id=task_id, report_user_id=report_user_id,
        status=status, pending_audit=pending_audit, offset=offset, limit=limit,
    )
    return ok({
        "items": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "report_user_id": r.report_user_id,
                "good_qty": r.good_qty,
                "bad_qty": r.bad_qty,
                "remark": r.remark,
                "attachment_ids": r.attachment_ids,
                "status": r.status,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "report_user": (
                    {"id": r.report_user.id, "full_name": r.report_user.full_name}
                    if hasattr(r, "report_user") and r.report_user
                    else None
                ),
                "task": (
                    {
                        "id": r.task.id,
                        "task_code": r.task.task_code,
                        "process_id": r.task.process_id,
                    }
                    if hasattr(r, "task") and r.task
                    else None
                ),
            }
            for r in items
        ]
    })


@router.get("/{report_id}")
def get_api(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_report_by_id(db, report_id=report_id)
    if not item:
        raise HTTPException(status_code=400, detail="报工记录不存在")
    data = _report_out(item)
    data["audits"] = [
        {
            "id": a.id,
            "auditor_id": a.auditor_id,
            "audit_level": a.audit_level,
            "action": a.action,
            "reason": a.reason,
            "created_at": a.created_at,
        }
        for a in item.audits
    ]
    return ok(data)


@router.post("/{report_id}/leader-approve")
def leader_approve_api(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = get_report_by_id(db, report_id=report_id)
    if not report:
        raise HTTPException(status_code=400, detail="报工记录不存在")
    if report.status != "submitted":
        raise HTTPException(status_code=400, detail="报工状态不允许操作")
    create_audit(db, report_id=report.id,
                 auditor_id=user.id, audit_level="leader", action="approve", reason=None)
    update_report_status(db, report, "leader_approved")
    create_notification(
        db,
        user_id=report.report_user_id,
        title="报工已初审通过",
        content=f"报工 {report.id} 已由班组长初审通过",
        level="info",
        biz_type="report",
        biz_id=report.id,
        feishu_event="report.leader_approved",
    )
    db.commit()
    return ok({"report_id": report.id, "status": "leader_approved"})


@router.post("/{report_id}/qc-approve")
def qc_approve_api(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = get_report_by_id(db, report_id=report_id)
    if not report:
        raise HTTPException(status_code=400, detail="报工记录不存在")
    if report.status != "leader_approved":
        raise HTTPException(status_code=400, detail="报工状态不允许终审操作")
    create_audit(db, report_id=report.id,
                 auditor_id=user.id, audit_level="qc", action="approve", reason=None)
    update_report_status(db, report, "qc_approved")

    # 审核通过 → 自动生成工资明细 + 追溯码
    salary = calc_and_create_salary(db, report=report)

    # 模具模次自动累加
    task = db.get(Task, report.task_id)
    if task:
        increment_mold_shots_for_task(db, process_id=task.process_id, qty=report.good_qty)

    # 生成追溯码
    trace_code = None
    if task:
        wo = db.get(WorkOrder, task.work_order_id)
        if wo:
            trace_code = generate_trace_code(
                db,
                order_id=wo.order_id,
                sku_id=wo.sku_id,
                process_id=task.process_id,
                user_id=report.report_user_id,
                report_id=report.id,
                qty=report.good_qty,
            )
    create_notification(
        db,
        user_id=report.report_user_id,
        title="报工已终审通过",
        content=f"报工 {report.id} 已终审通过，计件金额 {float(salary.amount) if salary else 0:.2f}",
        level="info",
        biz_type="report",
        biz_id=report.id,
        feishu_event="report.qc_approved",
    )
    db.commit()
    return ok({
        "report_id": report.id,
        "status": "qc_approved",
        "salary_generated": salary is not None,
        "salary_amount": float(salary.amount) if salary else None,
        "trace_code": trace_code.code if trace_code else None,
    })


@router.post("/{report_id}/reject")
def reject_api(
    report_id: int,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = get_report_by_id(db, report_id=report_id)
    if not report:
        raise HTTPException(status_code=400, detail="报工记录不存在")
    if report.status not in ("submitted", "leader_approved"):
        raise HTTPException(status_code=400, detail="报工状态不允许驳回")
    create_audit(db, report_id=report.id,
                 auditor_id=user.id, audit_level="qc", action="reject", reason=reason)
    update_report_status(db, report, "rejected")
    create_notification(
        db,
        user_id=report.report_user_id,
        title="报工被驳回",
        content=f"报工 {report.id} 被驳回：{reason or '无原因'}",
        level="warning",
        biz_type="report",
        biz_id=report.id,
        feishu_event="report.rejected",
    )
    db.commit()
    return ok({"report_id": report.id, "status": "rejected"})


# ── 工资 ──

@router.get("/salary/items")
def salary_items_api(
    user_id: int | None = Query(default=None, ge=1),
    month: str | None = Query(default=None, max_length=7),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = get_salary_items(
        db,
        user_id=user_id, month=month,
        offset=offset, limit=limit,
    )
    return ok({
        "items": [
            {
                "id": s.id,
                "report_id": s.report_id,
                "user_id": s.user_id,
                "sku_id": s.sku_id,
                "process_id": s.process_id,
                "unit_price": float(s.unit_price),
                "good_qty": s.good_qty,
                "amount": float(s.amount),
                "month": s.month,
                "created_at": s.created_at,
            }
            for s in items
        ]
    })


# ── 补贴/扣款 ──

@router.get("/salary/allowances")
def salary_allowances_api(
    user_id: int | None = Query(default=None, ge=1),
    month: str | None = Query(default=None, max_length=7),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models.salary_allowance import SalaryAllowance
    from sqlalchemy import select
    stmt = select(SalaryAllowance)
    if user_id is not None:
        stmt = stmt.where(SalaryAllowance.user_id == user_id)
    if month:
        stmt = stmt.where(SalaryAllowance.month == month)
    stmt = stmt.order_by(SalaryAllowance.id.desc())
    items = db.scalars(stmt).all()
    return ok({"items": [{"id": a.id, "user_id": a.user_id, "allowance_type": a.allowance_type,
            "amount": float(a.amount), "month": a.month, "reason": a.reason, "created_at": a.created_at} for a in items]})


@router.post("/salary/allowances")
def create_allowance_api(
    payload: SalaryAllowanceCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models.salary_allowance import SalaryAllowance
    from decimal import Decimal
    a = SalaryAllowance(
        user_id=payload.user_id,
        allowance_type=payload.allowance_type,
        amount=Decimal(str(payload.amount)),
        month=payload.month,
        reason=payload.reason,
        created_by=user.id,
    )
    db.add(a)
    db.commit()
    return ok({"id": a.id, "allowance_type": a.allowance_type, "amount": float(a.amount)})


@router.get("/salary/summary")
def salary_summary_api(
    month: str | None = Query(default=None, max_length=7),
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = get_salary_summary(db, month=month, user_id=user_id)
    return ok({"items": data})
