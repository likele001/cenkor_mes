from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.mrp import compute_mrp, get_plan_by_id, list_plans
from app.models.user import User
from app.schemas.mrp import MrpComputeRequest

router = APIRouter()


def _item_out(item) -> dict:
    wo = item.work_order
    order = item.order
    sku = item.sku
    mat = item.material
    sup = item.supplier
    return {
        "id": item.id,
        "work_order_id": item.work_order_id,
        "order_id": item.order_id,
        "sku_id": item.sku_id,
        "material_id": item.material_id,
        "bom_id": item.bom_id,
        "bom_scope": item.bom_scope,
        "wo_qty": item.wo_qty,
        "qty_per": item.qty_per,
        "gross_qty": item.gross_qty,
        "stock_qty": item.stock_qty,
        "net_qty": item.net_qty,
        "suggested_purchase_qty": item.suggested_purchase_qty,
        "supplier_id": item.supplier_id,
        "unit_price": float(item.unit_price) if item.unit_price else None,
        "work_order_code": None,
        "order_code": order.code if order else None,
        "sku_code": sku.code if sku else None,
        "sku_name": sku.name if sku else None,
        "material_code": mat.code if mat else None,
        "material_name": mat.name if mat else None,
        "material_unit": mat.unit if mat else None,
        "supplier_name": sup.name if sup else None,
    }


@router.get("")
def list_api(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plans = list_plans(db, offset=offset, limit=limit)
    return ok({"items": [
        {
            "id": p.id,
            "code": p.code,
            "status": p.status,
            "source_type": p.source_type,
            "total_skus": p.total_skus,
            "total_materials": p.total_materials,
            "total_purchase_qty": p.total_purchase_qty,
            "created_at": p.created_at,
        }
        for p in plans
    ]})


@router.post("/compute")
def compute_api(
    body: MrpComputeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.work_order_ids:
        raise HTTPException(status_code=400, detail="请选择至少一个工单")
    try:
        plan = compute_mrp(db, body.work_order_ids, user.id, body.remark)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok({"id": plan.id, "code": plan.code})


@router.get("/{plan_id}")
def detail_api(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="MRP 计划不存在")
    return ok({
        "id": plan.id,
        "code": plan.code,
        "status": plan.status,
        "source_type": plan.source_type,
        "remark": plan.remark,
        "total_skus": plan.total_skus,
        "total_materials": plan.total_materials,
        "total_purchase_qty": plan.total_purchase_qty,
        "created_at": plan.created_at,
        "items": [_item_out(i) for i in plan.items],
    })
