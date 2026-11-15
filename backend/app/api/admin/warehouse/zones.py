# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""库区：仓库内的功能分区（存储 / 收货 / 拣货 / 待检 / 不良 / 发货）。

库区本身不挂库存 —— 库存落在库位上。所以删库区只校验「下面还有没有库位」，
不涉及库存搬运；要删有库位的库区，先把库位挪走或停用。
"""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.user import User
from app.models.warehouse import Warehouse, WarehouseLocation, WarehouseZone

ZoneType = Literal["storage", "receiving", "picking", "inspection", "defect", "shipping"]

ZONE_TYPE_LABELS = {
    "storage": "存储区",
    "receiving": "收货区",
    "picking": "拣货区",
    "inspection": "待检区",
    "defect": "不良品区",
    "shipping": "发货区",
}


class ZoneCreateIn(BaseModel):
    warehouse_id: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    zone_type: ZoneType = "storage"
    capacity: Decimal | None = Field(default=None, ge=0)
    sort_order: int = 0
    enabled: bool = True


class ZoneUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    zone_type: ZoneType | None = None
    capacity: Decimal | None = Field(default=None, ge=0)
    sort_order: int | None = None
    enabled: bool | None = None


router = APIRouter()


def _tenant_id(user: User) -> int:
    """单用户版固定单租户。用 property 而不是写死 1，多租户版接进来时不用改这里。"""
    return int(getattr(user, "tenant_id", 1) or 1)


def _zone_out(zone: WarehouseZone, location_count: int = 0) -> dict:
    return {
        "id": zone.id,
        "warehouse_id": zone.warehouse_id,
        "code": zone.code,
        "name": zone.name,
        "zone_type": zone.zone_type,
        "zone_type_label": ZONE_TYPE_LABELS.get(zone.zone_type, zone.zone_type),
        "capacity": float(zone.capacity) if zone.capacity is not None else None,
        "sort_order": zone.sort_order,
        "enabled": bool(zone.enabled),
        "location_count": location_count,
    }


@router.get("/zones")
def list_zones_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    stmt = select(WarehouseZone).where(WarehouseZone.tenant_id == tid)
    if warehouse_id is not None:
        stmt = stmt.where(WarehouseZone.warehouse_id == warehouse_id)
    if enabled is not None:
        stmt = stmt.where(WarehouseZone.enabled.is_(enabled))
    zones = db.scalars(stmt.order_by(WarehouseZone.warehouse_id, WarehouseZone.sort_order, WarehouseZone.id)).all()

    # 库位数一次查出来，避免每个库区一条 count（列表页通常只有几十个库区，但库位上千）
    counts = dict(
        db.execute(
            select(WarehouseLocation.zone_id, func.count(WarehouseLocation.id))
            .where(WarehouseLocation.tenant_id == tid, WarehouseLocation.zone_id.is_not(None))
            .group_by(WarehouseLocation.zone_id)
        ).all()
    )
    return ok({"items": [_zone_out(z, int(counts.get(z.id, 0))) for z in zones]})


@router.post("/zones", dependencies=[Depends(require_permissions(["warehouse.manage"]))])
def create_zone_api(
    payload: ZoneCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    wh = db.scalar(
        select(Warehouse).where(Warehouse.id == payload.warehouse_id)
    )
    if wh is None:
        raise HTTPException(status_code=404, detail="仓库不存在")

    exists = db.scalar(
        select(WarehouseZone.id).where(
            WarehouseZone.tenant_id == tid,
            WarehouseZone.warehouse_id == payload.warehouse_id,
            WarehouseZone.code == payload.code,
        )
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail=f"该仓库下库区编码 {payload.code} 已存在")

    zone = WarehouseZone(
        tenant_id=tid,
        warehouse_id=payload.warehouse_id,
        code=payload.code,
        name=payload.name,
        zone_type=payload.zone_type,
        capacity=payload.capacity,
        sort_order=payload.sort_order,
        enabled=payload.enabled,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return ok(_zone_out(zone))


@router.put("/zones/{zone_id}", dependencies=[Depends(require_permissions(["warehouse.manage"]))])
def update_zone_api(
    zone_id: int,
    payload: ZoneUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    zone = db.scalar(
        select(WarehouseZone).where(WarehouseZone.id == zone_id, WarehouseZone.tenant_id == tid)
    )
    if zone is None:
        raise HTTPException(status_code=404, detail="库区不存在")

    if payload.name is not None:
        zone.name = payload.name
    if payload.zone_type is not None:
        zone.zone_type = payload.zone_type
    if payload.capacity is not None:
        zone.capacity = payload.capacity
    if payload.sort_order is not None:
        zone.sort_order = payload.sort_order
    if payload.enabled is not None:
        zone.enabled = payload.enabled
    db.commit()
    db.refresh(zone)
    return ok(_zone_out(zone))


@router.delete("/zones/{zone_id}", dependencies=[Depends(require_permissions(["warehouse.manage"]))])
def delete_zone_api(
    zone_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    zone = db.scalar(
        select(WarehouseZone).where(WarehouseZone.id == zone_id, WarehouseZone.tenant_id == tid)
    )
    if zone is None:
        raise HTTPException(status_code=404, detail="库区不存在")

    used = db.scalar(
        select(func.count(WarehouseLocation.id)).where(
            WarehouseLocation.tenant_id == tid, WarehouseLocation.zone_id == zone_id
        )
    )
    if int(used or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"该库区下还有 {used} 个库位，请先挪走或停用库位再删",
        )

    db.delete(zone)
    db.commit()
    return ok({"id": zone_id})
