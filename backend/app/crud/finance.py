from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.crud.process_route import get_default_route_for_product
from app.models.finance import Statement, StatementItem
from app.models.order import Order, OrderItem
from app.models.process_price import ProcessPrice
from app.models.sku import Sku


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


def create_statement(
    db: Session,
    customer_id: int,
    code: str,
    order_amounts: list[tuple[int, Decimal]],
    period_start: date | None = None,
    period_end: date | None = None,
    remark: str | None = None,
) -> Statement:
    total = sum(amt for _, amt in order_amounts)
    stmt = Statement(
        customer_id=customer_id,
        code=code,
        period_start=period_start,
        period_end=period_end,
        total_amount=total,
        remark=remark,
        status="draft",
    )
    stmt.items = [
        StatementItem(order_id=oid, amount=amt)
        for oid, amt in order_amounts
    ]
    db.add(stmt)
    db.flush()
    return stmt


def get_statement_by_id(db: Session, statement_id: int) -> Statement | None:
    return db.scalar(
        select(Statement)
        .where(Statement.id == statement_id)
        .options(selectinload(Statement.customer), selectinload(Statement.items).selectinload(StatementItem.order))
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


def update_statement_status(db: Session, stmt: Statement, new_status: str) -> Statement:
    stmt.status = new_status
    db.flush()
    return stmt
