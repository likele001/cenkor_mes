# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""库位：库存真正落地的地方（库区 zone / 货架 rack / 货位 bin）。

库存按「仓库 + 库位 + 型号 + 批次」记在 stock_batch 上，所以库位一旦被批次
引用就不能删 —— 删掉会让批次变成无库位孤儿，MySQL 唯一键对 NULL 失效，
之后并发入库会重复计库存。要「去掉」一个库位请停用（is_active = false）。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.sku import Sku
from app.models.user import User
from app.models.warehouse import (
    StockBatch,
    Warehouse,
    WarehouseLocation,
    WarehouseZone,
)

LOCATION_TYPE_LABELS = {"zone": "库区", "rack": "货架", "bin": "货位"}


class LocationCreateIn(BaseModel):
    warehouse_id: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    zone_id: int | None = Field(default=None, ge=1)
    location_type: str = Field(default="bin", max_length=16)
    parent_id: int | None = Field(default=None, ge=1)
    capacity: int | None = Field(default=None, ge=0)
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class LocationUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    zone_id: int | None = Field(default=None, ge=1)
    location_type: str | None = Field(default=None, max_length=16)
    parent_id: int | None = Field(default=None, ge=1)
    capacity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


router = APIRouter()


def _tenant_id(user: User) -> int:
    return int(getattr(user, "tenant_id", 1) or 1)


def _location_out(loc: WarehouseLocation, zone_code: str | None = None, qty: int = 0, sku_count: int = 0) -> dict:
    return {
        "id": loc.id,
        "warehouse_id": loc.warehouse_id,
        "code": loc.code,
        "name": loc.name,
        "zone_id": loc.zone_id,
        "zone_code": zone_code,
        "location_type": loc.location_type,
        "location_type_label": LOCATION_TYPE_LABELS.get(loc.location_type, loc.location_type),
        "parent_id": loc.parent_id,
        "capacity": loc.capacity,
        "is_active": bool(loc.is_active),
        "remark": loc.remark,
        "qty_on_hand": qty,
        "sku_count": sku_count,
        # 没配容量的库位不显示 0% —— 0% 会被误读成「空置」，实际是「没配容量」
        "usage_pct": round(qty / loc.capacity * 100, 1) if loc.capacity else None,
    }


@router.get("/locations")
def list_locations_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    zone_id: int | None = Query(default=None, ge=1),
    is_active: bool | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    stmt = select(WarehouseLocation).where(WarehouseLocation.tenant_id == tid)
    if warehouse_id is not None:
        stmt = stmt.where(WarehouseLocation.warehouse_id == warehouse_id)
    if zone_id is not None:
        stmt = stmt.where(WarehouseLocation.zone_id == zone_id)
    if is_active is not None:
        stmt = stmt.where(WarehouseLocation.is_active.is_(is_active))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(WarehouseLocation.code.like(like), WarehouseLocation.name.like(like)))
    locs = db.scalars(stmt.order_by(WarehouseLocation.warehouse_id, WarehouseLocation.code)).all()

    # 库位上的库存量：一次 group by 取完（三元组不能直接 dict()，要自己收口）
    agg = {
        row[0]: (row[1], row[2])
        for row in db.execute(
            select(
                StockBatch.location_id,
                func.coalesce(func.sum(StockBatch.qty_on_hand), 0),
                func.count(func.distinct(StockBatch.sku_id)),
            )
            .where(StockBatch.tenant_id == tid)
            .group_by(StockBatch.location_id)
        ).all()
    }
    zone_codes = dict(
        db.execute(
            select(WarehouseZone.id, WarehouseZone.code).where(WarehouseZone.tenant_id == tid)
        ).all()
    )
    items = []
    for loc in locs:
        qty, sku_cnt = agg.get(loc.id, (0, 0))
        items.append(_location_out(loc, zone_codes.get(loc.zone_id), int(qty or 0), int(sku_cnt or 0)))
    return ok({"items": items})


@router.get("/locations/{location_id}/stock")
def location_stock_api(
    location_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    loc = db.scalar(
        select(WarehouseLocation).where(
            WarehouseLocation.id == location_id, WarehouseLocation.tenant_id == tid
        )
    )
    if loc is None:
        raise HTTPException(status_code=404, detail="库位不存在")

    rows = db.execute(
        select(StockBatch, Sku)
        .join(Sku, Sku.id == StockBatch.sku_id)
        .where(StockBatch.tenant_id == tid, StockBatch.location_id == location_id)
        .order_by(StockBatch.expiry_date.is_(None), StockBatch.expiry_date, StockBatch.id)
    ).all()
    return ok(
        {
            "location": _location_out(loc),
            "items": [
                {
                    "batch_id": b.id,
                    "batch_no": b.batch_no,
                    "sku_id": b.sku_id,
                    "sku_code": s.code,
                    "sku_name": s.name,
                    "qty_on_hand": int(b.qty_on_hand or 0),
                    "qty_reserved": int(b.qty_reserved or 0),
                    "available": max(0, int(b.qty_on_hand or 0) - int(b.qty_reserved or 0)),
                    "status": b.status,
                    "expiry_date": b.expiry_date,
                }
                for b, s in rows
            ],
        }
    )


@router.post("/locations", dependencies=[Depends(require_permissions(["warehouse.manage"]))])
def create_location_api(
    payload: LocationCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    if db.scalar(select(Warehouse.id).where(Warehouse.id == payload.warehouse_id)) is None:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if payload.zone_id is not None:
        zone = db.scalar(
            select(WarehouseZone).where(
                WarehouseZone.id == payload.zone_id, WarehouseZone.tenant_id == tid
            )
        )
        if zone is None:
            raise HTTPException(status_code=404, detail="库区不存在")
        if zone.warehouse_id != payload.warehouse_id:
            raise HTTPException(status_code=400, detail="库区不属于该仓库")

    exists = db.scalar(
        select(WarehouseLocation.id).where(
            WarehouseLocation.tenant_id == tid,
            WarehouseLocation.warehouse_id == payload.warehouse_id,
            WarehouseLocation.code == payload.code,
        )
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail=f"该仓库下库位编码 {payload.code} 已存在")

    loc = WarehouseLocation(
        tenant_id=tid,
        warehouse_id=payload.warehouse_id,
        code=payload.code,
        name=payload.name,
        zone_id=payload.zone_id,
        location_type=payload.location_type,
        parent_id=payload.parent_id,
        capacity=payload.capacity,
        is_active=payload.is_active,
        remark=payload.remark,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    zone_code = db.scalar(select(WarehouseZone.code).where(WarehouseZone.id == loc.zone_id)) if loc.zone_id else None
    return ok(_location_out(loc, zone_code))


@router.put("/locations/{location_id}", dependencies=[Depends(require_permissions(["warehouse.manage"]))])
def update_location_api(
    location_id: int,
    payload: LocationUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    loc = db.scalar(
        select(WarehouseLocation).where(
            WarehouseLocation.id == location_id, WarehouseLocation.tenant_id == tid
        )
    )
    if loc is None:
        raise HTTPException(status_code=404, detail="库位不存在")

    if payload.zone_id is not None:
        zone = db.scalar(
            select(WarehouseZone).where(
                WarehouseZone.id == payload.zone_id, WarehouseZone.tenant_id == tid
            )
        )
        if zone is None:
            raise HTTPException(status_code=404, detail="库区不存在")
        if zone.warehouse_id != loc.warehouse_id:
            raise HTTPException(status_code=400, detail="库区不属于该仓库")
        loc.zone_id = payload.zone_id
    if payload.name is not None:
        loc.name = payload.name
    if payload.location_type is not None:
        loc.location_type = payload.location_type
    if payload.parent_id is not None:
        if payload.parent_id == loc.id:
            raise HTTPException(status_code=400, detail="上级库位不能是自己")
        loc.parent_id = payload.parent_id
    if payload.capacity is not None:
        loc.capacity = payload.capacity
    if payload.is_active is not None:
        loc.is_active = payload.is_active
    if payload.remark is not None:
        loc.remark = payload.remark
    db.commit()
    db.refresh(loc)
    zone_code = db.scalar(select(WarehouseZone.code).where(WarehouseZone.id == loc.zone_id)) if loc.zone_id else None
    return ok(_location_out(loc, zone_code))


@router.delete("/locations/{location_id}", dependencies=[Depends(require_permissions(["warehouse.manage"]))])
def delete_location_api(
    location_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    loc = db.scalar(
        select(WarehouseLocation).where(
            WarehouseLocation.id == location_id, WarehouseLocation.tenant_id == tid
        )
    )
    if loc is None:
        raise HTTPException(status_code=404, detail="库位不存在")

    batch_cnt = db.scalar(
        select(func.count(StockBatch.id)).where(
            StockBatch.tenant_id == tid, StockBatch.location_id == location_id
        )
    )
    if int(batch_cnt or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"该库位下还有 {batch_cnt} 条批次记录，删掉会让批次失去库位归属。"
                "请先把库存移库到别的库位，或直接停用该库位"
            ),
        )
    child_cnt = db.scalar(
        select(func.count(WarehouseLocation.id)).where(
            WarehouseLocation.tenant_id == tid, WarehouseLocation.parent_id == location_id
        )
    )
    if int(child_cnt or 0) > 0:
        raise HTTPException(status_code=409, detail=f"该库位下还有 {child_cnt} 个子库位，请先处理")

    db.delete(loc)
    db.commit()
    return ok({"id": location_id})
