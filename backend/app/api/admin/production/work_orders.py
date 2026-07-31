from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.work_order import get_work_order_by_id, list_work_orders
from app.models.sku import Sku
from app.models.user import User
from app.models.work_order import WorkOrder
from app.services.entity_refs import process_ref_dict, product_ref_dict, sku_ref_dict
from app.tasks._sync_excel import make_excel_response
from app.services.product_label_print import build_product_trace_labels_html
from app.services.trace_public import list_label_pieces_for_work_order


router = APIRouter(dependencies=[Depends(require_permissions(["work.manage"]))])


def _task_out(x) -> dict:
    return {
        "id": x.id,
        "work_order_id": x.work_order_id,
        "process_id": x.process_id,
        "seq": x.seq,
        "planned_qty": x.planned_qty,
        "status": x.status,
        "assigned_user_id": x.assigned_user_id,
        "assigned_at": x.assigned_at,
        "assigned_by": x.assigned_by,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
        "process": process_ref_dict(x.process),
    }


def _out(x) -> dict:
    sku = x.sku if hasattr(x, "sku") else None
    product = x.product if hasattr(x, "product") else None
    sku_out = sku_ref_dict(sku, product)
    return {
        "id": x.id,
        "order_id": x.order_id,
        "order_item_id": x.order_item_id,
        "product_id": x.product_id,
        "sku_id": x.sku_id,
        "qty": x.qty,
        "status": x.status,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
        "product": product_ref_dict(product),
        "sku": sku_out,
        "sku_display_label": sku_out["display_label"] if sku_out else None,
    }


@router.get("")
def list_api(
    order_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_work_orders(db, order_id=order_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_out(x) for x in items]})


@router.get("/export")
def export_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_work_orders(db, offset=0, limit=999999)
    rows = []
    for x in items:
        order_code = x.order.code if x.order else ""
        sku_code = x.sku.code if x.sku else ""
        sku_name = x.sku.name if x.sku else ""
        rows.append([x.code, order_code, sku_code, sku_name, x.qty, x.status, str(x.created_at) if x.created_at else ""])
    return make_excel_response(
        headers=["工单号", "订单号", "型号编码", "型号名称", "数量", "状态", "创建时间"],
        rows=rows,
        filename="work_orders.xlsx",
        sheet_name="工单",
    )


@router.get("/{work_order_id}")
def get_api(
    work_order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_work_order_by_id(db, work_order_id=work_order_id, with_tasks=True)
    if not item:
        raise HTTPException(status_code=400, detail="工单不存在")
    data = _out(item)
    data["tasks"] = [_task_out(x) for x in item.tasks]
    return ok(data)


class ProductLabelPrintIn(BaseModel):
    piece_ids: list[int] = Field(default_factory=list)
    piece_no_from: int | None = Field(default=None, ge=1)
    piece_no_to: int | None = Field(default=None, ge=1)


def _get_work_order_for_print(db: Session, work_order_id: int) -> WorkOrder | None:
    return db.scalar(
        select(WorkOrder)
        .where(WorkOrder.id == work_order_id)
        .options(
            selectinload(WorkOrder.sku).selectinload(Sku.product),
            selectinload(WorkOrder.product),
        )
    )


@router.get("/{work_order_id}/print-product-labels")
def print_product_labels_api(
    work_order_id: int,
    piece_no_from: int | None = Query(default=None, ge=1),
    piece_no_to: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wo = _get_work_order_for_print(db, work_order_id)
    if not wo:
        raise HTTPException(status_code=400, detail="工单不存在")
    pieces = list_label_pieces_for_work_order(db, work_order_id,
        piece_no_from=piece_no_from,
        piece_no_to=piece_no_to,
    )
    html = build_product_trace_labels_html(db, wo, pieces)
    return ok({"html": html, "count": len(pieces), "work_order_id": work_order_id})


@router.post("/{work_order_id}/print-product-labels")
def print_product_labels_post_api(
    work_order_id: int,
    payload: ProductLabelPrintIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wo = _get_work_order_for_print(db, work_order_id)
    if not wo:
        raise HTTPException(status_code=400, detail="工单不存在")
    pieces = list_label_pieces_for_work_order(db, work_order_id,
        piece_no_from=payload.piece_no_from,
        piece_no_to=payload.piece_no_to,
        piece_ids=payload.piece_ids or None,
    )
    html = build_product_trace_labels_html(db, wo, pieces)
    return ok({"html": html, "count": len(pieces), "work_order_id": work_order_id})
