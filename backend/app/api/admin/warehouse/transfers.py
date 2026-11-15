# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""库间 / 库位间调拨单：建单 → 审核 → 执行 →（可取消）。

业务规则全部在 app.services.warehouse.transfer 里，这里只做参数校验与权限。
执行时整单预检：任何一行库存不足就整单拒绝，不会出现「扣了一半」的半成品单据。
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.sku import Sku
from app.models.user import User
from app.models.warehouse import (
    StockTransfer,
    StockTransferItem,
    Warehouse,
    WarehouseLocation,
)
from app.services.warehouse import transfer as transfer_svc

STATUS_LABELS = {
    "draft": "草稿",
    "pending": "待审核",
    "approved": "已审核",
    "done": "已完成",
    "cancelled": "已取消",
}


class TransferItemIn(BaseModel):
    sku_id: int = Field(ge=1)
    qty: Decimal = Field(gt=0)
    batch_no: str | None = Field(default=None, max_length=64)
    material_id: int | None = None
    remark: str | None = Field(default=None, max_length=255)


class TransferCreateIn(BaseModel):
    from_warehouse_id: int = Field(ge=1)
    to_warehouse_id: int = Field(ge=1)
    from_location_id: int | None = Field(default=None, ge=1)
    to_location_id: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=255)
    remark: str | None = Field(default=None, max_length=255)
    transfer_no: str | None = Field(default=None, max_length=32)
    items: list[TransferItemIn] = Field(min_length=1)


router = APIRouter()


def _tenant_id(user: User) -> int:
    return int(getattr(user, "tenant_id", 1) or 1)


def _transfer_out(t: StockTransfer, from_wh: str | None = None, to_wh: str | None = None, item_count: int = 0) -> dict:
    return {
        "id": t.id,
        "transfer_no": t.transfer_no,
        "from_warehouse_id": t.from_warehouse_id,
        "from_warehouse_name": from_wh,
        "from_location_id": t.from_location_id,
        "to_warehouse_id": t.to_warehouse_id,
        "to_warehouse_name": to_wh,
        "to_location_id": t.to_location_id,
        "status": t.status,
        "status_label": STATUS_LABELS.get(t.status, t.status),
        "reason": t.reason,
        "remark": t.remark,
        "item_count": item_count,
        "created_by": t.created_by,
        "approved_by": t.approved_by,
        "approved_at": t.approved_at,
        "done_at": t.done_at,
        "created_at": t.created_at,
    }


@router.get("/transfers")
def list_transfers_api(
    status: str | None = Query(default=None, max_length=16),
    warehouse_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    stmt = select(StockTransfer).where(StockTransfer.tenant_id == tid)
    if status:
        stmt = stmt.where(StockTransfer.status == status)
    if warehouse_id is not None:
        stmt = stmt.where(
            (StockTransfer.from_warehouse_id == warehouse_id)
            | (StockTransfer.to_warehouse_id == warehouse_id)
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(StockTransfer.id.desc()).offset(offset).limit(limit)
    ).all()

    wh_names = dict(db.execute(select(Warehouse.id, Warehouse.name)).all())
    counts = dict(
        db.execute(
            select(StockTransferItem.transfer_id, func.count(StockTransferItem.id))
            .where(StockTransferItem.tenant_id == tid)
            .group_by(StockTransferItem.transfer_id)
        ).all()
    )
    items = [
        _transfer_out(
            t,
            wh_names.get(t.from_warehouse_id),
            wh_names.get(t.to_warehouse_id),
            int(counts.get(t.id, 0)),
        )
        for t in rows
    ]
    return ok({"total": int(total), "items": items, "offset": offset, "limit": limit})


@router.get("/transfers/{transfer_id}")
def get_transfer_api(
    transfer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = _tenant_id(user)
    t = db.scalar(
        select(StockTransfer).where(StockTransfer.id == transfer_id, StockTransfer.tenant_id == tid)
    )
    if t is None:
        raise HTTPException(status_code=404, detail="调拨单不存在")

    wh_names = dict(db.execute(select(Warehouse.id, Warehouse.name)).all())
    loc_codes = dict(
        db.execute(
            select(WarehouseLocation.id, WarehouseLocation.code).where(
                WarehouseLocation.tenant_id == tid
            )
        ).all()
    )
    rows = db.execute(
        select(StockTransferItem, Sku)
        .join(Sku, Sku.id == StockTransferItem.sku_id)
        .where(StockTransferItem.transfer_id == transfer_id)
        .order_by(StockTransferItem.id)
    ).all()
    data = _transfer_out(
        t, wh_names.get(t.from_warehouse_id), wh_names.get(t.to_warehouse_id), len(rows)
    )
    data["from_location_code"] = loc_codes.get(t.from_location_id)
    data["to_location_code"] = loc_codes.get(t.to_location_id)
    data["items"] = [
        {
            "id": it.id,
            "sku_id": it.sku_id,
            "sku_code": s.code,
            "sku_name": s.name,
            "qty": float(it.qty),
            "batch_no": it.batch_no,
            "from_batch_id": it.from_batch_id,
            "to_batch_id": it.to_batch_id,
            "remark": it.remark,
        }
        for it, s in rows
    ]
    return ok(data)


@router.post("/transfers", dependencies=[Depends(require_permissions(["warehouse.manage"]))])
def create_transfer_api(
    payload: TransferCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        t = transfer_svc.create_transfer(db, _tenant_id(user), payload, operator_id=user.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(t)
    return ok(_transfer_out(t))


@router.post(
    "/transfers/{transfer_id}/approve",
    dependencies=[Depends(require_permissions(["warehouse.manage"]))],
)
def approve_transfer_api(
    transfer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        t = transfer_svc.approve_transfer(db, _tenant_id(user), transfer_id, operator_id=user.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(t)
    return ok(_transfer_out(t))


@router.post(
    "/transfers/{transfer_id}/execute",
    dependencies=[Depends(require_permissions(["warehouse.manage"]))],
)
def execute_transfer_api(
    transfer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        t = transfer_svc.execute_transfer(db, _tenant_id(user), transfer_id, operator_id=user.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(t)
    return ok(_transfer_out(t))


@router.post(
    "/transfers/{transfer_id}/cancel",
    dependencies=[Depends(require_permissions(["warehouse.manage"]))],
)
def cancel_transfer_api(
    transfer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        t = transfer_svc.cancel_transfer(db, _tenant_id(user), transfer_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(t)
    return ok(_transfer_out(t))
