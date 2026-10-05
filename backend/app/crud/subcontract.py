# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.crud.warehouse import adjust_stock, resolve_warehouse_id
from app.models.material import Supplier
from app.models.process import Process
from app.models.sku import Sku
from app.models.subcontract import (
    SubcontractOrder,
    SubcontractOrderItem,
    SubcontractReceiveLog,
    SubcontractSendLog,
)

__all__ = [
    "get_order_by_id",
    "list_orders",
    "create_order",
    "update_order_status",
    "add_send_log",
    "add_receive_log",
]


def _order_options():
    return (
        selectinload(SubcontractOrder.supplier),
        selectinload(SubcontractOrder.items).selectinload(SubcontractOrderItem.sku),
        selectinload(SubcontractOrder.items).selectinload(SubcontractOrderItem.process),
        selectinload(SubcontractOrder.send_logs).selectinload(SubcontractSendLog.warehouse),
        selectinload(SubcontractOrder.receive_logs).selectinload(SubcontractReceiveLog.warehouse),
    )


def get_order_by_id(db: Session, order_id: int) -> SubcontractOrder | None:
    return db.scalar(
        select(SubcontractOrder)
        .where(SubcontractOrder.id == order_id)
        .options(*_order_options())
    )


def list_orders(
    db: Session,
    status: str | None = None,
    supplier_id: int | None = None,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[SubcontractOrder]:
    stmt = (
        select(SubcontractOrder)
        .options(selectinload(SubcontractOrder.supplier))
        .order_by(SubcontractOrder.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if status:
        stmt = stmt.where(SubcontractOrder.status == status)
    if supplier_id:
        stmt = stmt.where(SubcontractOrder.supplier_id == supplier_id)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(SubcontractOrder.code.like(kw))
    return db.scalars(stmt).all()


def create_order(
    db: Session,
    supplier_id: int,
    code: str,
    remark: str | None,
    items: list[dict],
    created_by: int | None,
) -> SubcontractOrder:
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise ValueError("供应商不存在")

    if not code:
        from app.services.code_generator import BizType, allocate_code
        code = allocate_code(db, BizType.SUBCONTRACT)

    existing = db.scalar(select(SubcontractOrder).where(SubcontractOrder.code == code))
    if existing:
        raise ValueError("委外单号已存在")

    order = SubcontractOrder(
        supplier_id=supplier_id,
        code=code,
        status="draft",
        remark=remark,
        created_by=created_by,
    )
    order.items = [
        SubcontractOrderItem(
            sku_id=i["sku_id"],
            process_id=i.get("process_id"),
            qty=i["qty"],
            unit_price=i.get("unit_price"),
            remark=i.get("remark"),
        )
        for i in items
    ]
    db.add(order)
    db.flush()
    return order


def update_order_status(db: Session, order: SubcontractOrder, status: str) -> SubcontractOrder:
    valid = {"draft", "sent", "partial_received", "received", "settled"}
    if status not in valid:
        raise ValueError(f"无效状态，可选: {', '.join(valid)}")
    order.status = status
    db.flush()
    return order


def add_send_log(
    db: Session,
    order: SubcontractOrder,
    item_id: int,
    qty: int,
    remark: str | None,
    sent_by: int | None,
    warehouse_id: int | None = None,
) -> SubcontractSendLog:
    item = next((i for i in order.items if i.id == item_id), None)
    if not item:
        raise ValueError("明细不存在")
    if qty <= 0:
        raise ValueError("发料数量必须大于0")
    remaining = item.qty - item.sent_qty
    if qty > remaining:
        raise ValueError(f"发料数量超出委外量：本单 {item.qty}，已发 {item.sent_qty}，最多还能发 {remaining}")

    wh_id = resolve_warehouse_id(db, warehouse_id, action="委外发料")
    sku_code = item.sku.code if item.sku else f"型号#{item.sku_id}"
    # 发料即出库：先扣账，扣不动就不留发料记录
    adjust_stock(
        db,
        warehouse_id=wh_id,
        sku_id=item.sku_id,
        change_qty=-qty,
        biz_type="subcontract_out",
        biz_id=order.id,
        remark=f"委外发料#{order.code} {sku_code} x{qty}",
    )
    log = SubcontractSendLog(
        order_id=order.id,
        item_id=item_id,
        warehouse_id=wh_id,
        qty=qty,
        remark=remark,
        sent_by=sent_by,
    )
    db.add(log)
    item.sent_qty += qty
    db.flush()

    if order.status == "draft":
        order.status = "sent"
    db.flush()
    return log


def add_receive_log(
    db: Session,
    order: SubcontractOrder,
    item_id: int,
    qty: int,
    remark: str | None,
    received_by: int | None,
    warehouse_id: int | None = None,
) -> SubcontractReceiveLog:
    item = next((i for i in order.items if i.id == item_id), None)
    if not item:
        raise ValueError("明细不存在")
    if qty <= 0:
        raise ValueError("收货数量必须大于0")
    outstanding = item.sent_qty - item.received_qty
    if qty > outstanding:
        raise ValueError(f"收货数量超出在制外协量：已发 {item.sent_qty}，已收 {item.received_qty}，最多还能收 {outstanding}")

    wh_id = resolve_warehouse_id(db, warehouse_id, action="委外收货")
    sku_code = item.sku.code if item.sku else f"型号#{item.sku_id}"
    adjust_stock(
        db,
        warehouse_id=wh_id,
        sku_id=item.sku_id,
        change_qty=qty,
        biz_type="subcontract_in",
        biz_id=order.id,
        remark=f"委外收货#{order.code} {sku_code} x{qty}",
    )
    log = SubcontractReceiveLog(
        order_id=order.id,
        item_id=item_id,
        warehouse_id=wh_id,
        qty=qty,
        remark=remark,
        received_by=received_by,
    )
    db.add(log)
    item.received_qty += qty
    db.flush()

    all_received = all(i.received_qty >= i.qty for i in order.items)
    any_received = any(i.received_qty > 0 for i in order.items)
    if all_received:
        order.status = "received"
    elif any_received:
        order.status = "partial_received"
    db.flush()
    return log
