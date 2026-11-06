# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""库存盘点 API

权限沿用仓储模块已有的两个点，不新增权限码：
读用 `warehouse.view`（与库存页同一拨人看），
写（制单/录实盘/确认/作废）用 `warehouse.manage`。
盘点确认会真实改库存，所以确认端点单独再挂一道 `warehouse.manage`。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_any_permissions, require_permissions
from app.core.response import ok
from app.crud.warehouse import resolve_warehouse_id
from app.crud.stocktake import (
    StocktakeStateError,
    add_item,
    cancel_stocktake,
    confirm_stocktake,
    count_stocktakes,
    create_stocktake,
    get_stocktake,
    list_stocktakes,
    record_counts,
    remove_item,
    stocktake_out,
)
from app.models.stocktake import Stocktake
from app.models.user import User
from app.services.code_generator import BizType, resolve_code
from app.tasks._sync_excel import make_excel_response

router = APIRouter(
    prefix="/stocktakes",
    dependencies=[Depends(require_any_permissions(["warehouse.manage", "warehouse.view"]))],
)

_WRITE = [Depends(require_permissions(["warehouse.manage"]))]


class StocktakeCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    warehouse_id: int | None = Field(default=None, ge=1, description="盘点仓库；多仓必填")
    item_type: str | None = Field(default=None, description="all/product/material，不传=全部")
    sku_ids: list[int] | None = Field(default=None, description="只盘这些型号；不传=按范围全盘")
    remark: str | None = Field(default=None, max_length=500)


class CountIn(BaseModel):
    item_id: int = Field(ge=1)
    counted_qty: int = Field(ge=0)
    remark: str | None = Field(default=None, max_length=255)


class RecordCountsIn(BaseModel):
    items: list[CountIn] = Field(min_length=1)


class ItemAddIn(BaseModel):
    sku_id: int = Field(ge=1)
    remark: str | None = Field(default=None, max_length=255)


def _load(db: Session, stocktake_id: int):
    st = get_stocktake(db, stocktake_id)
    if not st:
        raise HTTPException(status_code=404, detail="盘点单不存在")
    return st


def _bad(e: Exception) -> HTTPException:
    """状态不对按 409 回，参数/数据不对按 400 回——前端据此决定是提示还是刷新。"""
    if isinstance(e, StocktakeStateError):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


@router.get("")
def list_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_stocktakes(db, warehouse_id=warehouse_id, status=status, offset=offset, limit=limit)
    return ok({
        "items": [stocktake_out(s, with_items=False) for s in items],
        "total": count_stocktakes(db, warehouse_id=warehouse_id, status=status),
    })


@router.get("/{stocktake_id}")
def get_api(stocktake_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(stocktake_out(_load(db, stocktake_id)))


@router.post("", dependencies=_WRITE)
def create_api(
    payload: StocktakeCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        warehouse_id = resolve_warehouse_id(db, payload.warehouse_id, action="盘点")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    code = resolve_code(
        db,
        biz_type=BizType.STOCKTAKE,
        code=payload.code,
        exists=lambda c: db.scalar(select(Stocktake.id).where(Stocktake.code == c)) is not None,
        duplicate_msg="盘点单号已存在",
    )
    try:
        st = create_stocktake(
            db,
            code=code,
            warehouse_id=warehouse_id,
            item_type=payload.item_type,
            sku_ids=payload.sku_ids,
            remark=payload.remark,
            created_by=user.id,
        )
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(stocktake_out(get_stocktake(db, st.id)))


@router.put("/{stocktake_id}/items", dependencies=_WRITE)
def record_counts_api(
    stocktake_id: int,
    payload: RecordCountsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    st = _load(db, stocktake_id)
    try:
        record_counts(db, st, [r.model_dump() for r in payload.items])
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(stocktake_out(get_stocktake(db, st.id)))


@router.post("/{stocktake_id}/items", dependencies=_WRITE)
def add_item_api(
    stocktake_id: int,
    payload: ItemAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    st = _load(db, stocktake_id)
    try:
        add_item(db, st, payload.sku_id, payload.remark)
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(stocktake_out(get_stocktake(db, st.id)))


@router.delete("/{stocktake_id}/items/{item_id}", dependencies=_WRITE)
def remove_item_api(
    stocktake_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    st = _load(db, stocktake_id)
    try:
        remove_item(db, st, item_id)
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(stocktake_out(get_stocktake(db, st.id)))


@router.post("/{stocktake_id}/confirm", dependencies=_WRITE)
def confirm_api(
    stocktake_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    st = _load(db, stocktake_id)
    try:
        result = confirm_stocktake(db, st, confirmed_by=user.id)
    except ValueError as e:
        raise _bad(e)
    db.commit()
    result["stocktake"] = stocktake_out(get_stocktake(db, st.id))
    return ok(result)


@router.post("/{stocktake_id}/cancel", dependencies=_WRITE)
def cancel_api(
    stocktake_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    st = _load(db, stocktake_id)
    try:
        cancel_stocktake(db, st)
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(stocktake_out(get_stocktake(db, st.id)))


@router.get("/{stocktake_id}/export")
def export_api(
    stocktake_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """导出盘点表：可直接打印给仓管带去现场逐行点。"""
    st = _load(db, stocktake_id)
    headers = ["单号", "仓库", "编码", "名称", "规格", "账面数", "实盘数", "差异", "已入账变动", "备注"]
    rows = []
    for it in (st.items or []):
        rows.append([
            st.code,
            st.warehouse.name if st.warehouse else "",
            it.sku.code if it.sku else "",
            it.sku.name if it.sku else "",
            (it.sku.spec or "") if it.sku else "",
            it.book_qty,
            "" if it.counted_qty is None else it.counted_qty,
            "" if it.diff_qty is None else it.diff_qty,
            "" if it.adjusted_qty is None else it.adjusted_qty,
            it.remark or "",
        ])
    return make_excel_response(headers, rows, f"stocktake_{st.code}.xlsx", "盘点表")
