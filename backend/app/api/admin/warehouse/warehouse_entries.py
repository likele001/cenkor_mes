from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.warehouse_entry import (
    cancel_entry,
    confirm_entry,
    create_entry,
    get_entry_by_id,
    list_entries,
)
from app.models.warehouse_entry import WarehouseEntry
from app.models.warehouse import Warehouse
from app.models.material import Material
from app.models.purchase import PurchaseOrder
from app.models.material_issue import MaterialReturn
from app.models.user import User
from app.services.code_generator import BizType, resolve_code

router = APIRouter(dependencies=[Depends(require_permissions(["warehouse.manage"]))])


class EntryItemIn(BaseModel):
    material_id: int = Field(ge=1)
    sku_id: int = Field(ge=1)
    qty: int = Field(ge=1)


class EntryCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    source_type: str = Field(default="other")  # purchase/material_return/other
    warehouse_id: int = Field(ge=1)
    purchase_order_id: int | None = Field(default=None, ge=1)
    material_return_id: int | None = Field(default=None, ge=1)
    remark: str | None = Field(default=None, max_length=255)
    items: list[EntryItemIn] = Field(min_length=1)


def _entry_out(x: WarehouseEntry) -> dict:
    items = []
    for it in x.items:
        items.append({
            "id": it.id,
            "material_id": it.material_id,
            "material_code": it.material.code if it.material else None,
            "material_name": it.material.name if it.material else None,
            "sku_id": it.sku_id,
            "sku_code": it.sku.code if it.sku else None,
            "sku_name": it.sku.name if it.sku else None,
            "qty": it.qty,
            "unit_cost": str(it.unit_cost),
            "cost_amount": str(it.cost_amount),
        })
    return {
        "id": x.id,
        "code": x.code,
        "status": x.status,
        "source_type": x.source_type,
        "warehouse_id": x.warehouse_id,
        "warehouse_code": x.warehouse.code if x.warehouse else None,
        "warehouse_name": x.warehouse.name if x.warehouse else None,
        "purchase_order_id": x.purchase_order_id,
        "purchase_order_code": x.purchase_order.code if x.purchase_order else None,
        "material_return_id": x.material_return_id,
        "material_return_code": x.material_return.code if x.material_return else None,
        "total_qty": x.total_qty,
        "total_cost": str(x.total_cost),
        "confirmed_at": x.confirmed_at.isoformat() if x.confirmed_at else None,
        "confirmed_by": x.confirmed_by,
        "remark": x.remark,
        "created_by": x.created_by,
        "created_at": x.created_at.isoformat() if x.created_at else None,
        "items": items,
    }


@router.get("/entries")
def list_api(
    warehouse_id: int | None = Query(default=None),
    source_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = list_entries(db, warehouse_id=warehouse_id, source_type=source_type, status=status, offset=offset, limit=limit)
    return ok([_entry_out(x) for x in rows])


@router.get("/entries/{entry_id}")
def get_api(entry_id: int, db: Session = Depends(get_db)):
    x = get_entry_by_id(db, entry_id)
    if not x:
        raise HTTPException(status_code=404, detail="入库单不存在")
    return ok(_entry_out(x))


@router.post("/entries")
def create_api(
    payload: EntryCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wh = db.get(Warehouse, payload.warehouse_id)
    if not wh or not wh.is_active:
        raise HTTPException(status_code=400, detail="仓库不存在或已停用")
    if payload.source_type not in {"purchase", "material_return", "other"}:
        raise HTTPException(status_code=400, detail="入库类型无效")
    if payload.source_type == "purchase":
        if not payload.purchase_order_id:
            raise HTTPException(status_code=400, detail="采购入库必须关联采购单")
        po = db.get(PurchaseOrder, payload.purchase_order_id)
        if not po:
            raise HTTPException(status_code=400, detail="采购单不存在")
    if payload.source_type == "material_return":
        if not payload.material_return_id:
            raise HTTPException(status_code=400, detail="退料入库必须关联退料单")
        mr = db.get(MaterialReturn, payload.material_return_id)
        if not mr:
            raise HTTPException(status_code=400, detail="退料单不存在")
    for it in payload.items:
        m = db.get(Material, it.material_id)
        if not m or not m.is_active:
            raise HTTPException(status_code=400, detail=f"物料 {it.material_id} 不存在")
        if m.sku_id != it.sku_id:
            raise HTTPException(status_code=400, detail=f"物料 {m.name} 与 SKU 不匹配")
    code = resolve_code(
        db,
        biz_type=BizType.WAREHOUSE_ENTRY,
        code=payload.code,
        exists=lambda c: db.scalar(select(WarehouseEntry.id).where(WarehouseEntry.code == c)) is not None,
        duplicate_msg="入库单号已存在",
    )
    entry = create_entry(
        db,
        code=code,
        source_type=payload.source_type,
        warehouse_id=payload.warehouse_id,
        items=[{"material_id": it.material_id, "sku_id": it.sku_id, "qty": it.qty} for it in payload.items],
        purchase_order_id=payload.purchase_order_id,
        material_return_id=payload.material_return_id,
        remark=payload.remark,
        created_by=user.id,
    )
    db.commit()
    return ok(_entry_out(get_entry_by_id(db, entry.id)))


@router.post("/entries/{entry_id}/confirm")
def confirm_api(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = get_entry_by_id(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="入库单不存在")
    try:
        confirm_entry(db, entry, confirmed_by=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok(_entry_out(get_entry_by_id(db, entry.id)))


@router.post("/entries/{entry_id}/cancel")
def cancel_api(entry_id: int, db: Session = Depends(get_db)):
    entry = get_entry_by_id(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="入库单不存在")
    try:
        cancel_entry(db, entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok(_entry_out(get_entry_by_id(db, entry.id)))
