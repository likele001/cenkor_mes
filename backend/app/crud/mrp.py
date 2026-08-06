from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.material import Material, MaterialBom, MaterialBomItem, Supplier
from app.models.mrp import MrpItem, MrpPlan
from app.models.order import Order
from app.models.sku import Sku
from app.models.warehouse import Stock
from app.models.work_order import WorkOrder
from app.crud.material_bom import get_effective_bom_for_sku

__all__ = [
    "compute_mrp",
    "get_plan_by_id",
    "list_plans",
]


def _get_total_stock_by_sku(db: Session, sku_id: int) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(Stock.qty), 0)).where(Stock.sku_id == sku_id)
    )
    return int(total or 0)


def compute_mrp(db: Session, work_order_ids: list[int], created_by: int | None, remark: str | None) -> MrpPlan:
    work_orders = db.scalars(
        select(WorkOrder)
        .where(WorkOrder.id.in_(work_order_ids))
        .options(
            selectinload(WorkOrder.order),
            selectinload(WorkOrder.sku),
        )
    ).all()

    if not work_orders:
        raise ValueError("未找到指定工单")

    from app.services.code_generator import BizType, allocate_code
    code = allocate_code(db, BizType.MRP_RUN)

    plan = MrpPlan(
        code=code,
        status="computed",
        source_type="work_order",
        remark=remark,
        created_by=created_by,
    )
    db.add(plan)
    db.flush()

    seen_skus: set[int] = set()
    seen_materials: set[int] = set()
    total_purchase = 0

    for wo in work_orders:
        bom, scope = get_effective_bom_for_sku(db, wo.sku_id)
        if not bom:
            continue

        stock_qty = _get_total_stock_by_sku(db, wo.sku_id)

        for bi in bom.items:
            material = bi.material
            gross_qty = bi.qty_per * wo.qty
            mat_stock = _get_total_stock_by_sku(db, material.sku_id) if material.sku_id else 0
            net_qty = max(gross_qty - mat_stock, 0)
            suggested = net_qty

            supplier_id = material.supplier_id
            unit_price = None

            item = MrpItem(
                plan_id=plan.id,
                work_order_id=wo.id,
                order_id=wo.order_id,
                sku_id=wo.sku_id,
                material_id=bi.material_id,
                bom_id=bom.id,
                bom_scope=scope,
                wo_qty=wo.qty,
                qty_per=bi.qty_per,
                gross_qty=gross_qty,
                stock_qty=mat_stock,
                net_qty=net_qty,
                suggested_purchase_qty=suggested,
                supplier_id=supplier_id,
                unit_price=unit_price,
            )
            db.add(item)
            db.flush()

            seen_skus.add(wo.sku_id)
            seen_materials.add(bi.material_id)
            total_purchase += suggested

    plan.total_skus = len(seen_skus)
    plan.total_materials = len(seen_materials)
    plan.total_purchase_qty = total_purchase

    db.flush()
    return plan


def get_plan_by_id(db: Session, plan_id: int) -> MrpPlan | None:
    return db.scalar(
        select(MrpPlan)
        .where(MrpPlan.id == plan_id)
        .options(
            selectinload(MrpPlan.items)
            .selectinload(MrpItem.sku),
            selectinload(MrpPlan.items)
            .selectinload(MrpItem.material),
            selectinload(MrpPlan.items)
            .selectinload(MrpItem.work_order),
            selectinload(MrpPlan.items)
            .selectinload(MrpItem.order),
            selectinload(MrpPlan.items)
            .selectinload(MrpItem.supplier),
        )
    )


def list_plans(db: Session, offset: int = 0, limit: int = 50) -> list[MrpPlan]:
    return db.scalars(
        select(MrpPlan)
        .order_by(MrpPlan.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
