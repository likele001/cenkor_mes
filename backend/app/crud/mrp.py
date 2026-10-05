# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""MRP 物料需求计划：算净需求 + 落成采购单。

净需求 = 毛需求 −（可用库存 + 在途采购量）。两个口径以前都缺：
- 库存算的是全部仓库之和，停用仓里的料也被当成可用；
- 在途（已下单未到货）根本没参与计算，同一批料会被下一次 MRP 再建议买一遍。

多张工单共用一种物料时，库存按行顺序扣减（先到先得），不是每张工单各看一次全额库存，
否则两张各需 60、库存只有 100，MRP 会说两头都不缺料。

仍然保留待完善的部分：不含安全库存/最小起订量/批量、不做多阶 BOM 展开、
建议量不裁剪到供应商实际供货节奏，转出来的采购单也需要人审后才确认。
"""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.crud.approval_record import record_status
from app.crud.material_bom import get_effective_bom_for_sku
from app.crud.purchase_order import create_purchase_order
from app.models.material import Material
from app.models.mrp import MrpItem, MrpPlan
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.warehouse import Stock, Warehouse
from app.models.work_order import WorkOrder

# 在途采购量只看已确认、还没收完的采购单；草稿单还没下单，不占用需求
_OPEN_PO_STATUSES = ("confirmed", "partial_received")


def _stock_map(db: Session, sku_ids: list[int], warehouse_ids: list[int] | None) -> dict[int, int]:
    """可用库存：指定仓库优先，否则只算启用中的仓库。"""
    if not sku_ids:
        return {}
    stmt = (
        select(Stock.sku_id, func.coalesce(func.sum(Stock.qty), 0))
        .join(Warehouse, Warehouse.id == Stock.warehouse_id)
        .where(Stock.sku_id.in_(sku_ids))
    )
    if warehouse_ids:
        stmt = stmt.where(Stock.warehouse_id.in_(warehouse_ids))
    else:
        stmt = stmt.where(Warehouse.is_active.is_(True))
    rows = db.execute(stmt.group_by(Stock.sku_id)).all()
    return {int(sku_id): int(qty or 0) for sku_id, qty in rows}


def _on_order_map(db: Session, material_ids: list[int]) -> dict[int, int]:
    """在途量 = 已确认采购单里还没收进来的数量。"""
    if not material_ids:
        return {}
    stmt = (
        select(
            PurchaseOrderItem.material_id,
            func.coalesce(func.sum(PurchaseOrderItem.qty - PurchaseOrderItem.received_qty), 0),
        )
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id)
        .where(
            PurchaseOrderItem.material_id.in_(material_ids),
            PurchaseOrder.status.in_(_OPEN_PO_STATUSES),
        )
        .group_by(PurchaseOrderItem.material_id)
    )
    rows = db.execute(stmt).all()
    return {int(mid): max(int(qty or 0), 0) for mid, qty in rows}


def _last_purchase_hint(db: Session, material_ids: list[int]) -> dict[int, tuple[Decimal, int | None]]:
    """每种物料最近一次的（采购单价, 供应商）。

    单价让采购员不用翻历史单；供应商是兜底——物料档案经常没填，
    那样这行建议永远转不成采购单，退回按最近实际给它供过货的那家。
    """
    if not material_ids:
        return {}
    rows = db.execute(
        select(PurchaseOrderItem.material_id, PurchaseOrderItem.unit_price, PurchaseOrder.supplier_id)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id)
        .where(PurchaseOrderItem.material_id.in_(material_ids), PurchaseOrderItem.unit_price.is_not(None))
        .order_by(PurchaseOrderItem.material_id, PurchaseOrderItem.id.desc())
    ).all()
    hints: dict[int, tuple[Decimal, int | None]] = {}
    for mid, price, supplier_id in rows:
        hints.setdefault(int(mid), (Decimal(str(price)), int(supplier_id)))
    return hints


def compute_mrp(
    db: Session,
    work_order_ids: list[int],
    created_by: int | None,
    remark: str | None,
    warehouse_ids: list[int] | None = None,
) -> MrpPlan:
    work_orders = db.scalars(
        select(WorkOrder)
        .where(WorkOrder.id.in_(work_order_ids))
        .options(selectinload(WorkOrder.order), selectinload(WorkOrder.sku))
        .order_by(WorkOrder.id)
    ).all()

    if not work_orders:
        raise ValueError("未找到指定工单")

    # 第一遍：按 BOM 收集毛需求
    demand: list[tuple[WorkOrder, int, Material, int, int]] = []  # (wo, bom_id, material, qty_per, gross)
    seen_material_ids: set[int] = set()
    seen_sku_ids: set[int] = set()
    bom_scope_by_wo: dict[int, str | None] = {}
    for wo in work_orders:
        bom, scope = get_effective_bom_for_sku(db, wo.sku_id)
        if not bom:
            continue
        bom_scope_by_wo[wo.id] = scope
        seen_sku_ids.add(wo.sku_id)
        for bi in bom.items:
            material = bi.material
            if material is None:
                continue
            demand.append((wo, bom.id, material, bi.qty_per, bi.qty_per * wo.qty))
            seen_material_ids.add(material.id)

    if not demand:
        raise ValueError("所选工单都没有物料清单（BOM），无法计算需求")

    sku_ids = sorted({m.sku_id for _w, _b, m, _q, _g in demand if m.sku_id})
    stock_map = _stock_map(db, sku_ids, warehouse_ids)
    on_order = _on_order_map(db, list(seen_material_ids))
    hints = _last_purchase_hint(db, list(seen_material_ids))

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

    total_purchase = 0
    # 第二遍：按行顺序扣池子。同一物料的库存+在途是一个池，先到先扣，
    # 不是每张工单各看一次全额，否则两张各需 60、库存只有 100 会说两头都不缺料。
    pool: dict[int, int] = {}
    for wo, bom_id, material, qty_per, gross in demand:
        if material.id not in pool:
            pool[material.id] = stock_map.get(material.sku_id, 0) + on_order.get(material.id, 0)
        coverable = min(gross, pool[material.id])
        pool[material.id] -= coverable
        net = gross - coverable
        hint = hints.get(material.id)

        item = MrpItem(
            plan_id=plan.id,
            work_order_id=wo.id,
            order_id=wo.order_id,
            sku_id=wo.sku_id,
            material_id=material.id,
            bom_id=bom_id,
            bom_scope=bom_scope_by_wo.get(wo.id),
            wo_qty=wo.qty,
            qty_per=qty_per,
            gross_qty=gross,
            stock_qty=stock_map.get(material.sku_id, 0) if material.sku_id else 0,
            on_order_qty=on_order.get(material.id, 0),
            net_qty=net,
            suggested_purchase_qty=net,
            supplier_id=material.supplier_id or (hint[1] if hint else None),
            unit_price=hint[0] if hint else None,
        )
        db.add(item)
        db.flush()

        total_purchase += net

    plan.total_skus = len(seen_sku_ids)
    plan.total_materials = len(seen_material_ids)
    plan.total_purchase_qty = total_purchase

    record_status(
        db,
        biz_type="mrp_plan",
        biz_id=plan.id,
        biz_code=plan.code,
        action="compute",
        operator=created_by,
        to_status=plan.status,
        detail={
            "work_order_ids": [wo.id for wo in work_orders],
            "warehouse_ids": warehouse_ids,
            "total_purchase_qty": total_purchase,
        },
    )
    db.flush()
    return plan


def convert_plan_to_purchase_orders(
    db: Session,
    plan_id: int,
    *,
    operator_id: int | None,
    item_ids: list[int] | None = None,
    only_with_supplier: bool = True,
    remark: str | None = None,
) -> dict:
    """把建议量落成采购草稿单：按供应商分单，同一物料的多行合并成一行。

    只生成 draft，不自动确认——确认那一步得由采购主管看价、看交期再点。
    """
    plan = db.scalar(select(MrpPlan).where(MrpPlan.id == plan_id))
    if not plan:
        raise ValueError("MRP 计划不存在")

    stmt = select(MrpItem).where(
        MrpItem.plan_id == plan.id,
        MrpItem.suggested_purchase_qty > 0,
        MrpItem.purchase_order_id.is_(None),
    )
    if item_ids:
        stmt = stmt.where(MrpItem.id.in_(item_ids))
    items = list(db.scalars(stmt.order_by(MrpItem.supplier_id, MrpItem.material_id)).all())
    if not items:
        raise ValueError("没有可转采购的建议行（可能已经转过了）")

    skipped = [i for i in items if i.supplier_id is None]
    if only_with_supplier:
        items = [i for i in items if i.supplier_id is not None]
        if not items:
            raise ValueError("所有建议行都没有指定供应商，请先在物料档案里维护供应商")
    else:
        skipped = []

    groups: dict[int, list[MrpItem]] = {}
    for item in items:
        groups.setdefault(int(item.supplier_id), []).append(item)

    created: list[dict] = []
    for supplier_id, rows in groups.items():
        merged: dict[int, dict] = {}
        for r in rows:
            slot = merged.setdefault(
                r.material_id,
                {"qty": 0, "price": r.unit_price, "items": []},
            )
            slot["qty"] += r.suggested_purchase_qty
            if slot["price"] is None and r.unit_price is not None:
                slot["price"] = r.unit_price
            slot["items"].append(r)

        po_items = [
            (material_id, int(info["qty"]), float(info["price"]) if info["price"] is not None else None, f"MRP {plan.code}")
            for material_id, info in merged.items()
        ]
        po = create_purchase_order(
            db,
            supplier_id=supplier_id,
            code=None,
            remark=remark or f"由 MRP 计划 {plan.code} 生成",
            created_by=operator_id,
            items=po_items,
        )
        for info in merged.values():
            for r in info["items"]:
                r.purchase_order_id = po.id
        created.append({"purchase_order_id": po.id, "code": po.code, "lines": len(po_items)})

    remaining = db.scalar(
        select(func.count()).select_from(MrpItem).where(
            MrpItem.plan_id == plan.id,
            MrpItem.suggested_purchase_qty > 0,
            MrpItem.purchase_order_id.is_(None),
        )
    )
    plan.status = "converted" if not remaining else "partial_converted"

    record_status(
        db,
        biz_type="mrp_plan",
        biz_id=plan.id,
        biz_code=plan.code,
        action="convert",
        operator=operator_id,
        from_status="computed",
        to_status=plan.status,
        reason=remark,
        detail={
            "purchase_orders": created,
            "converted_items": len(items),
            "skipped_no_supplier": [i.id for i in skipped],
        },
    )
    db.flush()
    return {
        "plan_id": plan.id,
        "plan_code": plan.code,
        "status": plan.status,
        "purchase_orders": created,
        "converted_items": len(items),
        "skipped_no_supplier": len(skipped),
    }


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


def count_plans(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(MrpPlan)) or 0)
