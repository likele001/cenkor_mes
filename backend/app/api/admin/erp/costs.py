# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.erp_cost import (
    add_cost_item,
    close_cost,
    get_cost_by_work_order,
    get_or_create_cost,
    list_costs,
    recompute_cost,
)
from app.models.erp_cost import WorkOrderCost
from app.models.material_issue import MaterialIssue
from app.models.order import OrderItem
from app.models.user import User
from app.models.work_order import WorkOrder
from app.schemas.erp_cost import CostCalculateIn, OverheadIn


router = APIRouter()


def _item_out(x) -> dict:
    return {
        "id": x.id,
        "cost_type": x.cost_type,
        "source_type": x.source_type,
        "source_id": x.source_id,
        "ref_code": x.ref_code,
        "amount": float(x.amount or 0),
        "remark": x.remark,
    }


def _out(x: WorkOrderCost, with_items: bool = False) -> dict:
    d = {
        "id": x.id,
        "work_order_id": x.work_order_id,
        "order_id": x.order_id,
        "product_id": x.product_id,
        "sku_id": x.sku_id,
        "qty": x.qty,
        "material_cost": float(x.material_cost or 0),
        "labor_cost": float(x.labor_cost or 0),
        "overhead_cost": float(x.overhead_cost or 0),
        "total_cost": float(x.total_cost or 0),
        "unit_cost": float(x.unit_cost or 0),
        "quote_amount": float(x.quote_amount or 0),
        "gross_profit": float(x.gross_profit or 0),
        "gross_margin": float(x.gross_margin or 0),
        "status": x.status,
        "computed_at": x.computed_at,
        "updated_at": x.updated_at,
    }
    if with_items:
        d["items"] = [_item_out(it) for it in x.items]
    return d


@router.get("")
def list_api(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_costs(db, user.tenant_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_out(x) for x in items]})


@router.get("/{work_order_id}")
def detail_api(
    work_order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cost = get_cost_by_work_order(db, user.tenant_id, work_order_id)
    if not cost:
        raise HTTPException(status_code=404, detail="该工单尚未核算成本")
    return ok(_out(cost, with_items=True))


@router.post("/calculate")
def calculate_api(
    body: CostCalculateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 单工单核算
    if body.work_order_id:
        wo = db.scalar(
            select(WorkOrder).where(WorkOrder.tenant_id == user.tenant_id, WorkOrder.id == body.work_order_id)
        )
        if not wo:
            raise HTTPException(status_code=404, detail="工单不存在")
        cost = _calculate_one(db, user.tenant_id, wo)
        db.commit()
        return ok(_out(cost, with_items=True), "核算完成")

    # 按期间批量核算：以材料领用时间为窗，粗略取工单全部
    if body.period:
        costs = []
        work_orders = db.scalars(
            select(WorkOrder).where(WorkOrder.tenant_id == user.tenant_id).limit(500)
        ).all()
        for wo in work_orders:
            cost = _calculate_one(db, user.tenant_id, wo)
            costs.append(_out(cost))
        db.commit()
        return ok({"items": costs}, "批量核算完成")

    raise HTTPException(status_code=400, detail="请指定 work_order_id 或 period")


def _calculate_one(db: Session, tenant_id: int, wo: WorkOrder) -> WorkOrderCost:
    cost = get_or_create_cost(db, tenant_id, wo.id)
    # 冗余工单/订单/型号信息
    cost.work_order_id = wo.id
    cost.order_id = wo.order_id
    cost.product_id = wo.product_id
    cost.sku_id = wo.sku_id
    cost.qty = wo.qty or 0

    # 清空旧明细重算
    for it in list(cost.items):
        db.delete(it)
    db.flush()

    # 1) 材料：material_issues 按 work_order_id 汇总
    material_total = Decimal("0")
    issues = db.scalars(
        select(MaterialIssue).where(
            MaterialIssue.tenant_id == tenant_id,
            MaterialIssue.work_order_id == wo.id,
        )
    ).all()
    for mi in issues:
        amt = mi.total_cost or Decimal("0")
        material_total += amt
        add_cost_item(
            db, cost,
            cost_type="material", source_type="material_issue",
            source_id=mi.id, ref_code=mi.code,
            amount=amt,
        )

    # 2) 人工：工单计件工资（SalaryItem 按 work_order_id 关联，若字段存在）
    labor_total = Decimal("0")
    try:
        from app.models.salary import SalaryItem
        if hasattr(SalaryItem, "work_order_id"):
            salary_rows = db.scalars(
                select(SalaryItem).where(
                    SalaryItem.tenant_id == tenant_id,
                    SalaryItem.work_order_id == wo.id,
                )
            ).all()
            for sr in salary_rows:
                amt = Decimal(str(sr.amount or 0))
                labor_total += amt
                add_cost_item(
                    db, cost,
                    cost_type="labor", source_type="salary",
                    source_id=sr.id, ref_code=None,
                    amount=amt,
                )
    except Exception:
        pass  # SalaryItem 无 work_order_id 时跳过（可后续经 report→task 链路扩展）

    cost.material_cost = material_total
    cost.labor_cost = labor_total
    cost.total_cost = material_total + labor_total
    cost.unit_cost = (cost.total_cost / Decimal(str(wo.qty))) if wo.qty else Decimal("0")

    # 3) 报价：订单明细 subtotal 取该工单 sku 对应行
    quote = Decimal("0")
    oi = db.scalar(
        select(OrderItem).where(
            OrderItem.tenant_id == tenant_id,
            OrderItem.order_id == wo.order_id,
            OrderItem.sku_id == wo.sku_id,
        )
    )
    if oi is not None and oi.subtotal is not None:
        quote = Decimal(str(oi.subtotal))
    cost.quote_amount = quote
    cost.gross_profit = quote - cost.total_cost
    if quote:
        cost.gross_margin = cost.gross_profit / quote
    cost.status = "calculated"
    cost.computed_at = date.today()  # placeholder datetime
    from datetime import datetime
    cost.computed_at = datetime.now()
    db.flush()
    return cost


@router.post("/{work_order_id}/overhead")
def overhead_api(
    work_order_id: int,
    body: OverheadIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wo = db.scalar(
        select(WorkOrder).where(WorkOrder.tenant_id == user.tenant_id, WorkOrder.id == work_order_id)
    )
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    cost = get_or_create_cost(db, user.tenant_id, wo.id)
    add_cost_item(
        db, cost,
        cost_type="overhead", source_type="manual",
        source_id=None, ref_code=None,
        amount=body.amount, remark=body.remark,
    )
    cost = recompute_cost(db, cost)
    db.commit()
    return ok(_out(cost, with_items=True), "已补录制造费用")


@router.post("/{work_order_id}/close")
def close_api(
    work_order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cost = get_cost_by_work_order(db, user.tenant_id, work_order_id)
    if not cost:
        raise HTTPException(status_code=404, detail="该工单尚未核算成本")
    cost = close_cost(db, cost)
    db.commit()
    return ok({"id": cost.id}, "已关闭")
