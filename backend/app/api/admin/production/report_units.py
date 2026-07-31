from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.notification import create_notification
from app.crud.attachment import get_attachments_by_ids
from app.crud.report_unit import (
    _parse_attachment_ids,
    calc_and_create_salary_for_unit,
    create_unit_audit,
    get_unit_by_id,
    list_report_units,
    reset_unit_to_draft)
from app.crud.task import get_task_by_id
from app.crud.process_flow import (
    ensure_unit_piece_on_qc_approve,
    is_first_process_task,
    piece_display_label,
    void_piece_if_bad_first_process)
from app.models.work_order_piece import WorkOrderPiece
from app.crud.trace import generate_process_trace_event, generate_trace_code
from app.crud.warehouse import adjust_stock
from app.models.warehouse import Warehouse
from app.services.attachment_media import attachment_play_url
from app.services.report_mode_settings import use_unit_report_mode
from app.services.mold_shot_tracker import increment_mold_shots_for_task
from app.crud.quality import (
    create_inspection_records,
    find_template_for_process,
    get_inspection_records_for_audit)
from app.models.report_unit import ReportUnit
from app.models.task import Task
from app.models.user import User
from app.tasks._sync_excel import make_excel_response
from app.models.work_order import WorkOrder
from app.services.approval_flow_resolver import (
    get_next_step,
    get_status_after_approval,
    get_report_approval_steps,
    is_terminal_status,
    format_step_label)

router = APIRouter(prefix="/report-units", dependencies=[Depends(require_permissions(["report.audit"]))])

class InspectionResultIn(BaseModel):
    template_item_id: int
    result: str = Field(default="pass", pattern="^(pass|fail|na)$")
    measured_value: str | None = Field(default=None, max_length=64)
    defect_code_id: int | None = Field(default=None)
    remark: str | None = Field(default=None, max_length=500)

class QcApproveIn(BaseModel):
    qc_attachment_ids: str = Field(default="", max_length=512)
    inspection_results: list[InspectionResultIn] = Field(default_factory=list)
    remark: str | None = Field(default=None, max_length=500)

def _attachments_meta(db: Session, raw: str | None) -> list[dict]:
    ids = _parse_attachment_ids(raw)
    rows = get_attachments_by_ids(db, ids)
    return [
        {
            "id": a.id,
            "content_type": a.content_type,
            "original_filename": a.original_filename,
            "size": a.size,
            "play_url": attachment_play_url(a, db=db),
        }
        for a in rows
    ]

def _unit_list_out(u: ReportUnit) -> dict:
    prescreen = None
    if u.prescreen_level or u.prescreen_json:
        prescreen = {
            "level": u.prescreen_level,
            "score": None,
            "reasons": [],
            "auto_pass": False,
        }
        if u.prescreen_json:
            try:
                import json as _json
                pj = _json.loads(u.prescreen_json)
                prescreen["score"] = pj.get("score")
                prescreen["reasons"] = pj.get("reasons") or []
                prescreen["auto_pass"] = bool(pj.get("auto_pass"))
            except Exception:
                prescreen["raw_json"] = u.prescreen_json
    return {
        "id": u.id,
        "task_id": u.task_id,
        "task_assignment_id": u.task_assignment_id,
        "user_id": u.user_id,
        "unit_seq": u.unit_seq,
        "result_type": u.result_type,
        "employee_attachment_ids": u.employee_attachment_ids,
        "qc_attachment_ids": u.qc_attachment_ids,
        "remark": u.remark,
        "status": u.status,
        "prescreen_level": u.prescreen_level,
        "prescreen_json": u.prescreen_json,
        "prescreen_at": u.prescreen_at,
        "prescreen": prescreen,
        "submitted_at": u.submitted_at,
        "created_at": u.created_at,
        "updated_at": u.updated_at,
        "task": (
            {
                "id": u.task.id,
                "task_code": u.task.task_code,
                "process_id": u.task.process_id,
                "process_name": u.task.process.name if u.task.process else None,
            }
            if u.task
            else None
        ),
        "report_user": (
            {"id": u.user.id, "full_name": u.user.full_name}
            if u.user
            else None
        ),
        "product": (
            {"id": u.task.work_order.sku.id, "name": u.task.work_order.sku.name, "code": u.task.work_order.sku.code}
            if u.task and u.task.work_order and u.task.work_order.sku
            else None
        ),
        "order": (
            {"id": u.task.work_order.order.id, "code": u.task.work_order.order.code}
            if u.task and u.task.work_order and u.task.work_order.order
            else None
        ),
    }

@router.get("")
def list_api(
    task_id: int | None = Query(default=None, ge=1),
    user_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    prescreen_level: str | None = Query(default=None),
    pending_audit: bool = Query(default=False, description="仅返回待审（submitted/leader_approved），排除 draft 等"),
    risk_first: bool = Query(default=False, description="高风险优先排序"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    items = list_report_units(db, task_id=task_id,
        user_id=user_id,
        status=status,
        prescreen_level=prescreen_level,
        risk_first=risk_first,
        pending_audit=pending_audit,
        offset=offset,
        limit=limit)
    count_filters = []
    if task_id:
        count_filters.append(ReportUnit.task_id == task_id)
    if user_id:
        count_filters.append(ReportUnit.user_id == user_id)
    if pending_audit:
        count_filters.append(ReportUnit.status.in_(("submitted", "leader_approved")))
    elif status:
        count_filters.append(ReportUnit.status == status)
    if prescreen_level:
        count_filters.append(ReportUnit.prescreen_level == prescreen_level)
    total = db.scalar(select(func.count(ReportUnit.id)).where(*count_filters))
    return ok({"items": [_unit_list_out(u) for u in items], "total": int(total or 0)})

@router.get("/export")
def export_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    items = list_report_units(db, offset=0, limit=999999)
    rows = []
    for u in items:
        task_code = u.task.task_code if u.task else ""
        process_name = u.task.process.name if u.task and u.task.process else ""
        user_name = u.user.full_name if u.user else ""
        rows.append([
            task_code,
            process_name,
            user_name,
            u.result_type or "",
            1 if u.result_type == "good" else 0,
            1 if u.result_type == "bad" else 0,
            str(u.created_at) if u.created_at else "",
        ])
    return make_excel_response(
        headers=["任务编码", "工序名称", "员工姓名", "结果类型", "良品数", "不良数", "创建时间"],
        rows=rows,
        filename="report_units.xlsx",
        sheet_name="报工件次")

@router.get("/approval-steps")
def get_approval_steps_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """Get the configured approval steps for report audit."""
    steps = get_report_approval_steps(db)
    return ok({"steps": steps})

@router.get("/{unit_id}")
def get_api(
    unit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    unit = get_unit_by_id(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="报工件次不存在")
    data = _unit_list_out(unit)
    data["employee_attachments"] = _attachments_meta(db, unit.employee_attachment_ids)
    data["qc_attachments"] = _attachments_meta(db, unit.qc_attachment_ids)
    data["audits"] = [
        {
            "id": a.id,
            "auditor_id": a.auditor_id,
            "audit_level": a.audit_level,
            "action": a.action,
            "attachment_ids": a.attachment_ids,
            "reason": a.reason,
            "created_at": a.created_at,
        }
        for a in unit.audits
    ]
    return ok(data)

@router.post("/{unit_id}/approve")
def approve_api(
    unit_id: int,
    payload: QcApproveIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """Approve a report unit at the current step. Dynamically resolves which step this is."""
    unit = get_unit_by_id(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="报工件次不存在")

    audit_count = len([a for a in unit.audits if a.action == "approve"])
    next_step = get_next_step(db, audit_count)
    if not next_step:
        raise HTTPException(status_code=400, detail="该件次已全部审核通过")

    step_index = audit_count
    total_steps = len(get_report_approval_steps(db))
    is_last_step = step_index >= total_steps - 1
    step_role = next_step["approver_role"]

    # Status validation
    if unit.status not in ("submitted", "leader_approved") and not unit.status.startswith("step_"):
        raise HTTPException(status_code=400, detail="状态不允许审核")

    # If last step (terminal), require QC attachments
    if is_last_step:
        if not payload or not payload.qc_attachment_ids.strip():
            raise HTTPException(status_code=400, detail="终审请上传至少1个审核图片或视频")

    # ── Save inspection results (only for last step) ──
    auto_rejected = False
    if is_last_step and payload and payload.inspection_results:
        task = db.get(Task, unit.task_id) if unit.task_id else None
        if task:
            tmpl = find_template_for_process(db, task.process_id)
            if tmpl:
                audit = create_unit_audit(
                    db,
                    report_unit_id=unit.id,
                    auditor_id=user.id,
                    audit_level=step_role,
                    action="approve",
                    reason=None,
                    attachment_ids=payload.qc_attachment_ids.strip() if payload else None)
                create_inspection_records(db, audit.id, payload.inspection_results)

                critical_fails = [
                    r for r in payload.inspection_results
                    if r.result == "fail" and r.defect_code_id
                ]
                if critical_fails:
                    from app.crud.quality import get_defect_code
                    critical_defects = [
                        r for r in critical_fails
                        if get_defect_code(db, r.defect_code_id)
                        and get_defect_code(db, r.defect_code_id).severity == "critical"
                    ]
                    if critical_defects:
                        audit.action = "reject"
                        unit.status = "draft"
                        reset_unit_to_draft(db, unit)
                        create_notification(
                            db,
                            user_id=unit.user_id,
                            title="件次报工被驳回（质检不合格）",
                            content=f"第{unit.unit_seq}件存在致命缺陷，请重新报工",
                            level="warning",
                            biz_type="report_unit",
                            biz_id=unit.id,
                            feishu_event="report.rejected")
                        db.commit()
                        return ok({"id": unit.id, "status": unit.status, "auto_rejected": True, "step_index": step_index})

    # ── Save admin remark ──
    if payload and payload.remark:
        unit.remark = payload.remark

    # ── Create audit record ──
    audit = create_unit_audit(
        db,
        report_unit_id=unit.id,
        auditor_id=user.id,
        audit_level=step_role,
        action="approve",
        reason=None,
        attachment_ids=payload.qc_attachment_ids.strip() if is_last_step and payload else None)

    # Save inspection results if not already saved above
    if is_last_step and payload and payload.inspection_results and not auto_rejected:
        existing = get_inspection_records_for_audit(db, audit.id)
        if not existing:
            create_inspection_records(db, audit.id, payload.inspection_results)

    # ── Update status ──
    new_status = get_status_after_approval(db, audit_count)
    unit.status = new_status

    if payload and payload.qc_attachment_ids.strip():
        # Append to existing qc_attachment_ids if any
        existing = unit.qc_attachment_ids or ""
        if existing:
            unit.qc_attachment_ids = existing + "," + payload.qc_attachment_ids.strip()
        else:
            unit.qc_attachment_ids = payload.qc_attachment_ids.strip()

    # ── Terminal step: salary, trace, stock ──
    if is_terminal_status(new_status):
        salary = calc_and_create_salary_for_unit(db, unit)
        trace_code = None
        task = db.get(Task, unit.task_id)
        piece = db.get(WorkOrderPiece, unit.piece_id) if unit.piece_id else None
        unit_label = piece_display_label(piece) or f"第{unit.unit_seq}件"

        if unit.result_type == "bad" and use_unit_report_mode(db) and task:
            void_piece_if_bad_first_process(db, unit, task)

        if unit.result_type == "good" and task:
            increment_mold_shots_for_task(db, process_id=task.process_id, qty=1)

        if unit.result_type == "good" and use_unit_report_mode(db):
            if task:
                wo = db.get(WorkOrder, task.work_order_id)
                if wo:
                    try:
                        piece_id, product_code = ensure_unit_piece_on_qc_approve(db, unit, task, wo
                        )
                    except ValueError as e:
                        raise HTTPException(status_code=400, detail=str(e)) from e
                    if product_code:
                        if is_first_process_task(db, task):
                            trace_code = generate_trace_code(
                                db, order_id=wo.order_id,
                                sku_id=wo.sku_id, process_id=task.process_id,
                                user_id=unit.user_id, product_code=product_code,
                                work_order_id=wo.id, piece_id=piece_id,
                                task_seq=int(task.seq), report_unit_id=unit.id, qty=1)
                        else:
                            trace_code = generate_process_trace_event(db, product_code=product_code,
                                order_id=wo.order_id, sku_id=wo.sku_id,
                                process_id=task.process_id, user_id=unit.user_id,
                                work_order_id=wo.id, piece_id=piece_id,
                                task_seq=int(task.seq), report_unit_id=unit.id)

        # Auto stock-in for good units
        if unit.result_type == "good" and use_unit_report_mode(db):
            if task:
                wo = db.get(WorkOrder, task.work_order_id)
                if wo:
                    warehouse = db.scalar(
                        select(Warehouse).where(Warehouse.is_active.is_(True)
                        ).order_by(Warehouse.id.asc()).limit(1)
                    )
                    if warehouse:
                        adjust_stock(
                            db, warehouse_id=warehouse.id,
                            sku_id=wo.sku_id, change_qty=1, biz_type="produce_in",
                            biz_id=unit.id, remark=f"工单#{wo.id} 件次#{unit.unit_seq} 终审通过自动入库")

        step_label = format_step_label(next_step, step_index, total_steps)
        create_notification(
            db, user_id=unit.user_id,
            title="件次报工已终审通过",
            content=(
                f"{unit_label}已终审通过"
                + (f"，成品码 {trace_code.product_code}" if trace_code and trace_code.product_code else "")
                + f"，计件 {float(salary.amount) if salary else 0:.2f} 元"
            ),
            level="info", biz_type="report_unit", biz_id=unit.id,
            feishu_event="report.qc_approved")
        db.commit()
        return ok({
            "id": unit.id, "status": unit.status, "step_index": step_index,
            "salary_generated": salary is not None,
            "salary_amount": float(salary.amount) if salary else None,
            "trace_code": trace_code.code if trace_code else None,
            "product_code": trace_code.product_code if trace_code else None,
        })

    # ── Non-terminal step ──
    step_label = format_step_label(next_step, step_index, total_steps)
    create_notification(
        db, user_id=unit.user_id,
        title=f"件次报工已通过（{step_label}）",
        content=f"任务件次 #{unit.unit_seq} 已通过 {step_label}",
        level="info", biz_type="report_unit", biz_id=unit.id,
        feishu_event="report.leader_approved")
    db.commit()
    return ok({"id": unit.id, "status": unit.status, "step_index": step_index})

@router.post("/{unit_id}/reject")
def reject_api(
    unit_id: int,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    unit = get_unit_by_id(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="报工件次不存在")
    if unit.status not in ("submitted", "leader_approved"):
        raise HTTPException(status_code=400, detail="状态不允许驳回")
    create_unit_audit(
        db,
        report_unit_id=unit.id,
        auditor_id=user.id,
        audit_level="qc",
        action="reject",
        reason=reason)
    reset_unit_to_draft(db, unit)
    create_notification(
        db,
        user_id=unit.user_id,
        title="件次报工被驳回",
        content=f"第{unit.unit_seq}件被驳回：{reason or '无原因'}，请重新报工",
        level="warning",
        biz_type="report_unit",
        biz_id=unit.id,
        feishu_event="report.rejected")
    db.commit()
    return ok({"id": unit.id, "status": unit.status})
