"""ERP 工单成本核算 CRUD"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.erp_cost import WorkOrderCost, WorkOrderCostItem


def list_costs(
    db: Session,
    tenant_id: int,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[WorkOrderCost]:
    stmt = select(WorkOrderCost).where(WorkOrderCost.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(WorkOrderCost.status == status)
    stmt = stmt.order_by(WorkOrderCost.updated_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def get_cost_by_work_order(db: Session, tenant_id: int, work_order_id: int) -> WorkOrderCost | None:
    return db.scalar(
        select(WorkOrderCost)
        .where(WorkOrderCost.tenant_id == tenant_id, WorkOrderCost.work_order_id == work_order_id)
        .options(selectinload(WorkOrderCost.items))
    )


def get_or_create_cost(db: Session, tenant_id: int, work_order_id: int) -> WorkOrderCost:
    cost = get_cost_by_work_order(db, tenant_id, work_order_id)
    if cost:
        return cost
    cost = WorkOrderCost(tenant_id=tenant_id, work_order_id=work_order_id, status="draft")
    db.add(cost)
    db.flush()
    return cost


def add_cost_item(db: Session, cost: WorkOrderCost, *, cost_type: str, source_type: str, source_id: int | None, ref_code: str | None, amount: Decimal, remark: str | None = None) -> WorkOrderCostItem:
    item = WorkOrderCostItem(
        tenant_id=cost.tenant_id,
        cost_id=cost.id,
        cost_type=cost_type,
        source_type=source_type,
        source_id=source_id,
        ref_code=ref_code,
        amount=amount,
        remark=remark,
    )
    db.add(item)
    db.flush()
    return item


def recompute_cost(db: Session, cost: WorkOrderCost) -> WorkOrderCost:
    items = list(db.scalars(select(WorkOrderCostItem).where(WorkOrderCostItem.cost_id == cost.id)).all())
    material = sum((i.amount for i in items if i.cost_type == "material"), Decimal("0"))
    labor = sum((i.amount for i in items if i.cost_type == "labor"), Decimal("0"))
    overhead = sum((i.amount for i in items if i.cost_type == "overhead"), Decimal("0"))
    total = material + labor + overhead
    cost.material_cost = material
    cost.labor_cost = labor
    cost.overhead_cost = overhead
    cost.total_cost = total
    cost.unit_cost = (total / Decimal(str(cost.qty))) if cost.qty else Decimal("0")
    cost.gross_profit = (cost.quote_amount or Decimal("0")) - total
    if cost.quote_amount:
        cost.gross_margin = cost.gross_profit / cost.quote_amount
    cost.status = "calculated"
    cost.computed_at = datetime.now()
    db.flush()
    return cost


def close_cost(db: Session, cost: WorkOrderCost) -> WorkOrderCost:
    cost.status = "closed"
    db.flush()
    return cost
