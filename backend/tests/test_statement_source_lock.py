# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""对账单来源占用：草稿不锁单、确认时拦重复、待开票列表过滤未定状态。"""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud.finance import (
    ensure_sources_unbilled,
    list_billable_orders,
    list_billed_order_ids,
    list_billed_shipment_ids,
)
from app.models.customer import Customer
from app.models.finance import Statement, StatementItem
from app.models.order import Order, OrderItem
from app.models.sku import Sku


def _order(db: Session, customer: Customer, sku: Sku, *, code: str, status: str = "confirmed") -> Order:
    o = Order(customer_id=customer.id, code=code, status=status)
    o.items = [OrderItem(line_no=1, sku_id=sku.id, qty=10, unit_price=Decimal("5.0000"), subtotal=Decimal("50.00"))]
    db.add(o)
    db.flush()
    return o


def _stmt(db: Session, customer: Customer, order: Order, *, code: str, status: str = "draft") -> Statement:
    s = Statement(customer_id=customer.id, code=code, total_amount=Decimal("50.00"), status=status)
    s.items = [StatementItem(order_id=order.id, source_type="order", amount=Decimal("50.00"))]
    db.add(s)
    db.flush()
    return s


def test_draft_statement_does_not_lock_source(session: Session, customer: Customer, sku: Sku):
    """草稿弃用后不该把订单永久锁死：只有确认后的账单才算占用。"""
    order = _order(session, customer, sku, code="SO-LOCK-1")
    stmt = _stmt(session, customer, order, code="ST-LOCK-1")
    assert order.id not in list_billed_order_ids(session)

    stmt.status = "confirmed"
    session.flush()
    assert order.id in list_billed_order_ids(session)


def test_partial_and_paid_still_lock(session: Session, customer: Customer, sku: Sku):
    order = _order(session, customer, sku, code="SO-LOCK-2")
    stmt = _stmt(session, customer, order, code="ST-LOCK-2", status="paid")
    assert order.id in list_billed_order_ids(session)
    assert order.id not in list_billed_order_ids(session, exclude_statement_id=stmt.id)


def test_confirm_rejects_duplicate_source(session: Session, customer: Customer, sku: Sku):
    """两张草稿勾了同一张订单：第一张确认后，第二张再确认必须被拦。"""
    order = _order(session, customer, sku, code="SO-LOCK-3")
    first = _stmt(session, customer, order, code="ST-LOCK-3A")
    second = _stmt(session, customer, order, code="ST-LOCK-3B")

    ensure_sources_unbilled(session, first)  # 自己占自己不算冲突
    first.status = "confirmed"
    session.flush()

    with pytest.raises(ValueError, match="已在其他已确认对账单"):
        ensure_sources_unbilled(session, second)


def test_billable_orders_skip_unsettled_status(session: Session, customer: Customer, sku: Sku):
    _order(session, customer, sku, code="SO-DRAFT", status="draft")
    _order(session, customer, sku, code="SO-PENDING", status="pending_confirm")
    confirmed = _order(session, customer, sku, code="SO-CONFIRMED", status="confirmed")

    codes = {o.code for o in list_billable_orders(session, customer.id)}
    assert "SO-DRAFT" not in codes
    assert "SO-PENDING" not in codes
    assert "SO-CONFIRMED" in codes

    # 被已确认账单占用后就不再出现在待开票列表
    _stmt(session, customer, confirmed, code="ST-BILLED", status="confirmed")
    codes = {o.code for o in list_billable_orders(session, customer.id)}
    assert "SO-CONFIRMED" not in codes


def test_shipment_source_lock_follows_statement_status(session: Session, customer: Customer, sku: Sku):
    from app.models.shipment import Shipment, ShipmentItem

    order = _order(session, customer, sku, code="SO-LOCK-4")
    shipment = Shipment(order_id=order.id, code="SH-LOCK-4", status="shipped")
    shipment.items = [ShipmentItem(sku_id=sku.id, qty=4)]
    session.add(shipment)
    session.flush()

    stmt = Statement(customer_id=customer.id, code="ST-LOCK-4", total_amount=Decimal("20.00"), status="draft")
    stmt.items = [StatementItem(shipment_id=shipment.id, source_type="shipment", amount=Decimal("20.00"))]
    session.add(stmt)
    session.flush()

    assert shipment.id not in list_billed_shipment_ids(session)
    stmt.status = "partial"
    session.flush()
    assert shipment.id in list_billed_shipment_ids(session)
