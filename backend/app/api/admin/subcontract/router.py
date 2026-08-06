from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.subcontract import (
    add_receive_log,
    add_send_log,
    create_order,
    get_order_by_id,
    list_orders,
    update_order_status,
)
from app.models.user import User
from app.schemas.subcontract import (
    ReceiveLogIn,
    SendLogIn,
    SubcontractOrderCreate,
)

router = APIRouter()


def _item_out(item) -> dict:
    return {
        "id": item.id,
        "order_id": item.order_id,
        "sku_id": item.sku_id,
        "process_id": item.process_id,
        "qty": item.qty,
        "unit_price": float(item.unit_price) if item.unit_price else None,
        "sent_qty": item.sent_qty,
        "received_qty": item.received_qty,
        "remark": item.remark,
        "sku_code": item.sku.code if item.sku else None,
        "sku_name": item.sku.name if item.sku else None,
        "process_name": item.process.name if item.process else None,
    }


def _order_brief(o) -> dict:
    return {
        "id": o.id,
        "code": o.code,
        "status": o.status,
        "supplier_id": o.supplier_id,
        "supplier_name": o.supplier.name if o.supplier else None,
        "created_at": o.created_at,
    }


@router.get("")
def list_api(
    status: str | None = Query(default=None),
    supplier_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    orders = list_orders(db, status=status, supplier_id=supplier_id, keyword=keyword, offset=offset, limit=limit)
    return ok({"items": [_order_brief(o) for o in orders]})


@router.post("")
def create_api(
    body: SubcontractOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        order = create_order(
            db,
            supplier_id=body.supplier_id,
            code=body.code,
            remark=body.remark,
            items=[i.model_dump() for i in body.items],
            created_by=user.id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok({"id": order.id, "code": order.code})


@router.get("/{order_id}")
def detail_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="委外单不存在")
    return ok({
        "id": order.id,
        "supplier_id": order.supplier_id,
        "code": order.code,
        "status": order.status,
        "remark": order.remark,
        "created_by": order.created_by,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "supplier_name": order.supplier.name if order.supplier else None,
        "items": [_item_out(i) for i in order.items],
        "send_logs": [
            {
                "id": l.id, "order_id": l.order_id, "item_id": l.item_id,
                "qty": l.qty, "remark": l.remark,
                "sent_by": l.sent_by, "sent_at": l.sent_at,
            }
            for l in (order.send_logs or [])
        ],
        "receive_logs": [
            {
                "id": l.id, "order_id": l.order_id, "item_id": l.item_id,
                "qty": l.qty, "remark": l.remark,
                "received_by": l.received_by, "received_at": l.received_at,
            }
            for l in (order.receive_logs or [])
        ],
    })


@router.patch("/{order_id}/status")
def status_api(
    order_id: int,
    status: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="委外单不存在")
    try:
        update_order_status(db, order, status)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok({"id": order.id, "status": order.status})


@router.post("/{order_id}/send")
def send_api(
    order_id: int,
    body: SendLogIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="委外单不存在")
    try:
        add_send_log(db, order, body.item_id, body.qty, body.remark, user.id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok({"order_id": order.id, "status": order.status})


@router.post("/{order_id}/receive")
def receive_api(
    order_id: int,
    body: ReceiveLogIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="委外单不存在")
    try:
        add_receive_log(db, order, body.item_id, body.qty, body.remark, user.id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok({"order_id": order.id, "status": order.status})
