# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.crud.approval_record import record_status, status_action
from app.crud.process_route import get_default_route_for_product
from app.models.finance import Statement, StatementItem
from app.models.order import Order, OrderItem
from app.models.process_price import ProcessPrice
from app.models.shipment import Shipment
from app.models.sku import Sku
from app.models.user import User


def calc_order_statement_amount(db: Session, order: Order) -> Decimal:
    """按订单明细：型号数量 × 默认工艺路线各工序工价之和。"""
    items = db.scalars(
        select(OrderItem)
        .where(OrderItem.order_id == order.id)
        .options(selectinload(OrderItem.sku).selectinload(Sku.product))
    ).all()
    if not items:
        raise ValueError(f"订单 {order.code} 无明细行")

    total = Decimal("0")
    for oi in items:
        sku = oi.sku
        if not sku:
            raise ValueError(f"订单 {order.code} 明细 SKU 不存在")
        route = get_default_route_for_product(db, sku.product_id)
        route_unit = Decimal("0")
        missing: list[int] = []
        for step in route.steps:
            price = db.scalar(
                select(ProcessPrice.unit_price).where(
                    ProcessPrice.sku_id == sku.id,
                    ProcessPrice.process_id == step.process_id,
                    ProcessPrice.is_active.is_(True),
                )
            )
            if price is None:
                missing.append(step.process_id)
            else:
                route_unit += Decimal(str(price))
        if missing:
            raise ValueError(f"订单 {order.code} 型号 {sku.code} 缺少工序工价（process_id={missing[0]}）")
        total += route_unit * int(oi.qty)
    return total


def _order_unit_prices(db: Session, order: Order) -> dict[int, Decimal]:
    """订单内每个型号的加权单价：Σsubtotal / Σqty，无金额时回退 unit_price。"""
    rows = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    agg: dict[int, list] = {}
    for oi in rows:
        slot = agg.setdefault(oi.sku_id, [0, Decimal("0"), None])
        slot[0] += int(oi.qty)
        slot[1] += Decimal(str(oi.subtotal or 0))
        if slot[2] is None:
            slot[2] = oi.unit_price
    out: dict[int, Decimal] = {}
    for sku_id, (qty, subtotal, unit_price) in agg.items():
        if qty <= 0:
            continue
        out[sku_id] = (
            (subtotal / Decimal(qty)).quantize(Decimal("0.0001"))
            if subtotal > 0
            else Decimal(str(unit_price or 0))
        )
    return out


def calc_shipment_statement_amount(db: Session, shipment: Shipment) -> Decimal:
    """按发货对账：发货数量 × 订单明细单价（同型号多行取加权单价）。"""
    if shipment.status not in ("shipped", "signed"):
        raise ValueError(f"发货单 {shipment.code} 尚未发货，不能对账")
    order = shipment.order
    if not order:
        raise ValueError(f"发货单 {shipment.code} 未关联订单")
    items = shipment.items or []
    if not items:
        raise ValueError(f"发货单 {shipment.code} 无明细")
    prices = _order_unit_prices(db, order)
    total = Decimal("0")
    for it in items:
        if int(it.qty) <= 0:
            raise ValueError(f"发货单 {shipment.code} 存在非正数量")
        if it.sku_id not in prices:
            raise ValueError(f"发货单 {shipment.code} 的型号不在订单 {order.code} 明细中")
        total += Decimal(int(it.qty)) * prices[it.sku_id]
    return total.quantize(Decimal("0.0001"))


# 只有确认之后的账单才真正占用来源单据。草稿既没有下游动作也没有金额锁定，
# 弃用一张草稿不该把订单/发货单永久锁死——历史上就是这么锁死且无法释放的。
BILLED_STATEMENT_STATUSES = ("confirmed", "partial", "paid")

# 可对账的订单状态：草稿 / 待确认还没定下来，不给开票
BILLABLE_ORDER_STATUSES = ("confirmed", "producing", "shipped", "completed")


def list_billed_shipment_ids(
    db: Session, *, exclude_statement_id: int | None = None
) -> set[int]:
    stmt = (
        select(StatementItem.shipment_id)
        .join(Statement, Statement.id == StatementItem.statement_id)
        .where(
            StatementItem.shipment_id.is_not(None),
            Statement.status.in_(BILLED_STATEMENT_STATUSES),
        )
    )
    if exclude_statement_id is not None:
        stmt = stmt.where(StatementItem.statement_id != exclude_statement_id)
    return {int(x) for x in db.scalars(stmt).all() if x is not None}


def list_billed_order_ids(
    db: Session, *, exclude_statement_id: int | None = None
) -> set[int]:
    stmt = (
        select(StatementItem.order_id)
        .join(Statement, Statement.id == StatementItem.statement_id)
        .where(
            StatementItem.order_id.is_not(None),
            Statement.status.in_(BILLED_STATEMENT_STATUSES),
        )
    )
    if exclude_statement_id is not None:
        stmt = stmt.where(StatementItem.statement_id != exclude_statement_id)
    return {int(x) for x in db.scalars(stmt).all() if x is not None}


def list_billable_orders(
    db: Session, customer_id: int, *, limit: int = 300
) -> list[Order]:
    """客户名下「状态已落定 + 未被已确认账单占用」的订单。"""
    billed = list_billed_order_ids(db)
    rows = db.scalars(
        select(Order)
        .where(
            Order.customer_id == customer_id,
            Order.status.in_(BILLABLE_ORDER_STATUSES),
        )
        .order_by(Order.id.desc())
        .limit(limit)
    ).all()
    return [o for o in rows if o.id not in billed]


def ensure_sources_unbilled(db: Session, stmt: Statement) -> None:
    """确认前复核来源单据。

    草稿不锁单，同一张订单/发货单因此可能被两张草稿同时勾中；
    重复占用必须在「确认」这一刻拦住，否则会重复计应收。
    """
    billed_orders = list_billed_order_ids(db, exclude_statement_id=stmt.id)
    billed_shipments = list_billed_shipment_ids(db, exclude_statement_id=stmt.id)
    for it in stmt.items:
        if it.order_id and it.order_id in billed_orders:
            code = it.order.code if it.order else f"#{it.order_id}"
            raise ValueError(f"订单 {code} 已在其他已确认对账单中对过账，不能重复确认")
        if it.shipment_id and it.shipment_id in billed_shipments:
            code = it.shipment.code if it.shipment else f"#{it.shipment_id}"
            raise ValueError(f"发货单 {code} 已在其他已确认对账单中对过账，不能重复确认")


def create_statement(
    db: Session,
    customer_id: int,
    code: str,
    order_amounts: list[tuple[int, Decimal]] | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    remark: str | None = None,
    due_date: date | None = None,
    shipment_amounts: list[tuple[int, Decimal]] | None = None,
) -> Statement:
    order_amounts = order_amounts or []
    shipment_amounts = shipment_amounts or []
    if not order_amounts and not shipment_amounts:
        raise ValueError("对账单至少需要一条明细")
    total = sum((amt for _, amt in order_amounts), Decimal("0")) + sum(
        (amt for _, amt in shipment_amounts), Decimal("0")
    )
    stmt = Statement(
        customer_id=customer_id,
        code=code,
        period_start=period_start,
        period_end=period_end,
        total_amount=total,
        remark=remark,
        due_date=due_date,
        status="draft",
    )
    stmt.items = [
        StatementItem(order_id=oid, source_type="order", amount=amt)
        for oid, amt in order_amounts
    ] + [
        StatementItem(shipment_id=sid, source_type="shipment", amount=amt)
        for sid, amt in shipment_amounts
    ]
    db.add(stmt)
    db.flush()
    return stmt


def get_statement_by_id(db: Session, statement_id: int) -> Statement | None:
    return db.scalar(
        select(Statement)
        .where(Statement.id == statement_id)
        .options(
            selectinload(Statement.customer),
            selectinload(Statement.items).selectinload(StatementItem.order),
            selectinload(Statement.items).selectinload(StatementItem.shipment),
        )
    )


def list_statements(
    db: Session,
    customer_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Statement]:
    stmt = select(Statement)
    if customer_id is not None:
        stmt = stmt.where(Statement.customer_id == customer_id)
    if status:
        stmt = stmt.where(Statement.status == status)
    stmt = stmt.order_by(Statement.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def update_statement_status(
    db: Session,
    stmt: Statement,
    new_status: str,
    *,
    operator: User | int | None = None,
    action: str | None = None,
    channel: str = "web",
    reason: str | None = None,
) -> Statement:
    old_status = stmt.status
    stmt.status = new_status
    record_status(
        db,
        biz_type="statement",
        biz_id=stmt.id,
        biz_code=stmt.code,
        action=action or status_action(new_status),
        operator=operator,
        from_status=old_status,
        to_status=new_status,
        channel=channel,
        reason=reason,
    )
    db.flush()
    return stmt
