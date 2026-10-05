# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.crud.warehouse import adjust_stock
from app.crud.approval_record import record_status
from app.models.material import Material
from app.models.material_issue import MaterialReturn
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.sku import Sku
from app.models.warehouse_entry import WarehouseEntry, WarehouseEntryItem
from app.crud.warehouse import adjust_stock


def _reject_return_entry(material_return_id: int | None) -> None:
    """退料回补由退料单确认时完成，入库单再走一次就是同一批料入两遍账。"""
    if material_return_id is not None:
        raise ValueError("退料入库请直接在退料单上确认，系统会回补库存，不要再建入库单")


def _check_purchase_qty(db: Session, purchase_order_id: int, wanted: dict[int, int]) -> PurchaseOrder:
    """入库数量必须落在采购单的未入库余量内，超出就直接拦下（建单时拦一次，确认时再拦一次）。"""
    po = db.get(PurchaseOrder, purchase_order_id)
    if not po:
        raise ValueError("采购单不存在")
    if po.status not in {"confirmed", "partial_received"}:
        raise ValueError(f"采购单 {po.code} 当前为 {po.status}，不允许入库")
    remain_by_material = {it.material_id: it.qty - it.received_qty for it in (po.items or [])}
    for material_id, qty in wanted.items():
        m = db.get(Material, material_id)
        name = m.name if m else f"物料#{material_id}"
        if material_id not in remain_by_material:
            raise ValueError(f"物料「{name}」不在采购单 {po.code} 中")
        if qty > remain_by_material[material_id]:
            raise ValueError(f"物料「{name}」入库 {qty} 超出采购未入库 {remain_by_material[material_id]}")
    return po


def _commit_purchase_receipt(db: Session, po: PurchaseOrder, entry: WarehouseEntry) -> None:
    """入库单确认后核销回采购单：推进 received_qty 与采购单状态，跟采购页「直接入库」同一口径。"""
    for it in entry.items:
        po_item = db.scalar(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.order_id == po.id,
                PurchaseOrderItem.material_id == it.material_id,
            )
        )
        po_item.received_qty += it.qty
    total_qty = sum(i.qty for i in po.items)
    total_received = sum(i.received_qty for i in po.items)
    po.status = "received" if total_received >= total_qty else "partial_received"
    db.flush()


def get_entry_by_id(db: Session, entry_id: int, with_items: bool = True) -> WarehouseEntry | None:
    q = select(WarehouseEntry)
    if with_items:
        q = q.options(
            selectinload(WarehouseEntry.items).selectinload(WarehouseEntryItem.material),
            selectinload(WarehouseEntry.items).selectinload(WarehouseEntryItem.sku),
            selectinload(WarehouseEntry.warehouse),
            selectinload(WarehouseEntry.purchase_order),
            selectinload(WarehouseEntry.material_return),
        )
    return db.scalar(q.where(WarehouseEntry.id == entry_id))


def list_entries(
    db: Session,
    warehouse_id: int | None = None,
    source_type: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[WarehouseEntry]:
    stmt = select(WarehouseEntry).options(
        selectinload(WarehouseEntry.warehouse),
        selectinload(WarehouseEntry.purchase_order),
        selectinload(WarehouseEntry.material_return),
    )
    if warehouse_id is not None:
        stmt = stmt.where(WarehouseEntry.warehouse_id == warehouse_id)
    if source_type:
        stmt = stmt.where(WarehouseEntry.source_type == source_type)
    if status:
        stmt = stmt.where(WarehouseEntry.status == status)
    stmt = stmt.order_by(WarehouseEntry.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def _resolve_cost(db: Session, sku_id: int) -> Decimal:
    cost = Decimal("0")
    if sku_id:
        sku = db.get(Sku, sku_id)
        if sku and sku.cost_price:
            cost = Decimal(str(sku.cost_price))
    return cost


def create_entry(
    db: Session,
    code: str,
    source_type: str,
    warehouse_id: int,
    items: list[dict],
    purchase_order_id: int | None = None,
    material_return_id: int | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> WarehouseEntry:
    _reject_return_entry(material_return_id)
    if source_type == "purchase" and purchase_order_id is None:
        raise ValueError("采购入库必须关联采购单")
    wanted: dict[int, int] = {}
    for it in items:
        qty = int(it["qty"])
        if qty <= 0:
            raise ValueError("入库数量必须大于 0")
        wanted[it["material_id"]] = wanted.get(it["material_id"], 0) + qty
    if purchase_order_id is not None:
        if source_type != "purchase":
            raise ValueError("关联采购单的入库单，入库类型必须是采购入库")
        _check_purchase_qty(db, purchase_order_id, wanted)
    entry = WarehouseEntry(
        code=code,
        source_type=source_type,
        warehouse_id=warehouse_id,
        purchase_order_id=purchase_order_id,
        material_return_id=material_return_id,
        remark=remark,
        created_by=created_by,
    )
    entry_items = []
    total_qty = 0
    total_cost = Decimal("0")
    for it in items:
        material_id = it["material_id"]
        sku_id = it["sku_id"]
        qty = int(it["qty"])
        unit_cost = _resolve_cost(db, sku_id)
        total_qty += qty
        total_cost += unit_cost * qty
        entry_items.append(WarehouseEntryItem(
            material_id=material_id, sku_id=sku_id,
            qty=qty, unit_cost=unit_cost, cost_amount=unit_cost * qty,
        ))
    entry.items = entry_items
    entry.total_qty = total_qty
    entry.total_cost = total_cost
    db.add(entry)
    db.flush()
    return entry


def confirm_entry(db: Session, entry: WarehouseEntry, confirmed_by: int | None = None, *, channel: str = "web") -> WarehouseEntry:
    if entry.status != "draft":
        raise ValueError(f"入库单 {entry.code} 状态不允许确认")
    _reject_return_entry(entry.material_return_id)
    po = None
    if entry.purchase_order_id is not None:
        totals: dict[int, int] = {}
        for it in entry.items:
            totals[it.material_id] = totals.get(it.material_id, 0) + it.qty
        po = _check_purchase_qty(db, entry.purchase_order_id, totals)
    for it in entry.items:
        adjust_stock(
            db,
            warehouse_id=entry.warehouse_id,
            sku_id=it.sku_id,
            change_qty=it.qty,
            biz_type="warehouse_entry",
            biz_id=entry.id,
            remark=entry.code,
        )
    entry.status = "confirmed"
    entry.confirmed_at = datetime.now()
    entry.confirmed_by = confirmed_by
    if po is not None:
        _commit_purchase_receipt(db, po, entry)
    record_status(
        db,
        biz_type="warehouse_entry",
        biz_id=entry.id,
        biz_code=entry.code,
        action="confirm",
        operator=confirmed_by,
        from_status="draft",
        to_status=entry.status,
        channel=channel,
        detail={"total_qty": entry.total_qty, "total_cost": str(entry.total_cost)},
    )
    db.flush()
    return entry


def cancel_entry(db: Session, entry: WarehouseEntry, *, operator_id: int | None = None, channel: str = "web") -> WarehouseEntry:
    if entry.status != "draft":
        raise ValueError(f"入库单 {entry.code} 状态不允许取消")
    entry.status = "cancelled"
    record_status(
        db,
        biz_type="warehouse_entry",
        biz_id=entry.id,
        biz_code=entry.code,
        action="cancel",
        operator=operator_id,
        from_status="draft",
        to_status=entry.status,
        channel=channel,
    )
    db.flush()
    return entry
