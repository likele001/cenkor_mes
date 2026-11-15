# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""批次库存查询、效期预警与追溯。

只读，全部数据来自 stock_batch / stock_ledger（由 fifo 服务写入），
这里不写任何业务表 —— 想改批次数量走 /stocks/adjust 或盘点，不在这里直接 UPDATE。

路由顺序注意：/batches/expiry-alerts 必须排在 /batches/{batch_id} 之前，
否则 "expiry-alerts" 会被当成 batch_id 去解析（FastAPI 按注册顺序匹配）。
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.models.sku import Sku
from app.models.user import User
from app.models.warehouse import (
    StockBatch,
    StockLedger,
    Warehouse,
    WarehouseLocation,
)
from app.services.warehouse import fifo, trace

BATCH_STATUS_LABELS = {
    "qualified": "合格",
    "held": "冻结",
    "rejected": "不合格",
    "expired": "已过期",
}


def _tenant_id(user: User) -> int:
    return int(getattr(user, "tenant_id", 1) or 1)


router = APIRouter()


@router.get("/batches")
def list_batches_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    location_id: int | None = Query(default=None, ge=1),
    sku_id: int | None = Query(default=None, ge=1),
    batch_no: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, max_length=16),
    expiring_days: int | None = Query(default=None, ge=-3650, le=3650),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """批次列表。expiring_days=30 表示只看 30 天内到期（含已过期，负数天）。"""
    tid = _tenant_id(user)
    stmt = select(StockBatch, Sku, WarehouseLocation).join(Sku, Sku.id == StockBatch.sku_id).outerjoin(
        WarehouseLocation, WarehouseLocation.id == StockBatch.location_id
    ).where(StockBatch.tenant_id == tid)

    if warehouse_id is not None:
        stmt = stmt.where(StockBatch.warehouse_id == warehouse_id)
    if location_id is not None:
        stmt = stmt.where(StockBatch.location_id == location_id)
    if sku_id is not None:
        stmt = stmt.where(StockBatch.sku_id == sku_id)
    if batch_no:
        like = f"%{batch_no}%"
        stmt = stmt.where(or_(StockBatch.batch_no.like(like), StockBatch.supplier_batch_no.like(like)))
    if status:
        stmt = stmt.where(StockBatch.status == status)
    if expiring_days is not None:
        limit_day = date.today() + timedelta(days=expiring_days)
        stmt = stmt.where(StockBatch.expiry_date.is_not(None), StockBatch.expiry_date <= limit_day)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(StockBatch.expiry_date.is_(None), StockBatch.expiry_date, StockBatch.id)
        .offset(offset)
        .limit(limit)
    ).all()

    today = date.today()
    items = []
    for b, s, loc in rows:
        days = (b.expiry_date - today).days if b.expiry_date else None
        items.append(
            {
                "id": b.id,
                "batch_no": b.batch_no,
                "supplier_batch_no": b.supplier_batch_no,
                "warehouse_id": b.warehouse_id,
                "location_id": b.location_id,
                "location_code": loc.code if loc else None,
                "sku_id": b.sku_id,
                "sku_code": s.code,
                "sku_name": s.name,
                "qty_on_hand": int(b.qty_on_hand or 0),
                "qty_reserved": int(b.qty_reserved or 0),
                "available": max(0, int(b.qty_on_hand or 0) - int(b.qty_reserved or 0)),
                "status": b.status,
                "status_label": BATCH_STATUS_LABELS.get(b.status, b.status),
                "mfg_date": b.mfg_date,
                "expiry_date": b.expiry_date,
                "days_to_expiry": days,
                "tier": fifo.expiry_level(days),
            }
        )
    return ok({"total": int(total), "items": items, "offset": offset, "limit": limit})


@router.get("/batches/expiry-alerts")
def expiry_alerts_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    days: int = Query(default=90, ge=1, le=3650),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """效期分档预警 T-90 / T-30 / T-7 / 已过期，直接复用核心 fifo.expiry_alerts。"""
    return ok(fifo.expiry_alerts(db, tenant_id=_tenant_id(user), warehouse_id=warehouse_id, days=days))


@router.get("/batches/{batch_id}/flows")
def batch_flows_api(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """单个批次的出入库流水（按发生时间正序）。"""
    tid = _tenant_id(user)
    batch = db.scalar(
        select(StockBatch).where(StockBatch.id == batch_id, StockBatch.tenant_id == tid)
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="批次不存在")

    rows = db.execute(
        select(StockLedger, WarehouseLocation.code)
        .outerjoin(WarehouseLocation, WarehouseLocation.id == StockLedger.location_id)
        .where(StockLedger.tenant_id == tid, StockLedger.batch_id == batch_id)
        .order_by(StockLedger.occurred_at, StockLedger.id)
    ).all()
    return ok(
        {
            "batch": {
                "id": batch.id,
                "batch_no": batch.batch_no,
                "qty_on_hand": int(batch.qty_on_hand or 0),
                "status": batch.status,
                "expiry_date": batch.expiry_date,
            },
            "items": [
                {
                    "id": lg.id,
                    "qty_delta": int(lg.qty_delta or 0),
                    "biz_type": lg.biz_type,
                    "ref_type": lg.ref_type,
                    "ref_id": lg.ref_id,
                    "location_code": loc_code,
                    "operator_id": lg.operator_id,
                    "occurred_at": lg.occurred_at,
                    "remark": lg.remark,
                }
                for lg, loc_code in rows
            ],
        }
    )


@router.get("/trace/forward")
def trace_forward_api(
    batch_no: str = Query(min_length=1, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """正向追溯：批次 → 全部出入库流水（含单据号）。"""
    return ok(trace.trace_forward(db, tenant_id=_tenant_id(user), batch_no=batch_no))


@router.get("/trace/backward")
def trace_backward_api(
    ref_type: str = Query(min_length=1, max_length=32),
    ref_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """反向追溯：单据 → 消耗掉的批次清单。"""
    return ok(trace.trace_backward(db, tenant_id=_tenant_id(user), ref_type=ref_type, ref_id=ref_id))


@router.get("/warehouses/{warehouse_id}/summary")
def warehouse_summary_api(
    warehouse_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """单仓概览：库区数 / 库位数 / 批次数 / 总量 / 临期与过期量。"""
    tid = _tenant_id(user)
    wh = db.scalar(select(Warehouse).where(Warehouse.id == warehouse_id))
    if wh is None:
        raise HTTPException(status_code=404, detail="仓库不存在")

    from app.models.warehouse import WarehouseZone

    zone_cnt = db.scalar(
        select(func.count(WarehouseZone.id)).where(
            WarehouseZone.tenant_id == tid, WarehouseZone.warehouse_id == warehouse_id
        )
    )
    loc_cnt = db.scalar(
        select(func.count(WarehouseLocation.id)).where(
            WarehouseLocation.tenant_id == tid, WarehouseLocation.warehouse_id == warehouse_id
        )
    )
    batch_cnt = db.scalar(
        select(func.count(StockBatch.id)).where(
            StockBatch.tenant_id == tid, StockBatch.warehouse_id == warehouse_id
        )
    )
    qty = db.scalar(
        select(func.coalesce(func.sum(StockBatch.qty_on_hand), 0)).where(
            StockBatch.tenant_id == tid, StockBatch.warehouse_id == warehouse_id
        )
    )
    today = date.today()
    expiring_qty = db.scalar(
        select(func.coalesce(func.sum(StockBatch.qty_on_hand), 0)).where(
            StockBatch.tenant_id == tid,
            StockBatch.warehouse_id == warehouse_id,
            StockBatch.expiry_date.is_not(None),
            StockBatch.expiry_date <= today + timedelta(days=30),
            StockBatch.expiry_date >= today,
        )
    )
    expired_qty = db.scalar(
        select(func.coalesce(func.sum(StockBatch.qty_on_hand), 0)).where(
            StockBatch.tenant_id == tid,
            StockBatch.warehouse_id == warehouse_id,
            StockBatch.expiry_date.is_not(None),
            StockBatch.expiry_date < today,
        )
    )
    return ok(
        {
            "warehouse": {"id": wh.id, "code": wh.code, "name": wh.name},
            "zone_count": int(zone_cnt or 0),
            "location_count": int(loc_cnt or 0),
            "batch_count": int(batch_cnt or 0),
            "qty_on_hand": int(qty or 0),
            "expiring_qty_30d": int(expiring_qty or 0),
            "expired_qty": int(expired_qty or 0),
        }
    )
