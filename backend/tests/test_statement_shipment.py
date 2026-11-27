# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""按发货对账：金额口径、状态校验、明细来源。"""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud.finance import calc_shipment_statement_amount, create_statement
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.shipment import Shipment, ShipmentItem
from app.models.sku import Sku


@pytest.fixture
def shipped(session: Session, customer: Customer, sku: Sku):
    order = Order(customer_id=customer.id, code="SO-SHIP-1", status="confirmed")
    order.items = [
        OrderItem(line_no=1, sku_id=sku.id, qty=10, unit_price=Decimal("5.5000"), subtotal=Decimal("55.00"))
    ]
    session.add(order)
    session.flush()
    shipment = Shipment(order_id=order.id, code="SH-1", status="shipped")
    shipment.items = [ShipmentItem(sku_id=sku.id, qty=4)]
    session.add(shipment)
    session.flush()
    return shipment


def test_amount_uses_order_unit_price(session: Session, shipped: Shipment):
    assert calc_shipment_statement_amount(session, shipped) == Decimal("22.0000")


def test_pending_shipment_rejected(session: Session, shipped: Shipment):
    shipped.status = "pending"
    with pytest.raises(ValueError, match="尚未发货"):
        calc_shipment_statement_amount(session, shipped)


def test_create_statement_by_shipment_source(session: Session, customer: Customer, shipped: Shipment):
    stmt = create_statement(
        session,
        customer_id=customer.id,
        code="ST-SHIP-1",
        shipment_amounts=[(shipped.id, Decimal("22.0000"))],
    )
    session.flush()
    assert stmt.total_amount == Decimal("22.0000")
    item = stmt.items[0]
    assert item.source_type == "shipment"
    assert item.shipment_id == shipped.id
    assert item.order_id is None
