from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.material import get_material_by_id
from app.crud.purchase_order import confirm_purchase_order, create_purchase_order, get_purchase_order_by_id, list_purchase_orders
from app.crud.supplier import get_supplier_by_id
from app.crud.warehouse import adjust_stock
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.purchase_order import PurchaseOrderCreateIn, PurchaseOrderReceiveIn, PurchaseOrderReturnIn
from app.tasks._sync_excel import make_excel_response


router = APIRouter(dependencies=[Depends(require_permissions(["purchase.manage"]))])


def _out(po) -> dict:
    sup = getattr(po, "supplier", None)
    return {
        "id": po.id,
        "supplier_id": po.supplier_id,
        "supplier_code": sup.code if sup else None,
        "supplier_name": sup.name if sup else None,
        "code": po.code,
        "status": po.status,
        "remark": po.remark,
        "confirmed_at": po.confirmed_at,
        "confirmed_by": po.confirmed_by,
        "created_by": po.created_by,
        "created_at": po.created_at,
        "updated_at": po.updated_at,
        "items": [
            {
                "id": it.id,
                "material_id": it.material_id,
                "material_code": it.material.code if it.material else None,
                "material_name": it.material.name if it.material else None,
                "qty": it.qty,
                "received_qty": it.received_qty,
                "returned_qty": it.returned_qty,
                "unit_price": it.unit_price,
                "remark": it.remark,
            }
            for it in (po.items or [])
        ],
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    supplier_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_purchase_orders(db, keyword=keyword, supplier_id=supplier_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_out(x) for x in items]})


@router.get("/export")
def export_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_purchase_orders(db, offset=0, limit=999999)
    rows = []
    for po in items:
        sup = getattr(po, "supplier", None)
        total_amount = sum((it.qty * (it.unit_price or 0)) for it in (po.items or []))
        rows.append([po.code, sup.name if sup else "", po.status, float(total_amount), str(po.created_at) if po.created_at else ""])
    return make_excel_response(
        headers=["采购单号", "供应商", "状态", "总金额", "创建时间"],
        rows=rows,
        filename="purchase_orders.xlsx",
        sheet_name="采购单",
    )


@router.post("")
def create_api(payload: PurchaseOrderCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sup = get_supplier_by_id(db, supplier_id=payload.supplier_id)
    if not sup or not sup.is_active:
        raise HTTPException(status_code=400, detail="供应商不存在")
    items_in = []
    for it in payload.items:
        m = get_material_by_id(db, material_id=it.material_id)
        if not m or not m.is_active:
            raise HTTPException(status_code=400, detail="物料不存在")
        items_in.append((it.material_id, it.qty, it.unit_price, it.remark))
    try:
        po = create_purchase_order(
            db,
            supplier_id=payload.supplier_id,
            code=payload.code,
            remark=payload.remark,
            created_by=user.id,
            items=items_in,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    po2 = get_purchase_order_by_id(db, order_id=po.id, with_items=True)
    if not po2:
        raise HTTPException(status_code=500, detail="创建失败")
    return ok(_out(po2))


@router.get("/{order_id}")
def get_api(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_purchase_order_by_id(db, order_id=order_id, with_items=True)
    if not item:
        raise HTTPException(status_code=404, detail="采购单不存在")
    return ok(_out(item))


@router.post("/{order_id}/confirm")
def confirm_api(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    po = get_purchase_order_by_id(db, order_id=order_id, with_items=False)
    if not po:
        raise HTTPException(status_code=404, detail="采购单不存在")
    try:
        confirm_purchase_order(db, po, confirmer_user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    po2 = get_purchase_order_by_id(db, order_id=order_id, with_items=True)
    if not po2:
        raise HTTPException(status_code=500, detail="确认失败")
    return ok(_out(po2))


@router.post("/{order_id}/receive")
def receive_api(
    order_id: int,
    payload: PurchaseOrderReceiveIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    po = get_purchase_order_by_id(db, order_id=order_id, with_items=True)
    if not po:
        raise HTTPException(status_code=404, detail="采购单不存在")
    if po.status not in {"confirmed", "partial_received"}:
        raise HTTPException(status_code=400, detail="采购单状态不允许入库")
    wh = db.get(Warehouse, payload.warehouse_id)
    if not wh or not wh.is_active:
        raise HTTPException(status_code=400, detail="仓库不存在")

    receive_map = None
    if payload.items is not None:
        order_item_map = {it.id: it for it in (po.items or [])}
        receive_map = {}
        for x in payload.items:
            it = order_item_map.get(x.item_id)
            if not it:
                raise HTTPException(status_code=400, detail="采购单明细不存在")
            if x.item_id in receive_map:
                raise HTTPException(status_code=400, detail="采购单明细重复")
            remain = it.qty - it.received_qty
            if x.receive_qty > remain:
                raise HTTPException(status_code=400, detail="入库数量超过未入库数量")
            if remain <= 0 and x.receive_qty > 0:
                raise HTTPException(status_code=400, detail="明细已全部入库")
            receive_map[x.item_id] = x.receive_qty

    any_received = False
    all_received = True
    old_status = po.status
    for it in po.items:
        remain = it.qty - it.received_qty
        if remain <= 0:
            continue
        rq = remain if receive_map is None else int(receive_map.get(it.id, 0))
        if rq == 0:
            all_received = False
            continue
        m = it.material
        if not m or not m.is_active:
            raise HTTPException(status_code=400, detail="物料不存在")
        adjust_stock(
            db,
            warehouse_id=payload.warehouse_id,
            sku_id=m.sku_id,
            change_qty=rq,
            biz_type="purchase_in",
            biz_id=po.id,
            remark=po.code,
        )
        it.received_qty += rq
        any_received = True
        if it.received_qty < it.qty:
            all_received = False

    if not any_received:
        raise HTTPException(status_code=400, detail="无可入库数量")
    po.status = "received" if all_received else "partial_received"
    write_op_log(
        db,
        request,
        user,
        module="purchase",
        action="receive",
        object_type="PurchaseOrder",
        object_id=po.id,
        detail=f"code={po.code},status={old_status}->{po.status},warehouse_id={payload.warehouse_id}",
    )
    db.commit()
    po2 = get_purchase_order_by_id(db, order_id=order_id, with_items=True)
    if not po2:
        raise HTTPException(status_code=500, detail="入库失败")
    return ok(_out(po2))


@router.post("/{order_id}/return")
def return_api(
    order_id: int,
    payload: PurchaseOrderReturnIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    po = get_purchase_order_by_id(db, order_id=order_id, with_items=True)
    if not po:
        raise HTTPException(status_code=404, detail="采购单不存在")
    if po.status not in {"partial_received", "received"}:
        raise HTTPException(status_code=400, detail="采购单状态不允许退货")
    wh = db.get(Warehouse, payload.warehouse_id)
    if not wh or not wh.is_active:
        raise HTTPException(status_code=400, detail="仓库不存在")

    if not payload.items:
        raise HTTPException(status_code=400, detail="退货明细不能为空")

    order_item_map = {it.id: it for it in (po.items or [])}
    return_map = {}
    for x in payload.items:
        it = order_item_map.get(x.item_id)
        if not it:
            raise HTTPException(status_code=400, detail="采购单明细不存在")
        if x.item_id in return_map:
            raise HTTPException(status_code=400, detail="采购单明细重复")
        max_return = it.received_qty - it.returned_qty
        if x.return_qty > max_return:
            raise HTTPException(status_code=400, detail="退货数量超过可退数量")
        return_map[x.item_id] = x.return_qty

    any_returned = False
    old_status = po.status
    for it in po.items:
        rq = return_map.get(it.id, 0)
        if rq <= 0:
            continue
        m = it.material
        if not m or not m.is_active:
            raise HTTPException(status_code=400, detail="物料不存在")
        adjust_stock(
            db,
            warehouse_id=payload.warehouse_id,
            sku_id=m.sku_id,
            change_qty=-rq,
            biz_type="purchase_return",
            biz_id=po.id,
            remark=po.code,
        )
        it.returned_qty += rq
        any_returned = True

    if not any_returned:
        raise HTTPException(status_code=400, detail="无有效退货数量")

    total_received = sum(it.received_qty for it in po.items)
    total_returned = sum(it.returned_qty for it in po.items)
    total_qty = sum(it.qty for it in po.items)
    net_received = total_received - total_returned
    if net_received <= 0:
        po.status = "confirmed"
    elif net_received < total_qty:
        po.status = "partial_received"
    else:
        po.status = "received"

    write_op_log(
        db,
        request,
        user,
        module="purchase",
        action="return",
        object_type="PurchaseOrder",
        object_id=po.id,
        detail=f"code={po.code},status={old_status}->{po.status},warehouse_id={payload.warehouse_id}",
    )
    db.commit()
    po2 = get_purchase_order_by_id(db, order_id=order_id, with_items=True)
    if not po2:
        raise HTTPException(status_code=500, detail="退货失败")
    return ok(_out(po2))


@router.post("/{order_id}/cancel")
def cancel_api(order_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    po = get_purchase_order_by_id(db, order_id=order_id, with_items=False)
    if not po:
        raise HTTPException(status_code=404, detail="采购单不存在")
    if po.status not in {"draft", "confirmed", "partial_received"}:
        raise HTTPException(status_code=400, detail="采购单状态不允许作废")
    old_status = po.status
    po.status = "canceled"
    write_op_log(
        db,
        request,
        user,
        module="purchase",
        action="cancel",
        object_type="PurchaseOrder",
        object_id=po.id,
        detail=f"code={po.code},status={old_status}->canceled",
    )
    db.commit()
    po2 = get_purchase_order_by_id(db, order_id=order_id, with_items=True)
    if not po2:
        raise HTTPException(status_code=500, detail="作废失败")
    return ok(_out(po2))
