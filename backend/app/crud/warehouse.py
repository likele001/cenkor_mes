from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.sku import Sku
from app.models.warehouse import Warehouse, Stock, StockLog


# ── 仓库 ──

def create_warehouse(db: Session, code: str, name: str, address: str | None = None) -> Warehouse:
    wh = Warehouse(code=code, name=name, address=address)
    db.add(wh)
    db.flush()
    return wh


def list_warehouses(db: Session) -> list[Warehouse]:
    return db.scalars(select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(Warehouse.id)).all()


# ── 库存 ──

def get_stock(db: Session, warehouse_id: int, sku_id: int) -> Stock | None:
    return db.scalar(
        select(Stock).where(
            Stock.warehouse_id == warehouse_id,
            Stock.sku_id == sku_id,
        )
    )


def get_or_create_stock(db: Session, warehouse_id: int, sku_id: int) -> Stock:
    s = get_stock(db, warehouse_id, sku_id)
    if not s:
        s = Stock(warehouse_id=warehouse_id, sku_id=sku_id, qty=0)
        db.add(s)
        db.flush()
    return s


def list_stocks(
    db: Session,
    warehouse_id: int | None = None,
    item_type: str | None = None,
) -> list[Stock]:
    stmt = (
        select(Stock)
        .join(Sku, Sku.id == Stock.sku_id)
        .options(selectinload(Stock.sku), selectinload(Stock.warehouse))
    )
    if warehouse_id is not None:
        stmt = stmt.where(Stock.warehouse_id == warehouse_id)
    if item_type == "material":
        stmt = stmt.where(Sku.code.like("MAT-%"))
    elif item_type == "product":
        stmt = stmt.where(~Sku.code.like("MAT-%"))
    stmt = stmt.order_by(Stock.warehouse_id, Stock.sku_id)
    return db.scalars(stmt).all()


def adjust_stock(
    db: Session,
    warehouse_id: int,
    sku_id: int,
    change_qty: int,
    biz_type: str,
    biz_id: int | None = None,
    remark: str | None = None,
) -> Stock:
    """调整库存，change_qty 正=入库 负=出库"""
    s = get_or_create_stock(db, warehouse_id, sku_id)
    s.qty += change_qty
    log = StockLog(
        warehouse_id=warehouse_id,
        sku_id=sku_id,
        change_qty=change_qty,
        balance_qty=s.qty,
        biz_type=biz_type,
        biz_id=biz_id,
        remark=remark,
    )
    db.add(log)
    db.flush()
    return s


def list_stock_logs(
    db: Session,
    warehouse_id: int | None = None,
    sku_id: int | None = None,
    item_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[StockLog]:
    stmt = select(StockLog).options(selectinload(StockLog.sku), selectinload(StockLog.warehouse))
    if warehouse_id is not None:
        stmt = stmt.where(StockLog.warehouse_id == warehouse_id)
    if sku_id is not None:
        stmt = stmt.where(StockLog.sku_id == sku_id)
    if item_type == "material":
        stmt = stmt.join(Sku, Sku.id == StockLog.sku_id).where(Sku.code.like("MAT-%"))
    elif item_type == "product":
        stmt = stmt.join(Sku, Sku.id == StockLog.sku_id).where(~Sku.code.like("MAT-%"))
    stmt = stmt.order_by(StockLog.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def sum_stock_qty_by_sku_ids(db: Session, sku_ids: list[int]) -> dict[int, int]:
    if not sku_ids:
        return {}
    rows = db.execute(
        select(Stock.sku_id, func.sum(Stock.qty))
        .where(Stock.sku_id.in_(sku_ids))
        .group_by(Stock.sku_id)
    ).all()
    return {int(sku_id): int(qty or 0) for sku_id, qty in rows}
