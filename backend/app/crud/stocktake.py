# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""库存盘点：制单 / 录实盘 / 确认入账

关键约束（改这里之前先看清楚）：

1. **确认入账只走 `adjust_stock`**。盘点差异不是"把 stocks.qty 改成实盘数"，
   而是一笔 `biz_type="stocktake"` 的库存流水。直改数量会让库存流水断链，
   安全库存预警、成本核算、账龄这些下游全部失真，而且事后查不出是谁改的。
2. **入账变动按「实盘 − 确认时账面」算，不是「实盘 − 快照账面」**。
   制单到确认之间仓库可能还在收发，用快照差额回冲会把这期间的真实业务抹掉。
3. **状态机是单向的**：draft → counting → confirmed / cancelled，
   confirmed 是终态（差异已经落账，改它等于改历史，只能靠再做一次盘点纠正）。
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.crud.warehouse import adjust_stock, lock_stock
from app.models.sku import Sku
from app.models.stocktake import Stocktake, StocktakeItem
from app.models.warehouse import Stock

_EDITABLE = ("draft", "counting")


class StocktakeStateError(ValueError):
    """盘点单状态不允许该操作"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _recount(st: Stocktake) -> None:
    """按明细重算三个计数。明细是唯一事实来源，计数只是给列表页省一次 join。"""
    items = st.items or []
    st.total_items = len(items)
    st.counted_items = sum(1 for it in items if it.counted_qty is not None)
    st.diff_items = sum(
        1 for it in items if it.diff_qty is not None and int(it.diff_qty) != 0
    )


def _item_out(it: StocktakeItem) -> dict:
    return {
        "id": it.id,
        "sku_id": it.sku_id,
        "sku_code": it.sku.code if it.sku else None,
        "sku_name": it.sku.name if it.sku else None,
        "sku_spec": it.sku.spec if it.sku else None,
        "book_qty": it.book_qty,
        "counted_qty": it.counted_qty,
        "diff_qty": it.diff_qty,
        "adjusted_qty": it.adjusted_qty,
        "remark": it.remark,
    }


def stocktake_out(st: Stocktake, with_items: bool = True) -> dict:
    data = {
        "id": st.id,
        "code": st.code,
        "status": st.status,
        "scope": st.scope,
        "warehouse_id": st.warehouse_id,
        "warehouse_code": st.warehouse.code if st.warehouse else None,
        "warehouse_name": st.warehouse.name if st.warehouse else None,
        "total_items": st.total_items,
        "counted_items": st.counted_items,
        "diff_items": st.diff_items,
        "counted_at": st.counted_at.isoformat() if st.counted_at else None,
        "confirmed_at": st.confirmed_at.isoformat() if st.confirmed_at else None,
        "confirmed_by": st.confirmed_by,
        "remark": st.remark,
        "created_by": st.created_by,
        "created_at": st.created_at.isoformat() if st.created_at else None,
    }
    if with_items:
        data["items"] = [_item_out(it) for it in (st.items or [])]
    return data


# ── 查询 ──

def get_stocktake(db: Session, stocktake_id: int) -> Stocktake | None:
    return db.scalar(
        select(Stocktake)
        .where(Stocktake.id == stocktake_id)
        .options(
            selectinload(Stocktake.warehouse),
            selectinload(Stocktake.items).selectinload(StocktakeItem.sku),
        )
    )


def list_stocktakes(
    db: Session,
    warehouse_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Stocktake]:
    stmt = select(Stocktake).options(selectinload(Stocktake.warehouse))
    if warehouse_id is not None:
        stmt = stmt.where(Stocktake.warehouse_id == warehouse_id)
    if status:
        stmt = stmt.where(Stocktake.status == status)
    stmt = stmt.order_by(Stocktake.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def count_stocktakes(
    db: Session,
    warehouse_id: int | None = None,
    status: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(Stocktake)
    if warehouse_id is not None:
        stmt = stmt.where(Stocktake.warehouse_id == warehouse_id)
    if status:
        stmt = stmt.where(Stocktake.status == status)
    return int(db.scalar(stmt) or 0)


# ── 制单 ──

def create_stocktake(
    db: Session,
    *,
    code: str,
    warehouse_id: int,
    item_type: str | None = None,
    sku_ids: list[int] | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> Stocktake:
    """建盘点单并把账面数快照进明细。

    - 传 `sku_ids` → 只盘这几个型号（循环盘点常用），账面为 0 也照样生成一行（为了能录盘盈）
    - 不传 → 按 `item_type`（all/product/material）把该仓库现有库存行全部快照进来
    """
    st = Stocktake(
        code=code,
        warehouse_id=warehouse_id,
        status="draft",
        scope="selected" if sku_ids else (item_type or "all"),
        remark=remark,
        created_by=created_by,
    )
    db.add(st)
    db.flush()

    rows: list[StocktakeItem] = []

    if sku_ids:
        wanted = list(dict.fromkeys(int(x) for x in sku_ids))
        existing = {
            int(s.sku_id): int(s.qty or 0)
            for s in db.scalars(
                select(Stock).where(
                    Stock.warehouse_id == warehouse_id, Stock.sku_id.in_(wanted)
                )
            ).all()
        }
        known = set(db.scalars(select(Sku.id).where(Sku.id.in_(wanted))).all())
        missing = [x for x in wanted if x not in known]
        if missing:
            raise ValueError(f"型号不存在：{missing}")
        for sku_id in wanted:
            rows.append(StocktakeItem(stocktake_id=st.id, sku_id=sku_id, book_qty=existing.get(sku_id, 0)))
    else:
        stmt = select(Stock).where(Stock.warehouse_id == warehouse_id)
        if item_type == "material":
            stmt = stmt.join(Sku, Sku.id == Stock.sku_id).where(Sku.code.like("MAT-%"))
        elif item_type == "product":
            stmt = stmt.join(Sku, Sku.id == Stock.sku_id).where(~Sku.code.like("MAT-%"))
        for s in db.scalars(stmt.order_by(Stock.sku_id)).all():
            rows.append(StocktakeItem(stocktake_id=st.id, sku_id=int(s.sku_id), book_qty=int(s.qty or 0)))

    if not rows:
        raise ValueError("该范围内没有库存行可盘：请换仓库/类型，或指定型号建单")
    db.add_all(rows)
    db.flush()
    db.refresh(st)
    _recount(st)
    db.flush()
    return st


# ── 明细维护 ──

def _editable(st: Stocktake, action: str) -> None:
    if st.status not in _EDITABLE:
        raise StocktakeStateError(f"盘点单当前状态为 {st.status}，不允许{action}")


def record_counts(
    db: Session,
    st: Stocktake,
    counts: list[dict],
) -> Stocktake:
    """批量录入实盘数。counts 每项形如 {item_id, counted_qty, remark?}。

    未在 counts 里出现的行保持"未盘"，确认时不会动它们——这样循环盘点可以分批录。
    """
    _editable(st, "录入实盘数")
    by_id = {int(it.id): it for it in (st.items or [])}
    now = _now()
    for row in counts:
        item_id = int(row["item_id"])
        it = by_id.get(item_id)
        if it is None:
            raise ValueError(f"明细行 {item_id} 不属于该盘点单")
        # 已确认入账的行不允许再被后到的录入覆盖（正常路径走不到，防重复提交）
        if it.adjusted_qty is not None:
            raise StocktakeStateError("该行已入账，不能再改实盘数")
        counted = int(row["counted_qty"])
        if counted < 0:
            raise ValueError(f"{it.sku.code if it.sku else item_id} 实盘数不能为负")
        it.counted_qty = counted
        it.diff_qty = counted - int(it.book_qty or 0)
        if row.get("remark") is not None:
            it.remark = row["remark"]
    if any(it.counted_qty is not None for it in (st.items or [])):
        st.status = "counting"
        st.counted_at = now
    _recount(st)
    db.flush()
    return st


def add_item(db: Session, st: Stocktake, sku_id: int, remark: str | None = None) -> StocktakeItem:
    """往盘点单里补一行（盘盈物资：账上根本没有这个型号的库存行）。"""
    _editable(st, "追加盘点行")
    sku = db.get(Sku, int(sku_id))
    if not sku:
        raise ValueError("型号不存在")
    exists = db.scalar(
        select(StocktakeItem.id).where(
            StocktakeItem.stocktake_id == st.id, StocktakeItem.sku_id == int(sku_id)
        )
    )
    if exists:
        raise ValueError(f"{sku.code} 已在盘点单中")
    s = db.scalar(
        select(Stock).where(
            Stock.warehouse_id == st.warehouse_id, Stock.sku_id == int(sku_id)
        )
    )
    it = StocktakeItem(
        stocktake_id=st.id,
        sku_id=int(sku_id),
        book_qty=int(s.qty or 0) if s else 0,
        remark=remark,
    )
    db.add(it)
    db.flush()
    db.refresh(st)
    _recount(st)
    db.flush()
    return it


def remove_item(db: Session, st: Stocktake, item_id: int) -> None:
    _editable(st, "删除盘点行")
    it = db.get(StocktakeItem, int(item_id))
    if not it or it.stocktake_id != st.id:
        raise ValueError("盘点行不存在")
    if it.counted_qty is not None:
        raise ValueError("该行已录实盘数，先清空实盘数才能删除")
    db.delete(it)
    db.flush()
    db.refresh(st)
    _recount(st)
    db.flush()


# ── 确认 / 作废 ──

def confirm_stocktake(db: Session, st: Stocktake, confirmed_by: int | None = None) -> dict:
    """确认入账：逐行把「实盘 − 当前账面」写成 stocktake 流水，并把盘点单置为终态。

    返回摘要（调整行数、盘盈/盘亏数量），供接口原样回给前端。
    """
    _editable(st, "确认入账")
    counted = [it for it in (st.items or []) if it.counted_qty is not None]
    if not counted:
        raise ValueError("还没有任何一行录入实盘数，无法确认")

    gain = loss = 0
    changed = 0
    for it in counted:
        # 先加行锁读当前账面：制单快照可能已经过期，入账必须基于此刻的真实库存
        cur = int(lock_stock(db, st.warehouse_id, it.sku_id).qty or 0)
        delta = int(it.counted_qty) - cur
        it.adjusted_qty = delta
        if delta == 0:
            continue
        adjust_stock(
            db,
            warehouse_id=st.warehouse_id,
            sku_id=it.sku_id,
            change_qty=delta,
            biz_type="stocktake",
            biz_id=st.id,
            remark=f"盘点#{st.code} 实盘 {it.counted_qty} / 账面 {cur}",
        )
        changed += 1
        if delta > 0:
            gain += delta
        else:
            loss += -delta

    st.status = "confirmed"
    st.confirmed_at = _now()
    st.confirmed_by = confirmed_by
    _recount(st)
    db.flush()
    return {
        "adjusted_lines": changed,
        "gain_qty": gain,
        "loss_qty": loss,
        "stocktake": stocktake_out(st),
    }


def cancel_stocktake(db: Session, st: Stocktake) -> Stocktake:
    if st.status == "confirmed":
        raise StocktakeStateError("已确认入账的盘点单不能作废，若盘错了请再做一次盘点纠正")
    if st.status == "cancelled":
        raise StocktakeStateError("盘点单已作废")
    st.status = "cancelled"
    db.flush()
    return st
