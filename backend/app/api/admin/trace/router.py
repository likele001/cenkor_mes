from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from sqlalchemy import select

from app.crud.process_flow import build_flow_chain_rows, get_piece_by_product_code
from app.crud.trace import get_trace_by_code, list_trace_codes
from app.models.salary import SalaryItem
from app.models.user import User
from app.services.trace_public import build_trace_public_url, trace_qr_payload, _collect_media_for_piece


router = APIRouter(dependencies=[Depends(require_permissions(["trace.query"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "product_code": x.product_code,
        "order_id": x.order_id,
        "sku_id": x.sku_id,
        "process_id": x.process_id,
        "report_id": x.report_id,
        "user_id": x.user_id,
        "qty": x.qty,
        "remark": x.remark,
        "created_at": x.created_at,
    }


@router.get("")
def list_api(
    order_id: int | None = Query(default=None, ge=1),
    sku_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_trace_codes(
        db,
        order_id=order_id, sku_id=sku_id,
        offset=offset, limit=limit,
    )
    return ok({"items": [_out(x) for x in items]})


@router.get("/{code}")
def trace_api(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tc = get_trace_by_code(db, code=code)
    if not tc:
        raise HTTPException(status_code=400, detail="追溯码不存在")

    order = tc.order
    sku = tc.sku
    proc = tc.process
    report = tc.report
    report_unit = tc.report_unit
    ruser = tc.user

    salary_info = None
    stmt = select(SalaryItem)
    if tc.report_unit_id:
        stmt = stmt.where(SalaryItem.report_unit_id == tc.report_unit_id)
    elif tc.report_id:
        stmt = stmt.where(SalaryItem.report_id == tc.report_id)
    si = db.scalar(stmt.limit(1))
    if si:
        salary_info = {
            "id": si.id,
            "amount": float(si.amount),
            "unit_price": float(si.unit_price),
            "good_qty": si.good_qty,
            "month": si.month,
        }

    audit_rows = []
    if report:
        audit_rows = list(report.audits)
    elif report_unit:
        audit_rows = list(report_unit.audits)

    piece = tc.piece
    if not piece:
        lookup = (tc.product_code or code).strip().upper()
        if lookup.startswith("FP"):
            piece = get_piece_by_product_code(db, lookup)

    product_code = piece.product_code if piece else tc.product_code
    flow_chain = build_flow_chain_rows(db, piece, tc)
    piece_no = piece.piece_no if piece else None
    public_code = product_code or tc.code

    return ok({
        "trace_code": public_code,
        "product_code": product_code,
        "public_trace_url": build_trace_public_url(public_code),
        "piece_id": tc.piece_id,
        "piece_no": piece_no,
        "work_order_id": tc.work_order_id,
        "task_seq": tc.task_seq,
        "flow_chain": flow_chain,
        "qty": tc.qty,
        "remark": tc.remark,
        "created_at": tc.created_at,
        "order": {
            "id": order.id,
            "code": order.code,
            "status": order.status,
            "created_at": order.created_at,
        } if order else None,
        "sku": {
            "id": sku.id,
            "code": sku.code,
            "name": sku.name,
        } if sku else None,
        "process": {
            "id": proc.id,
            "code": proc.code,
            "name": proc.name,
        } if proc else None,
        "report": {
            "id": report.id,
            "good_qty": report.good_qty,
            "bad_qty": report.bad_qty,
            "status": report.status,
            "created_at": report.created_at,
        } if report else None,
        "report_unit": {
            "id": report_unit.id,
            "unit_seq": report_unit.unit_seq,
            "result_type": report_unit.result_type,
            "status": report_unit.status,
            "submitted_at": report_unit.submitted_at,
        } if report_unit else None,
        "report_user": {
            "id": ruser.id,
            "full_name": ruser.full_name,
            "username": ruser.username,
        } if ruser else None,
        "audits": [
            {
                "audit_level": a.audit_level,
                "action": a.action,
                "reason": a.reason,
                "created_at": a.created_at,
            }
            for a in audit_rows
        ],
        "salary": salary_info,
        "media": _collect_media_for_piece(db, piece.id, product_code=public_code) if piece else [],
        "qr": trace_qr_payload(public_code),
    })
