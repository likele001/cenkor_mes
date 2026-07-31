from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.process_price import ProcessPrice


def get_price_by_id(db: Session, price_id: int) -> ProcessPrice | None:
    return db.scalar(select(ProcessPrice).where(ProcessPrice.id == price_id))


def get_price_by_sku_process(db: Session, sku_id: int, process_id: int) -> ProcessPrice | None:
    return db.scalar(
        select(ProcessPrice).where(ProcessPrice.sku_id == sku_id, ProcessPrice.process_id == process_id)
    )


def list_prices_for_sku(
    db: Session,
    sku_id: int,
    *,
    include_inactive: bool = True,
) -> list[ProcessPrice]:
    stmt = select(ProcessPrice).where(ProcessPrice.sku_id == sku_id)
    if not include_inactive:
        stmt = stmt.where(ProcessPrice.is_active.is_(True))
    stmt = stmt.order_by(ProcessPrice.process_id.asc())
    return db.scalars(stmt).all()


def batch_upsert_prices(
    db: Session,
    sku_id: int,
    items: list[dict],
) -> tuple[int, int]:
    """批量保存工价。items: [{process_id, unit_price, is_active?}]。返回 (created, updated)。"""
    created = 0
    updated = 0
    for it in items:
        process_id = int(it["process_id"])
        raw_price = it.get("unit_price")
        if raw_price is None or raw_price == "":
            continue
        unit_price = Decimal(str(raw_price))
        if unit_price < 0:
            raise ValueError(f"工序#{process_id} 单价不能为负")
        is_active = bool(it.get("is_active", True))
        existing = get_price_by_sku_process(db, sku_id, process_id)
        if existing:
            update_price(db, existing, unit_price=unit_price, is_active=is_active)
            updated += 1
        else:
            if unit_price == 0 and not is_active:
                continue
            create_price(
                db,
                sku_id=sku_id,
                process_id=process_id,
                unit_price=unit_price,
                is_active=is_active,
            )
            created += 1
    return created, updated


def list_prices(
    db: Session,
    sku_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[ProcessPrice]:
    stmt = select(ProcessPrice)
    if sku_id is not None:
        stmt = stmt.where(ProcessPrice.sku_id == sku_id)
    if not include_inactive:
        stmt = stmt.where(ProcessPrice.is_active.is_(True))
    stmt = stmt.order_by(ProcessPrice.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def create_price(
    db: Session,
    sku_id: int,
    process_id: int,
    unit_price: Decimal,
    is_active: bool,
) -> ProcessPrice:
    item = ProcessPrice(sku_id=sku_id, process_id=process_id, unit_price=unit_price, is_active=is_active)
    db.add(item)
    db.flush()
    return item


def update_price(
    db: Session,
    item: ProcessPrice,
    unit_price: Decimal | None = None,
    is_active: bool | None = None,
) -> ProcessPrice:
    if unit_price is not None:
        item.unit_price = unit_price
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item
