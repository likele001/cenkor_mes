# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""CRM 报价转订单：真实落单、带入报价、幂等与非法输入。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.crud.crm import convert_quotation_to_order
from app.models.crm import CrmQuotation, CrmQuotationItem
from app.models.order import Order, OrderItem


def _make_quotation(
    session,
    tenant,
    customer,
    sku,
    *,
    code="QT-1",
    status="accepted",
    qty="10",
    price="100",
    item_discount="0",
    header_discount="0",
    sku_id=None,
):
    q = CrmQuotation(
        id=1,
        tenant_id=tenant.id,
        code=code,
        title="测试报价",
        customer_id=customer.id,
        status=status,
        discount_rate=Decimal(header_discount),
        valid_until=date(2026, 12, 31),
    )
    session.add(q)
    session.flush()
    item = CrmQuotationItem(
        id=1,
        tenant_id=tenant.id,
        quotation_id=q.id,
        sku_id=sku.id if sku_id is None else sku_id,
        product_name="型号A",
        quantity=Decimal(qty),
        unit_price=Decimal(price),
        discount_rate=Decimal(item_discount),
        amount=Decimal(price) * Decimal(qty),
    )
    session.add(item)
    session.flush()
    return q, item


def test_convert_creates_order_with_quoted_prices(session, tenant, customer, sku, test_user):
    q, _ = _make_quotation(
        session, tenant, customer, sku,
        qty="10", price="100", item_discount="0.05", header_discount="0.1",
    )

    result = convert_quotation_to_order(session, tenant.id, q.id, test_user.id)

    assert result["created"] is True
    order = session.get(Order, result["order_id"])
    assert order is not None
    assert order.customer_id == customer.id
    assert order.status == "draft"
    items = session.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    assert len(items) == 1
    # 100 × (1-5%) × (1-10%) = 85.5
    assert Decimal(str(items[0].unit_price)) == Decimal("85.5")
    assert Decimal(str(items[0].subtotal)) == Decimal("855.00")
    assert Decimal(str(order.amount)) == Decimal("855.00")

    session.refresh(q)
    assert q.status == "ordered"
    assert q.converted_order_id == order.id
    assert q.owner_user_id == test_user.id


def test_convert_is_idempotent(session, tenant, customer, sku, test_user):
    q, _ = _make_quotation(session, tenant, customer, sku)

    first = convert_quotation_to_order(session, tenant.id, q.id, test_user.id)
    second = convert_quotation_to_order(session, tenant.id, q.id, test_user.id)

    assert first["created"] is True
    assert second["created"] is False
    assert second["order_id"] == first["order_id"]
    count = session.scalar(select(func.count()).select_from(Order))
    assert count == 1


def test_convert_rejects_draft_quotation(session, tenant, customer, sku, test_user):
    q, _ = _make_quotation(session, tenant, customer, sku, status="draft")
    with pytest.raises(ValueError, match="仅已接受或已批准"):
        convert_quotation_to_order(session, tenant.id, q.id, test_user.id)


def test_convert_rejects_fractional_quantity(session, tenant, customer, sku, test_user):
    q, _ = _make_quotation(session, tenant, customer, sku, qty="2.5")
    with pytest.raises(ValueError, match="正整数"):
        convert_quotation_to_order(session, tenant.id, q.id, test_user.id)


def test_convert_rejects_item_without_sku(session, tenant, customer, sku, test_user):
    q, item = _make_quotation(session, tenant, customer, sku)
    item.sku_id = None
    session.flush()
    with pytest.raises(ValueError, match="缺少产品型号"):
        convert_quotation_to_order(session, tenant.id, q.id, test_user.id)


def test_convert_returns_none_for_other_tenant(session, tenant, customer, sku, test_user):
    q, _ = _make_quotation(session, tenant, customer, sku)
    assert convert_quotation_to_order(session, tenant.id + 999, q.id, test_user.id) is None


def test_convert_uses_earliest_delivery_date(session, tenant, customer, sku, test_user):
    q, item = _make_quotation(session, tenant, customer, sku)
    item.delivery_date = date(2026, 10, 1)
    session.flush()

    result = convert_quotation_to_order(session, tenant.id, q.id, test_user.id)
    assert session.get(Order, result["order_id"]).due_date == date(2026, 10, 1)
