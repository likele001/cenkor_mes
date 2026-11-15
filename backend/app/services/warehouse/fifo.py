"""库位 + 批次/效期 + FIFO 服务层。

新台账（stock_batch / stock_ledger）为准；旧 stocks / stock_logs 通过
`adjust_stock` 双写，失败只记日志，不阻断新流程。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import case, select
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud.platform_setting import get_setting
from app.crud.warehouse import adjust_stock
from app.models.code_sequence import CodeSequence
from app.models.sku import Sku
from app.models.warehouse import StockBatch, StockLedger, Warehouse, WarehouseLocation

logger = logging.getLogger(__name__)


# ── 库位 ──

def ensure_default_location(db: Session, tenant_id: int, warehouse_id: int) -> WarehouseLocation:
    """取（或建）仓库默认库位 code='DEFAULT'。"""
    loc = db.scalar(
        select(WarehouseLocation).where(
            WarehouseLocation.tenant_id == tenant_id,
            WarehouseLocation.warehouse_id == warehouse_id,
            WarehouseLocation.code == "DEFAULT",
        )
    )
    if loc:
        return loc
    loc = WarehouseLocation(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        code="DEFAULT",
        name="默认库位",
        location_type="bin",
        is_active=True,
    )
    try:
        # 并发首插撞唯一键时只回滚 savepoint，外层事务不受影响
        with db.begin_nested():
            db.add(loc)
    except IntegrityError:
        pass
    loc = db.scalar(
        select(WarehouseLocation).where(
            WarehouseLocation.tenant_id == tenant_id,
            WarehouseLocation.warehouse_id == warehouse_id,
            WarehouseLocation.code == "DEFAULT",
        )
    )
    if loc is None:
        raise RuntimeError(f"默认库位创建失败（仓库 {warehouse_id}）")
    return loc


# ── 批次号 ──

def generate_batch_no(db: Session, tenant_id: int) -> str:
    """前缀 + YYYYMMDD + 4 位当日流水。"""
    prefix = (get_setting(db, "wms.batch_prefix") or "").strip() or "B"
    period_key = datetime.now().strftime("%Y%m%d")
    row = db.scalar(
        select(CodeSequence)
        .where(
            CodeSequence.biz_type == "stock_batch",
            CodeSequence.period_key == period_key,
        )
        .with_for_update()
    )
    if row is None:
        row = CodeSequence(
            tenant_id=tenant_id,
            biz_type="stock_batch",
            period_key=period_key,
            last_value=0,
        )
        db.add(row)
        db.flush()
    row.last_value += 1
    db.flush()
    return f"{prefix}{period_key}{row.last_value:04d}"


# ── 效期 ──

def days_to_expiry(expiry_date: date | None) -> int | None:
    if expiry_date is None:
        return None
    return (expiry_date - date.today()).days


def expiry_level(days: int | None) -> str:
    if days is None:
        return "none"
    if days < 0:
        return "expired"
    if days <= 7:
        return "q7"
    if days <= 30:
        return "q30"
    if days <= 90:
        return "q90"
    return "ok"


# ── FIFO 排序与可分配量 ──

def fifo_order() -> list:
    """效期升序（NULL 最后）→ 生产日期 → id；MySQL 5.7 无 NULLS LAST。"""
    return [
        case((StockBatch.expiry_date.is_(None), 1), else_=0).asc(),
        StockBatch.expiry_date.asc(),
        StockBatch.mfg_date.asc(),
        StockBatch.id.asc(),
    ]


def available_qty(batch: StockBatch) -> int:
    return max(0, int(batch.qty_on_hand or 0) - int(batch.qty_reserved or 0))


def list_available(
    db: Session,
    *,
    tenant_id: int,
    warehouse_id: int,
    sku_id: int,
    need_qty: int | None = None,
) -> list[dict]:
    """按 FIFO 列出可分配批次；need_qty 非空时给出建议分配量。"""
    stmt = (
        select(StockBatch, WarehouseLocation)
        .outerjoin(WarehouseLocation, WarehouseLocation.id == StockBatch.location_id)
        .where(
            StockBatch.tenant_id == tenant_id,
            StockBatch.warehouse_id == warehouse_id,
            StockBatch.sku_id == sku_id,
            StockBatch.status == "qualified",
            StockBatch.qty_on_hand - StockBatch.qty_reserved > 0,
        )
        .order_by(*fifo_order())
    )
    rows = db.execute(stmt).all()

    result: list[dict] = []
    remaining = int(need_qty) if need_qty is not None else 0
    cumulative = 0
    for batch, loc in rows:
        available = available_qty(batch)
        if available <= 0:
            continue
        suggested = 0
        if need_qty is not None and remaining > 0:
            suggested = min(available, remaining)
            remaining -= suggested
            cumulative += suggested
        days = days_to_expiry(batch.expiry_date)
        result.append(
            {
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "supplier_batch_no": batch.supplier_batch_no,
                "location_id": batch.location_id,
                "location_code": loc.code if loc else None,
                "location_name": loc.name if loc else None,
                "mfg_date": batch.mfg_date,
                "expiry_date": batch.expiry_date,
                "days_to_expiry": days,
                "available": available,
                "suggested_qty": suggested,
                "cumulative": cumulative,
            }
        )
    return result


# ── 分配 ──

def allocate(
    db: Session,
    *,
    tenant_id: int,
    warehouse_id: int,
    sku_id: int,
    qty: int,
    allocations: list[dict] | None = None,
) -> list[dict]:
    """返回 [{batch_id, qty}]；allocations 为空时按 FIFO 自动分配。"""
    if qty <= 0:
        raise ValueError("数量必须大于 0")

    if allocations is None:
        rows = list_available(
            db, tenant_id=tenant_id, warehouse_id=warehouse_id, sku_id=sku_id, need_qty=qty
        )
        plan: list[dict] = []
        remaining = qty
        for row in rows:
            if remaining <= 0:
                break
            take = min(int(row["available"]), remaining)
            if take <= 0:
                continue
            plan.append({"batch_id": row["batch_id"], "qty": take})
            remaining -= take
        if remaining > 0:
            raise ValueError(f"库存不足（需要 {qty}，可分配 {qty - remaining}）")
        return plan

    plan = []
    seen: set[int] = set()
    for item in allocations:
        batch_id = int(item.get("batch_id") or 0)
        take = int(item.get("qty") or 0)
        if take <= 0:
            raise ValueError("分配数量必须大于 0")
        # 同一批次只能出现一次：重复行会各自通过可分配量校验，扣减时累加成负库存
        if batch_id in seen:
            raise ValueError(f"批次 {batch_id} 重复分配，请合并数量后重试")
        seen.add(batch_id)
        batch = db.scalar(
            select(StockBatch).where(
                StockBatch.id == batch_id,
                StockBatch.tenant_id == tenant_id,
                StockBatch.warehouse_id == warehouse_id,
                StockBatch.sku_id == sku_id,
            )
        )
        if batch is None:
            raise ValueError(f"批次 {batch_id} 不存在或不属于当前仓库/型号")
        if batch.status != "qualified":
            raise ValueError("批次已冻结或不合格，禁止出库")
        if available_qty(batch) < take:
            raise ValueError(f"批次 {batch.batch_no} 可分配量不足")
        plan.append({"batch_id": batch.id, "qty": take})
    if not plan:
        raise ValueError("数量必须大于 0")
    total = sum(p["qty"] for p in plan)
    if total != qty:
        raise ValueError(f"分配数量合计 {total} 与出库数量 {qty} 不一致")
    return plan


# ── 出库 ──

def issue(
    db: Session,
    *,
    tenant_id: int,
    warehouse_id: int,
    sku_id: int,
    qty: int,
    biz_type: str = "material_issue",
    ref_type: str | None = None,
    ref_id: int | None = None,
    operator_id: int | None = None,
    remark: str | None = None,
    allocations: list[dict] | None = None,
    sync_legacy: bool = True,
) -> dict:
    plan = allocate(
        db,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        sku_id=sku_id,
        qty=qty,
        allocations=allocations,
    )
    ids = sorted({p["batch_id"] for p in plan})
    locked = {
        b.id: b
        for b in db.scalars(
            select(StockBatch)
            .where(StockBatch.id.in_(ids), StockBatch.tenant_id == tenant_id)
            .order_by(StockBatch.id.asc())
            .with_for_update()
            # 必须强制覆盖 ORM 缓存：分配阶段可能已把批次读进 identity map，
            # 若此时另一个请求已提交扣减，缓存里的旧数量会让锁内复核失效。
            .execution_options(populate_existing=True)
        ).all()
    }
    # 锁内复核，避免分配后数量被并发改动
    for p in plan:
        batch = locked.get(p["batch_id"])
        if batch is None:
            raise ValueError(f"批次 {p['batch_id']} 不存在")
        if batch.status != "qualified":
            raise ValueError("批次已冻结或不合格，禁止出库")
        if available_qty(batch) < p["qty"]:
            raise ValueError(f"批次 {batch.batch_no} 可分配量不足")

    now = datetime.now()
    for p in plan:
        batch = locked[p["batch_id"]]
        # 条件更新兜底：即便缓存/锁失效，数据库也不会把数量扣成负数
        result = db.execute(
            sa_update(StockBatch)
            .where(
                StockBatch.id == batch.id,
                StockBatch.tenant_id == tenant_id,
                StockBatch.status == "qualified",
                StockBatch.qty_on_hand - StockBatch.qty_reserved >= p["qty"],
            )
            .values(qty_on_hand=StockBatch.qty_on_hand - p["qty"])
            .execution_options(synchronize_session=False)
        )
        if not result.rowcount:
            raise ValueError(f"批次 {batch.batch_no} 可分配量不足")
        db.expire(batch, ["qty_on_hand"])
        db.add(
            StockLedger(
                tenant_id=tenant_id,
                batch_id=batch.id,
                location_id=batch.location_id,
                sku_id=sku_id,
                qty_delta=-p["qty"],
                biz_type=biz_type,
                ref_type=ref_type,
                ref_id=ref_id,
                occurred_at=now,
                operator_id=operator_id,
                remark=remark,
            )
        )
    db.flush()

    if sync_legacy:
        try:
            adjust_stock(
                db,
                warehouse_id=warehouse_id,
                sku_id=sku_id,
                change_qty=-qty,
                biz_type=biz_type,
                biz_id=ref_id,
                remark=remark,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "旧库存双写失败（出库）: tenant=%s warehouse=%s sku=%s qty=%s",
                tenant_id,
                warehouse_id,
                sku_id,
                qty,
            )
    db.flush()

    return {
        "allocations": [
            {
                "batch_id": p["batch_id"],
                "batch_no": locked[p["batch_id"]].batch_no,
                "qty": p["qty"],
            }
            for p in plan
        ],
        "total_qty": qty,
        "biz_type": biz_type,
    }


# ── 入库 ──

def receive(
    db: Session,
    *,
    tenant_id: int,
    warehouse_id: int,
    sku_id: int,
    qty: int,
    batch_no: str | None = None,
    location_id: int | None = None,
    supplier_batch_no: str | None = None,
    mfg_date: date | None = None,
    expiry_date: date | None = None,
    status: str | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    operator_id: int | None = None,
    biz_type: str = "purchase_in",
    ref_type: str | None = None,
    ref_id: int | None = None,
    remark: str | None = None,
    sync_legacy: bool = True,
) -> StockBatch:
    if qty <= 0:
        raise ValueError("数量必须大于 0")

    if location_id is None:
        location_id = ensure_default_location(db, tenant_id, warehouse_id).id
    else:
        loc = db.scalar(
            select(WarehouseLocation).where(
                WarehouseLocation.id == location_id,
                WarehouseLocation.tenant_id == tenant_id,
                WarehouseLocation.warehouse_id == warehouse_id,
            )
        )
        if loc is None:
            raise ValueError("库位不存在或不属于该仓库")

    batch_no = (batch_no or "").strip() or generate_batch_no(db, tenant_id)
    batch = db.scalar(
        select(StockBatch)
        .where(
            StockBatch.tenant_id == tenant_id,
            StockBatch.warehouse_id == warehouse_id,
            StockBatch.location_id == location_id,
            StockBatch.sku_id == sku_id,
            StockBatch.batch_no == batch_no,
        )
        .with_for_update()
    )
    if batch is not None:
        if supplier_batch_no and not batch.supplier_batch_no:
            batch.supplier_batch_no = supplier_batch_no
        if mfg_date is not None and batch.mfg_date is None:
            batch.mfg_date = mfg_date
        if expiry_date is not None and batch.expiry_date is None:
            batch.expiry_date = expiry_date
    else:
        batch = StockBatch(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            location_id=location_id,
            sku_id=sku_id,
            batch_no=batch_no,
            supplier_batch_no=supplier_batch_no,
            mfg_date=mfg_date,
            expiry_date=expiry_date,
            qty_on_hand=0,
            qty_reserved=0,
            status=status or "qualified",
            source_type=source_type,
            source_id=source_id,
        )
        db.add(batch)
        db.flush()

    db.add(
        StockLedger(
            tenant_id=tenant_id,
            batch_id=batch.id,
            location_id=location_id,
            sku_id=sku_id,
            qty_delta=qty,
            biz_type=biz_type,
            ref_type=ref_type,
            ref_id=ref_id,
            occurred_at=datetime.now(),
            operator_id=operator_id,
            remark=remark,
        )
    )
    db.flush()
    batch.qty_on_hand = (batch.qty_on_hand or 0) + qty
    db.flush()

    if sync_legacy:
        try:
            adjust_stock(
                db,
                warehouse_id=warehouse_id,
                sku_id=sku_id,
                change_qty=qty,
                biz_type=biz_type,
                biz_id=ref_id,
                remark=remark,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "旧库存双写失败（入库）: tenant=%s warehouse=%s sku=%s qty=%s",
                tenant_id,
                warehouse_id,
                sku_id,
                qty,
            )
    db.flush()
    return batch


# ── 移库 ──

def move(
    db: Session,
    *,
    tenant_id: int,
    batch_id: int,
    to_location_id: int,
    operator_id: int | None = None,
    remark: str | None = None,
    sync_legacy: bool = True,
) -> StockBatch:
    batch = db.scalar(
        select(StockBatch)
        .where(StockBatch.id == batch_id, StockBatch.tenant_id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if batch is None:
        raise ValueError("批次不存在")
    target = db.scalar(
        select(WarehouseLocation).where(
            WarehouseLocation.id == to_location_id,
            WarehouseLocation.tenant_id == tenant_id,
        )
    )
    if target is None:
        raise ValueError("目标库位不存在")
    if batch.location_id == to_location_id:
        raise ValueError("批次已在目标库位")

    qty = int(batch.qty_on_hand or 0)
    old_warehouse_id = batch.warehouse_id
    old_location_id = batch.location_id

    if qty != 0:
        now = datetime.now()
        db.add(
            StockLedger(
                tenant_id=tenant_id,
                batch_id=batch.id,
                location_id=old_location_id,
                sku_id=batch.sku_id,
                qty_delta=-qty,
                biz_type="move_out",
                occurred_at=now,
                operator_id=operator_id,
                remark=remark,
            )
        )
        db.add(
            StockLedger(
                tenant_id=tenant_id,
                batch_id=batch.id,
                location_id=target.id,
                sku_id=batch.sku_id,
                qty_delta=qty,
                biz_type="move_in",
                occurred_at=now,
                operator_id=operator_id,
                remark=remark,
            )
        )
        db.flush()

    batch.location_id = target.id
    batch.warehouse_id = target.warehouse_id
    db.flush()

    if sync_legacy and qty != 0 and old_warehouse_id != target.warehouse_id:
        for warehouse_id, change_qty in ((old_warehouse_id, -qty), (target.warehouse_id, qty)):
            try:
                adjust_stock(
                    db,
                    warehouse_id=warehouse_id,
                    sku_id=batch.sku_id,
                    change_qty=change_qty,
                    biz_type="move",
                    remark=remark,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "旧库存双写失败（移库）: tenant=%s warehouse=%s sku=%s qty=%s",
                    tenant_id,
                    warehouse_id,
                    batch.sku_id,
                    change_qty,
                )
        db.flush()
    return batch


# ── 批次调整 ──

def adjust(
    db: Session,
    *,
    tenant_id: int,
    batch_id: int,
    qty_delta: int,
    reason: str | None = None,
    operator_id: int | None = None,
    sync_legacy: bool = True,
) -> StockBatch:
    if qty_delta == 0:
        raise ValueError("调整数量不能为 0")
    batch = db.scalar(
        select(StockBatch)
        .where(StockBatch.id == batch_id, StockBatch.tenant_id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if batch is None:
        raise ValueError("批次不存在")

    new_qty = int(batch.qty_on_hand or 0) + qty_delta
    if new_qty < 0:
        raise ValueError("调整后数量不能为负")
    if new_qty < int(batch.qty_reserved or 0):
        raise ValueError("调整后数量不能小于已预留数量")

    # 条件更新兜底：并发调整/出库交错时，数据库层面也不会出现负库存
    result = db.execute(
        sa_update(StockBatch)
        .where(
            StockBatch.id == batch.id,
            StockBatch.tenant_id == tenant_id,
            StockBatch.qty_on_hand + qty_delta >= 0,
            StockBatch.qty_on_hand + qty_delta >= StockBatch.qty_reserved,
        )
        .values(qty_on_hand=StockBatch.qty_on_hand + qty_delta)
        .execution_options(synchronize_session=False)
    )
    if not result.rowcount:
        raise ValueError("调整后数量不能为负或小于已预留数量")
    db.expire(batch, ["qty_on_hand"])

    db.add(
        StockLedger(
            tenant_id=tenant_id,
            batch_id=batch.id,
            location_id=batch.location_id,
            sku_id=batch.sku_id,
            qty_delta=qty_delta,
            biz_type="adjust",
            ref_type="manual",
            occurred_at=datetime.now(),
            operator_id=operator_id,
            remark=reason,
        )
    )
    db.flush()

    if sync_legacy:
        try:
            adjust_stock(
                db,
                warehouse_id=batch.warehouse_id,
                sku_id=batch.sku_id,
                change_qty=qty_delta,
                biz_type="adjust",
                remark=reason,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "旧库存双写失败（调整）: tenant=%s batch=%s qty_delta=%s",
                tenant_id,
                batch.id,
                qty_delta,
            )
    db.flush()
    return batch


# ── 效期预警 ──

_EXPIRY_TIERS = ("T-7", "T-30", "T-90", "EXPIRED")


def expiry_alerts(
    db: Session,
    *,
    tenant_id: int,
    warehouse_id: int | None = None,
    days: int = 90,
) -> dict:
    today = date.today()
    limit = today + timedelta(days=days)
    stmt = (
        select(StockBatch, Sku, Warehouse, WarehouseLocation)
        .join(Sku, Sku.id == StockBatch.sku_id)
        .join(Warehouse, Warehouse.id == StockBatch.warehouse_id)
        .outerjoin(WarehouseLocation, WarehouseLocation.id == StockBatch.location_id)
        .where(
            StockBatch.tenant_id == tenant_id,
            StockBatch.status == "qualified",
            StockBatch.expiry_date.is_not(None),
            StockBatch.expiry_date <= limit,
            StockBatch.qty_on_hand - StockBatch.qty_reserved > 0,
        )
        .order_by(StockBatch.expiry_date.asc(), StockBatch.id.asc())
    )
    if warehouse_id is not None:
        stmt = stmt.where(StockBatch.warehouse_id == warehouse_id)
    rows = db.execute(stmt).all()

    summary = {"t7": 0, "t30": 0, "t90": 0, "expired": 0, "total": 0}
    tier_stat = {tier: {"tier": tier, "count": 0, "qty": 0} for tier in _EXPIRY_TIERS}
    items: list[dict] = []

    for batch, sku, warehouse, loc in rows:
        available = available_qty(batch)
        if available <= 0:
            continue
        d = days_to_expiry(batch.expiry_date)
        if d is None:
            continue
        if d < 0:
            tier = "EXPIRED"
            summary["expired"] += 1
        elif d <= 7:
            tier = "T-7"
            summary["t7"] += 1
        elif d <= 30:
            tier = "T-30"
            summary["t30"] += 1
        else:
            tier = "T-90"
            summary["t90"] += 1
        summary["total"] += 1
        tier_stat[tier]["count"] += 1
        tier_stat[tier]["qty"] += available
        items.append(
            {
                "id": batch.id,
                "batch_no": batch.batch_no,
                "sku_id": batch.sku_id,
                "sku_code": sku.code,
                "sku_name": sku.name,
                "warehouse_id": batch.warehouse_id,
                "warehouse_name": warehouse.name,
                "location_code": loc.code if loc else None,
                "supplier_batch_no": batch.supplier_batch_no,
                "mfg_date": batch.mfg_date,
                "expiry_date": batch.expiry_date,
                "days_to_expiry": d,
                "tier": tier,
                "is_expired": d < 0,
                "qty_on_hand": int(batch.qty_on_hand or 0),
                "qty_reserved": int(batch.qty_reserved or 0),
                "available": available,
            }
        )

    return {
        "days": days,
        "summary": summary,
        "tiers": [tier_stat[tier] for tier in _EXPIRY_TIERS],
        "items": items,
    }
