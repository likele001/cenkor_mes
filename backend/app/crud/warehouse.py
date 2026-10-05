# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.sku import Sku
from app.models.warehouse import Warehouse, Stock, StockLog


class StockShortage(ValueError):
    """账面库存不足：出库一律先把账扣平，不允许扣成负数。"""


# ── 仓库 ──

def create_warehouse(db: Session, code: str, name: str, address: str | None = None) -> Warehouse:
    wh = Warehouse(code=code, name=name, address=address)
    db.add(wh)
    db.flush()
    return wh


def list_warehouses(db: Session) -> list[Warehouse]:
    return db.scalars(select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(Warehouse.id)).all()


def resolve_warehouse_id(db: Session, warehouse_id: int | None, *, action: str) -> int:
    """出入库必须落到具体仓库：显式指定优先；只有一个启用仓库时沿用；多仓必须选。"""
    if warehouse_id:
        wh = db.get(Warehouse, int(warehouse_id))
        if not wh or not wh.is_active:
            raise ValueError(f"{action}的仓库不存在或已停用")
        return wh.id
    active = list_warehouses(db)
    if not active:
        raise ValueError("请先创建仓库")
    if len(active) > 1:
        raise ValueError(f"当前有 {len(active)} 个启用仓库，{action}时必须指定仓库")
    return active[0].id


# ── 库存 ──

def get_stock(db: Session, warehouse_id: int, sku_id: int) -> Stock | None:
    return db.scalar(
        select(Stock).where(
            Stock.warehouse_id == warehouse_id,
            Stock.sku_id == sku_id,
        )
    )


def lock_stock(db: Session, warehouse_id: int, sku_id: int) -> Stock:
    """加行锁取库存行，并发扣减不会丢更新（SQLite 会忽略 FOR UPDATE）。"""
    s = db.scalar(
        select(Stock)
        .where(Stock.warehouse_id == warehouse_id, Stock.sku_id == sku_id)
        .with_for_update()
    )
    if s:
        return s
    sp = db.begin_nested()
    try:
        s = Stock(warehouse_id=warehouse_id, sku_id=sku_id, qty=0)
        db.add(s)
        db.flush()
        sp.commit()
    except IntegrityError:
        # 并发首次建仓同一型号：唯一键冲突后取已存在行
        sp.rollback()
        return db.scalar(
            select(Stock).where(Stock.warehouse_id == warehouse_id, Stock.sku_id == sku_id)
        )
    return s


def _stock_label(s: Stock) -> str:
    wh = s.warehouse.name if s.warehouse else None
    sku = s.sku.name if s.sku else None
    return f"{wh or f'仓库#{s.warehouse_id}'} / {sku or f'型号#{s.sku_id}'}"


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
    """调整库存，change_qty 正=入库 负=出库。

    所有出入库都走这里：账面数不允许被扣成负数，出库不足直接抛 StockShortage，
    宁可业务报错也不要留下一张对不上实物账的库存表。
    """
    if warehouse_id is None or sku_id is None:
        raise ValueError("库存变动必须指定仓库与型号")
    change_qty = int(change_qty)
    if change_qty == 0:
        raise ValueError("库存变动数量不能为 0")

    s = lock_stock(db, warehouse_id, sku_id)
    balance = int(s.qty or 0) + change_qty
    if balance < 0:
        raise StockShortage(
            f"{_stock_label(s)} 库存不足：账面 {int(s.qty or 0)}，本次出库 {-change_qty}，缺 {-balance}"
        )
    s.qty = balance
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
