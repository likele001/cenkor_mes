# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_any_permissions, require_permissions
from app.core.response import ok
from app.crud.mrp import (
    compute_mrp,
    convert_plan_to_purchase_orders,
    count_plans,
    get_plan_by_id,
    list_plans,
)
from app.models.user import User
from app.schemas.mrp import MrpComputeRequest, MrpConvertRequest

router = APIRouter()


def _item_out(item) -> dict:
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
        "on_order_qty": item.on_order_qty,
        "net_qty": item.net_qty,
        "suggested_purchase_qty": item.suggested_purchase_qty,
        "supplier_id": item.supplier_id,
        "unit_price": float(item.unit_price) if item.unit_price else None,
        "purchase_order_id": item.purchase_order_id,
        # work_orders 表本身没有单号列，工单只能靠 id + 订单号定位
        "work_order_code": None,
        "order_code": order.code if order else None,
        "sku_code": sku.code if sku else None,
        "sku_name": sku.name if sku else None,
        "material_code": mat.code if mat else None,
        "material_name": mat.name if mat else None,
        "material_unit": mat.unit if mat else None,
        "supplier_name": sup.name if sup else None,
    }


def _plan_out(plan, with_items: bool) -> dict:
    data = {
        "id": plan.id,
        "code": plan.code,
        "status": plan.status,
        "source_type": plan.source_type,
        "remark": plan.remark,
        "total_skus": plan.total_skus,
        "total_materials": plan.total_materials,
        "total_purchase_qty": plan.total_purchase_qty,
        "created_at": plan.created_at,
    }
    if with_items:
        data["items"] = [_item_out(i) for i in plan.items]
    return data


@router.get("")
def list_api(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plans = list_plans(db, offset=offset, limit=limit)
    return ok({"items": [_plan_out(p, with_items=False) for p in plans], "total": count_plans(db)})


@router.post("/compute")
def compute_api(
    body: MrpComputeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    # 算需求是排产的活，转采购才是采购的活：计算放开给 plan.manage
    _=Depends(require_any_permissions(["purchase.manage", "plan.manage"])),
):
    if not body.work_order_ids:
        raise HTTPException(status_code=400, detail="请选择至少一个工单")
    try:
        plan = compute_mrp(db, body.work_order_ids, user.id, body.remark, body.warehouse_ids)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok({"id": plan.id, "code": plan.code, "total_purchase_qty": plan.total_purchase_qty})


@router.get("/{plan_id}")
def detail_api(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="MRP 计划不存在")
    return ok(_plan_out(plan, with_items=True))


@router.post("/{plan_id}/convert")
def convert_api(
    plan_id: int,
    body: MrpConvertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permissions(["purchase.manage"])),
):
    """把建议采购量落成采购草稿单，确认那一步留给人做。"""
    try:
        result = convert_plan_to_purchase_orders(
            db,
            plan_id,
            operator_id=user.id,
            item_ids=body.item_ids,
            only_with_supplier=body.only_with_supplier,
            remark=body.remark,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok(result)
