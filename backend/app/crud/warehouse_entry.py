from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.material_issue import MaterialReturn
from app.models.purchase import PurchaseOrder
from app.models.sku import Sku
from app.models.warehouse_entry import WarehouseEntry, WarehouseEntryItem
from app.crud.warehouse import adjust_stock


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


def confirm_entry(db: Session, entry: WarehouseEntry, confirmed_by: int | None = None) -> WarehouseEntry:
    if entry.status != "draft":
        raise ValueError(f"入库单 {entry.code} 状态不允许确认")
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
    db.flush()
    return entry


def cancel_entry(db: Session, entry: WarehouseEntry) -> WarehouseEntry:
    if entry.status != "draft":
        raise ValueError(f"入库单 {entry.code} 状态不允许取消")
    entry.status = "cancelled"
    db.flush()
    return entry
