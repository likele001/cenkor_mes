"""发货管理 API"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.notification import create_notification
from app.crud.order import get_order_by_id
from app.crud.shipment import create_shipment, get_shipment, list_shipments
from app.crud.warehouse import adjust_stock
from app.models.shipment import Shipment
from app.models.warehouse import Warehouse
from app.models.user import User

router = APIRouter(prefix="/shipments", dependencies=[Depends(require_permissions(["order.manage"]))])


class ShipmentItemIn(BaseModel):
    sku_id: int
    qty: int = Field(ge=1)


class ShipmentIn(BaseModel):
    order_id: int
    code: str = Field(min_length=1, max_length=64)
    logistics_company: str | None = Field(default=None, max_length=128)
    logistics_no: str | None = Field(default=None, max_length=64)
    remark: str | None = Field(default=None, max_length=500)
    items: list[ShipmentItemIn] = Field(min_length=1)


def _out(s: Shipment) -> dict:
    return {
        "id": s.id,
        "order_id": s.order_id,
        "order_code": s.order.code if s.order else None,
        "code": s.code,
        "logistics_company": s.logistics_company,
        "logistics_no": s.logistics_no,
        "status": s.status,
        "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
        "signed_at": s.signed_at.isoformat() if s.signed_at else None,
        "remark": s.remark,
        "items": [
            {
                "sku_id": it.sku_id,
                "sku_code": it.sku.code if it.sku else None,
                "sku_name": it.sku.name if it.sku else None,
                "qty": it.qty,
            }
            for it in (s.items or [])
        ],
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
def list_api(
    order_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_shipments(db, order_id=order_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_out(s) for s in items]})


@router.get("/{shipment_id}")
def get_api(shipment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = get_shipment(db, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="发货单不存在")
    return ok(_out(s))


@router.post("")
def create_api(payload: ShipmentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = create_shipment(db, payload.model_dump())
    db.commit()
    return ok(_out(s))


@router.post("/{shipment_id}/ship")
def ship_api(shipment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = get_shipment(db, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="发货单不存在")
    if s.status != "pending":
        raise HTTPException(status_code=400, detail="仅待发货状态可确认发货")

    warehouse = db.scalar(
        select(Warehouse).where(
            Warehouse.is_active.is_(True)
        ).order_by(Warehouse.id.asc()).limit(1)
    )
    if not warehouse:
        raise HTTPException(status_code=400, detail="请先创建仓库")

    for item in (s.items or []):
        adjust_stock(
            db,
            warehouse_id=warehouse.id,
            sku_id=item.sku_id,
            change_qty=-item.qty,
            biz_type="ship_out",
            biz_id=s.id,
            remark=f"发货#{s.code} {item.sku.code if item.sku else ''} x{item.qty}",
        )

    s.status = "shipped"
    s.shipped_at = datetime.now(timezone.utc)

    order = get_order_by_id(db, s.order_id, with_items=False)
    if order and order.status in ("confirmed", "producing"):
        order.status = "shipped"
        cust = order.customer
        if cust and cust.user_id:
            create_notification(
                db,
                user_id=cust.user_id,
                title="订单已发货",
                content=f"您的订单 {order.code} 已发货，物流单号：{s.logistics_no or '待补充'}",
                level="info",
                biz_type="order",
                biz_id=order.id,
                feishu_event="order.shipped",
            )

    db.commit()
    return ok(_out(s))


@router.post("/{shipment_id}/sign")
def sign_api(shipment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = get_shipment(db, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="发货单不存在")
    if s.status != "shipped":
        raise HTTPException(status_code=400, detail="仅已发货状态可签收")
    s.status = "signed"
    s.signed_at = datetime.now(timezone.utc)
    s.signed_by = user.id
    db.commit()
    return ok(_out(s))
