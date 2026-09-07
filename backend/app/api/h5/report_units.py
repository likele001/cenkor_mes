# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.notification import create_notification
from app.crud.report_unit import (
    get_next_draft_unit,
    get_unit_by_id,
    list_report_units,
    list_units_for_assignment,
    submit_unit,
    sync_assignment_units)
from app.crud.process_flow import (
    auto_bind_piece_to_unit,
    get_flow_context_for_task,
    get_prev_process_task,
    is_first_process_task,
    piece_display_label,
    _prev_process_unit_done,
)
from app.models.task import Task
from app.models.work_order_piece import WorkOrderPiece
from app.services.report_mode_settings import get_sequence_policy, use_unit_report_mode
from app.crud.task import get_task_by_code, get_task_by_id
from app.crud.task_assignment import get_assignment
from app.models.user import User

router = APIRouter()

def _ensure_employee(user: User) -> None:
    roles = {r.code for r in user.roles}
    if not ({"employee", "leader"} & roles):
        raise HTTPException(status_code=403, detail="无权限")

def _unit_out(u, piece: WorkOrderPiece | None = None, *, task_ctx: dict | None = None) -> dict:
    row = {
        "id": u.id,
        "task_id": u.task_id,
        "task_assignment_id": u.task_assignment_id,
        "unit_seq": u.unit_seq,
        "piece_id": u.piece_id,
        "piece_no": piece.piece_no if piece else None,
        "result_type": u.result_type,
        "employee_attachment_ids": u.employee_attachment_ids,
        "qc_attachment_ids": u.qc_attachment_ids,
        "remark": u.remark,
        "status": u.status,
        "submitted_at": u.submitted_at,
        "created_at": u.created_at,
        "updated_at": u.updated_at,
    }
    if piece and piece.product_code:
        row["product_code"] = piece.product_code
        row["unit_label"] = piece_display_label(piece)
    if task_ctx:
        row.update(task_ctx)
    return row

def _task_context_for_unit(db, task) -> dict:
    if not task:
        return {}
    wo = task.work_order if getattr(task, "work_order", None) else None
    if wo and not getattr(wo, "order", None) and wo.order_id:
        from app.models.order import Order

        wo.order = db.get(Order, wo.order_id)
    order = wo.order if wo else None
    sku = wo.sku if wo else None
    proc = task.process if getattr(task, "process", None) else None
    sku_label = None
    if sku:
        sku_label = f"{sku.code} - {sku.name}" if sku.name else sku.code
    return {
        "process_name": proc.name if proc else None,
        "order_code": order.code if order else None,
        "sku_label": sku_label,
    }

def _piece_for_unit(db, unit) -> WorkOrderPiece | None:
    if unit.piece_id:
        return db.get(WorkOrderPiece, unit.piece_id)
    return None

class ReportUnitSubmitIn(BaseModel):
    task_code: str = Field(min_length=1)
    unit_seq: int | None = Field(default=None, ge=1)
    result_type: str = Field(pattern="^(good|bad)$")
    attachment_ids: str = Field(min_length=1, max_length=512)
    remark: str | None = Field(default=None, max_length=500)
    anomaly_confirmed: bool = Field(default=False, description="前端二次确认后传 true，跳过异常检测")

@router.get("/tasks/{task_code}/units")
def task_units_api(
    task_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    if task_code.isdigit():
        task = get_task_by_id(db, task_id=int(task_code), with_refs=False)
    else:
        task = get_task_by_code(db, task_code=task_code, with_refs=False)
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在")
    assignment = get_assignment(db, task.id, user.id)
    if not assignment:
        raise HTTPException(status_code=403, detail="无权限")
    sync_assignment_units(db, assignment)
    db.flush()
    units = list_units_for_assignment(db, assignment.id)
    reported = sum(1 for u in units if u.status in ("submitted", "leader_approved", "qc_approved"))
    draft = sum(1 for u in units if u.status == "draft")
    flow = get_flow_context_for_task(db, task)
    item_rows = []
    for u in units:
        piece = _piece_for_unit(db, u)
        item_rows.append(_unit_out(u, piece))
    return ok(
        {
            "task_code": task.task_code,
            "assigned_qty": assignment.assigned_qty,
            "reported_qty": reported,
            "remaining_qty": draft,
            "flow": flow,
            "items": item_rows,
        }
    )

@router.post("/report-units")
def submit_report_unit_api(
    payload: ReportUnitSubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    if not use_unit_report_mode(db):
        raise HTTPException(status_code=400, detail="当前为批量报工模式，请使用「扫码报工」填写合格/不良数量")
    task = get_task_by_code(db, task_code=payload.task_code.strip(), with_refs=False)
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在")
    if task.status == "done":
        raise HTTPException(status_code=400, detail="任务已完成")
    assignment = get_assignment(db, task.id, user.id)
    if not assignment:
        raise HTTPException(status_code=403, detail="您未被派工到此任务")

    sync_assignment_units(db, assignment)
    if payload.unit_seq:
        from app.models.report_unit import ReportUnit
        from sqlalchemy import select

        unit = db.scalar(
            select(ReportUnit).where(ReportUnit.task_assignment_id == assignment.id,
                ReportUnit.unit_seq == payload.unit_seq)
        )
        if not unit:
            raise HTTPException(status_code=400, detail="件次不存在")
    else:
        unit = get_next_draft_unit(db, assignment.id)
        if not unit:
            raise HTTPException(status_code=400, detail="没有待报工件次")

    if use_unit_report_mode(db):
        try:
            auto_bind_piece_to_unit(db, unit, task)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # ── 柔性顺序：上一道工序未完成时软提示确认（不硬拦）──
    if not payload.anomaly_confirmed and use_unit_report_mode(db) and unit.piece_id:
        if get_sequence_policy(db) == "soft":
            if not is_first_process_task(db, task):
                prev_task = get_prev_process_task(db, task)
                if prev_task and not _prev_process_unit_done(db, prev_task, unit.piece_id):
                    return ok({
                        "anomaly_warning": True,
                        "anomaly_level": "suspect",
                        "anomaly_reason": "上一道工序尚未终审通过，确认继续报工？",
                        "anomaly_detail": {"type": "sequence_soft"},
                    })

    # 原 AI 异常检测（提交前拦截）已随 AI 功能移除，直接进入提交

    try:
        submit_unit(
            db,
            unit=unit,
            result_type=payload.result_type,
            employee_attachment_ids=payload.attachment_ids.strip(),
            remark=payload.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    anomaly_suffix = ""
    if payload.anomaly_confirmed:
        anomaly_suffix = "（已确认异常）"
        from app.crud.automation_log import create_automation_log

        create_automation_log(
            db,
            trigger="manual",
            action="report_anomaly_confirmed",
            status="success",
            biz_type="report_unit",
            biz_id=unit.id,
            message="用户确认异常后继续提交",
            created_by=user.id)
    create_notification(
        db,
        user_id=user.id,
        title="件次报工已提交",
        content=(
            f"任务 {payload.task_code} "
            f"{piece_display_label(_piece_for_unit(db, unit)) or f'第{unit.unit_seq}件'}"
            f"已提交（{payload.result_type}）{anomaly_suffix}"
        ),
        level="info",
        biz_type="report_unit",
        biz_id=unit.id)
    from app.services.feishu.notify import notify_report_submitted

    task = db.get(Task, unit.task_id) if unit.task_id else None
    notify_report_submitted(db, report_user_id=user.id,
        process_id=task.process_id if task else None,
        title="待审核件次报工",
        content=(
            f"员工 {user.full_name or user.username} 提交件次报工：任务 {payload.task_code} "
            f"第{unit.unit_seq}件（{payload.result_type}）{anomaly_suffix}"
        ),
        biz_type="report_unit",
        biz_id=unit.id)
    db.commit()
    piece = _piece_for_unit(db, unit)
    out = _unit_out(unit, piece)
    return ok(out)

@router.get("/report-units")
def my_report_units_api(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    items = list_report_units(db, user_id=user.id, status=status, offset=offset, limit=limit
    )
    return ok(
        {
            "items": [
                {
                    **_unit_out(
                        u,
                        _piece_for_unit(db, u),
                        task_ctx={
                            "task_code": u.task.task_code if u.task else None,
                            **_task_context_for_unit(db, u.task),
                        }),
                }
                for u in items
            ]
        }
    )

@router.get("/report-units/{unit_id}")
def my_report_unit_detail_api(
    unit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_employee(user)
    unit = get_unit_by_id(db, unit_id)
    if not unit or unit.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    return ok(
        {
            **_unit_out(unit, _piece_for_unit(db, unit)),
            "task_code": unit.task.task_code if unit.task else None,
            "audits": [
                {
                    "id": a.id,
                    "audit_level": a.audit_level,
                    "action": a.action,
                    "reason": a.reason,
                    "attachment_ids": a.attachment_ids,
                    "created_at": a.created_at,
                }
                for a in unit.audits
            ],
        }
    )
