from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.warehouse import create_warehouse, list_warehouses, list_stocks, adjust_stock, list_stock_logs
from app.models.user import User
from app.models.warehouse import Warehouse
from app.services.code_generator import BizType, resolve_code
from app.api.admin.warehouse.shipments import router as shipments_router
from app.tasks._sync_excel import make_excel_response


class WarehouseCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    address: str | None = Field(default=None, max_length=255)


def _warehouse_code_exists(db: Session, code: str) -> bool:
    return db.scalar(select(Warehouse.id).where(Warehouse.code == code)) is not None


router = APIRouter(dependencies=[Depends(require_permissions(["warehouse.manage"]))])
router.include_router(shipments_router)


@router.get("/warehouses")
def list_warehouses_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_warehouses(db)
    return ok({
        "items": [
            {"id": w.id, "code": w.code, "name": w.name, "address": w.address}
            for w in items
        ]
    })


@router.get("/warehouses/export")
def export_warehouses_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_warehouses(db)
    rows = []
    for w in items:
        rows.append([w.code, w.name, w.address or ""])
    return make_excel_response(
        headers=["仓库编码", "仓库名称", "地址"],
        rows=rows,
        filename="warehouses.xlsx",
        sheet_name="仓库",
    )


@router.post("/warehouses")
def create_warehouse_api(
    payload: WarehouseCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wh_code = resolve_code(
        db,
        biz_type=BizType.WAREHOUSE,
        code=payload.code,
        exists=lambda c: _warehouse_code_exists(db, c),
        duplicate_msg="仓库编码已存在",
    )
    wh = create_warehouse(db, code=wh_code, name=payload.name, address=payload.address)
    db.commit()
    return ok({"id": wh.id, "code": wh.code, "name": wh.name})


@router.put("/warehouses/{warehouse_id}")
def update_warehouse_api(
    warehouse_id: int,
    code: str = Query(min_length=1),
    name: str = Query(min_length=1),
    address: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wh = db.scalars(select(Warehouse).where(Warehouse.id == warehouse_id)).first()
    if not wh:
        raise HTTPException(status_code=404, detail="仓库不存在")
    wh.code = code
    wh.name = name
    if address is not None:
        wh.address = address
    db.commit()
    return ok({"id": wh.id, "code": wh.code, "name": wh.name, "address": wh.address})


@router.get("/stocks")
def list_stocks_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    item_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_stocks(db, warehouse_id=warehouse_id, item_type=item_type)
    return ok({
        "items": [
            {
                "id": s.id,
                "warehouse_id": s.warehouse_id,
                "warehouse_name": s.warehouse.name if s.warehouse else None,
                "sku_id": s.sku_id,
                "sku_code": s.sku.code if s.sku else None,
                "sku_name": s.sku.name if s.sku else None,
                "qty": s.qty,
                "updated_at": s.updated_at,
            }
            for s in items
        ]
    })


@router.post("/stocks/adjust")
def adjust_stock_api(
    warehouse_id: int = Query(ge=1),
    sku_id: int = Query(ge=1),
    change_qty: int = Query(description="正=入库 负=出库"),
    biz_type: str = Query(default="manual"),
    remark: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = adjust_stock(db, warehouse_id=warehouse_id,
                     sku_id=sku_id, change_qty=change_qty, biz_type=biz_type, remark=remark)
    db.commit()
    return ok({"qty": s.qty})


@router.get("/logs")
def list_logs_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    sku_id: int | None = Query(default=None, ge=1),
    item_type: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_stock_logs(db, warehouse_id=warehouse_id,
                            sku_id=sku_id, item_type=item_type, offset=offset, limit=limit)
    return ok({
        "items": [
            {
                "id": l.id,
                "warehouse_id": l.warehouse_id,
                "warehouse_name": l.warehouse.name if l.warehouse else None,
                "sku_id": l.sku_id,
                "sku_code": l.sku.code if l.sku else None,
                "sku_name": l.sku.name if l.sku else None,
                "change_qty": l.change_qty,
                "balance_qty": l.balance_qty,
                "biz_type": l.biz_type,
                "remark": l.remark,
                "created_at": l.created_at,
            }
            for l in items
        ]
    })
