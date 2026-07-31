"""客户公开溯源：URL、二维码、脱敏详情"""

from __future__ import annotations

import re
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.services.attachment_media import attachment_play_url
from app.crud.attachment import get_attachments_by_ids
from app.crud.report_unit import _parse_attachment_ids
from app.crud.process_flow import build_flow_chain_rows, get_piece_by_product_code, list_pieces_for_work_order
from app.crud.trace import get_trace_by_code, TRACE_TASK_SEQ_ORDER
from app.models.customer import Customer
from app.models.order import Order
from app.models.product import Product
from app.models.report_unit import ReportUnit
from app.models.sku import Sku
from app.models.trace import TraceCode
from app.models.work_order import WorkOrder
from app.models.work_order_piece import WorkOrderPiece
from app.services.task_qr import make_qr_svg


def build_trace_public_url(code: str, tenant_code: str | None = None) -> str:
    """
    客户扫码打开的 H5 溯源页。
    兼容旧站 trace.html?id= 写法（index.html 会跳转 #/trace）。
    """
    normalized = (code or "").strip()
    if not normalized:
        return ""
    base = (getattr(settings, "H5_PUBLIC_BASE_URL", None) or settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if not base:
        return normalized
    q = f"id={quote(normalized, safe='')}"
    tc = (tenant_code or "").strip()
    if tc:
        q += f"&tenant={quote(tc, safe='')}"
    return f"{base}/trace.html?{q}"


def trace_qr_payload(code: str, tenant_code: str | None = None) -> dict:
    url = build_trace_public_url(code, tenant_code)
    text = url or (code or "").strip()
    return {
        "code": (code or "").strip().upper(),
        "text": text,
        "trace_url": url,
        "svg": make_qr_svg(text),
    }


def _mask_user_name(full_name: str | None, username: str | None) -> str:
    name = (full_name or username or "").strip()
    if not name:
        return "—"
    if len(name) <= 1:
        return name
    return name[0] + "*" * (len(name) - 1)


def _collect_media_for_piece(db: Session, piece_id: int, *, product_code: str) -> list[dict]:
    units = db.scalars(
        select(ReportUnit)
        .where(
            ReportUnit.piece_id == piece_id,
            ReportUnit.status == "qc_approved",
        )
        .order_by(ReportUnit.id.asc())
    ).all()
    seen: set[int] = set()
    out: list[dict] = []
    for unit in units:
        ids: list[int] = []
        for raw in (unit.qc_attachment_ids, unit.employee_attachment_ids):
            ids.extend(_parse_attachment_ids(raw))
        for att in get_attachments_by_ids(db, ids):
            if att.id in seen:
                continue
            seen.add(att.id)
            kind = "video" if (att.content_type or "").startswith("video/") else "image"
            out.append(
                {
                    "id": att.id,
                    "kind": kind,
                    "content_type": att.content_type,
                    "original_filename": att.original_filename,
                    "url": attachment_play_url(att, db=db, public_trace_code=product_code),
                }
            )
    return out


def _resolve_piece_and_trace(db: Session, code: str) -> tuple[WorkOrderPiece | None, TraceCode | None]:
    normalized = code.strip().upper()
    piece = get_piece_by_product_code(db, normalized)
    trace = get_trace_by_code(db, normalized)
    if piece:
        return piece, trace
    if trace and trace.piece_id:
        piece = db.get(WorkOrderPiece, trace.piece_id)
    return piece, trace


def build_public_trace_detail(db: Session, code: str) -> dict | None:
    piece, trace = _resolve_piece_and_trace(db, code)
    if not piece and not trace:
        return None

    product_code = (piece.product_code if piece else None) or (trace.product_code if trace else None) or code.strip().upper()
    wo_id = piece.work_order_id if piece else (trace.work_order_id if trace else None)
    wo = db.get(WorkOrder, wo_id) if wo_id else None
    order = db.get(Order, wo.order_id) if wo else (db.get(Order, trace.order_id) if trace else None)
    sku = db.get(Sku, wo.sku_id) if wo else (db.get(Sku, trace.sku_id) if trace else None)
    product = db.get(Product, sku.product_id) if sku and sku.product_id else None
    customer = db.get(Customer, order.customer_id) if order and order.customer_id else None

    anchor = trace
    if not anchor and piece:
        anchor = db.scalar(
            select(TraceCode)
            .where(TraceCode.piece_id == piece.id)
            .order_by(*TRACE_TASK_SEQ_ORDER)
            .limit(1)
        )

    flow_chain = build_flow_chain_rows(db, piece, anchor) if anchor else []
    flow_steps = [
        {
            "process_name": row.get("process_name"),
            "operator": _mask_user_name(row.get("user_full_name"), row.get("username")),
            "time": row.get("created_at"),
            "trace_code": row.get("trace_code"),
        }
        for row in flow_chain
    ]

    media: list[dict] = []
    if piece:
        media = _collect_media_for_piece(db, piece.id, product_code=product_code)

    return {
        "product_code": product_code,
        "piece_no": piece.piece_no if piece else None,
        "product_name": product.name if product else (sku.name if sku else None),
        "product_code_display": product.code if product else (sku.code if sku else None),
        "sku_name": sku.name if sku else None,
        "sku_code": sku.code if sku else None,
        "order_code": order.code if order else None,
        "order_name": order.code if order else None,
        "customer_name": customer.name if customer else None,
        "work_order_id": wo.id if wo else None,
        "flow_steps": flow_steps,
        "media": media,
        "generated_at": anchor.created_at if anchor else None,
    }


def list_label_pieces_for_work_order(
    db: Session,
    work_order_id: int,
    *,
    piece_no_from: int | None = None,
    piece_no_to: int | None = None,
    piece_ids: list[int] | None = None,
) -> list[WorkOrderPiece]:
    from app.crud.process_flow import ensure_work_order_piece_pool

    wo = db.scalar(
        select(WorkOrder)
        .where(WorkOrder.id == work_order_id)
        .options(selectinload(WorkOrder.order), selectinload(WorkOrder.sku), selectinload(WorkOrder.product))
    )
    if not wo:
        return []
    ensure_work_order_piece_pool(db, wo.id, wo.qty)
    pieces = list_pieces_for_work_order(db, wo.id)
    if piece_ids:
        wanted = {int(x) for x in piece_ids if int(x) > 0}
        pieces = [p for p in pieces if p.id in wanted]
    if piece_no_from is not None:
        pieces = [p for p in pieces if p.piece_no >= int(piece_no_from)]
    if piece_no_to is not None:
        pieces = [p for p in pieces if p.piece_no <= int(piece_no_to)]
    return [p for p in pieces if p.product_code and p.status != "void"]
