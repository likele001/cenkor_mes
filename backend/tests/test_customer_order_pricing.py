# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""客户下单定价：多行金额、起订量、白名单、币种、价目持久化回归。

覆盖的核心风险：
- H5 客户下单曾不写 unit_price / subtotal，导致 orders.amount 恒为 0；
- 客户可通过请求体自带 unit_price 自己报价（现在 schema 不接收该字段）；
- 「保存可下单产品范围」曾整表删除重建，加了价格列会清空价目；
- 金额算法必须与 production_rollup.recalc_order_amount 完全一致。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.crud.customer_product import (
    get_customer_product_map,
    set_customer_product_pricing,
    set_customer_products,
)
from app.models.customer import Customer
from app.models.customer_product import CustomerProduct
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.sku import Sku
from app.schemas.order import CustomerOrderItemIn
from app.services.customer_pricing import CustomerPricingError, price_customer_order
from app.services.production_rollup import recalc_order_amount


def _allow(
    session,
    customer: Customer,
    product: Product,
    *,
    price: str = "0",
    min_qty: int = 1,
    currency: str = "CNY",
) -> CustomerProduct:
    """给客户配置一个可下单产品及其价目。"""
    row = CustomerProduct(
        customer_id=customer.id,
        product_id=product.id,
        price=Decimal(price),
        min_qty=min_qty,
        currency=currency,
    )
    session.add(row)
    session.flush()
    return row


def _extra_sku(session, product: Product, code: str) -> Sku:
    s = Sku(product_id=product.id, code=code, name=f"型号{code}", is_active=True)
    session.add(s)
    session.flush()
    return s


def _items(sku: Sku, qty: int, *, extra: tuple[Sku, int] | None = None):
    rows = [CustomerOrderItemIn(sku_id=sku.id, qty=qty)]
    if extra:
        rows.append(CustomerOrderItemIn(sku_id=extra[0].id, qty=extra[1]))
    return rows


def test_multi_line_amount_uses_customer_price(session, customer, product, sku):
    """两行购物车：单价 12.3456，3 件 + 2 件 → 37.04 + 24.69 = 61.73。"""
    _allow(session, customer, product, price="12.3456", min_qty=2, currency="CNY")
    second = _extra_sku(session, product, "SKU002")

    priced = price_customer_order(
        session,
        customer_id=customer.id,
        items=_items(sku, 3, extra=(second, 2)),
    )

    assert len(priced.lines) == 2
    assert priced.lines[0].unit_price == Decimal("12.3456")
    assert priced.lines[0].subtotal == Decimal("37.04")
    assert priced.lines[1].subtotal == Decimal("24.69")
    assert priced.amount == Decimal("61.73")
    assert priced.currency == "CNY"


def test_min_qty_is_enforced(session, customer, product, sku):
    _allow(session, customer, product, price="10", min_qty=5)
    with pytest.raises(CustomerPricingError, match="起订量为 5"):
        price_customer_order(session, customer.id, _items(sku, 4))


def test_unpriced_product_cannot_be_ordered(session, customer, product, sku):
    """0 元价目 = 尚未定价，必须拒绝，避免 0 元订单污染销售额看板。"""
    _allow(session, customer, product, price="0")
    with pytest.raises(CustomerPricingError, match="尚未定价"):
        price_customer_order(session, customer.id, _items(sku, 1))


def test_sku_outside_whitelist_is_rejected(session, customer, product, sku):
    other = Product(code="P999", name="未授权产品", is_active=True)
    session.add(other)
    session.flush()
    foreign = _extra_sku(session, other, "SKU999")
    _allow(session, customer, product, price="10")

    with pytest.raises(CustomerPricingError, match="不在您的可下单范围内"):
        price_customer_order(session, customer.id, _items(foreign, 1))


def test_mixed_currency_is_rejected(session, customer, product, sku):
    """金额不做汇率换算，混合币种相加没有业务含义，直接拒绝。"""
    other = Product(code="P998", name="外币产品", is_active=True)
    session.add(other)
    session.flush()
    foreign = _extra_sku(session, other, "SKU998")
    _allow(session, customer, product, price="10", currency="CNY")
    _allow(session, customer, other, price="10", currency="USD")

    with pytest.raises(CustomerPricingError, match="混合币种"):
        price_customer_order(session, customer.id, _items(sku, 1, extra=(foreign, 1)))


def test_request_body_cannot_override_price(session, customer, product, sku):
    """客户端即便硬塞 unit_price，Pydantic 也会丢弃，仍按价目表计价。"""
    _allow(session, customer, product, price="99.5")
    payload = CustomerOrderItemIn.model_validate(
        {"sku_id": sku.id, "qty": 2, "unit_price": "0.01"}
    )
    assert not hasattr(payload, "unit_price")

    priced = price_customer_order(session, customer.id, [payload])
    assert priced.lines[0].unit_price == Decimal("99.5000")
    assert priced.amount == Decimal("199.00")


def test_saving_product_scope_preserves_pricing(session, customer, product):
    """保存产品范围不能把管理员维护的价目清零（历史实现是整表删除重建）。"""
    _allow(session, customer, product, price="88.88", min_qty=7, currency="USD")
    set_customer_products(session, customer_id=customer.id, product_ids=[product.id])

    row = get_customer_product_map(session, customer.id)[product.id]
    assert row.price == Decimal("88.8800")
    assert row.min_qty == 7
    assert row.currency == "USD"


def test_pricing_update_validation(session, customer, product):
    _allow(session, customer, product, price="1")
    rows = set_customer_product_pricing(
        session,
        customer_id=customer.id,
        items=[{"product_id": product.id, "price": "25.5", "min_qty": 3, "currency": "EUR"}],
    )
    assert rows[0].currency == "EUR"
    assert rows[0].min_qty == 3

    with pytest.raises(ValueError, match="负数"):
        set_customer_product_pricing(
            session, customer.id,
            [{"product_id": product.id, "price": "-1", "min_qty": 1, "currency": "CNY"}],
        )
    with pytest.raises(ValueError, match="起订量"):
        set_customer_product_pricing(
            session, customer.id,
            [{"product_id": product.id, "price": "1", "min_qty": 0, "currency": "CNY"}],
        )
    with pytest.raises(ValueError, match="币种"):
        set_customer_product_pricing(
            session, customer.id,
            [{"product_id": product.id, "price": "1", "min_qty": 1, "currency": "XXX"}],
        )
    with pytest.raises(ValueError, match="可下单范围"):
        set_customer_product_pricing(
            session, customer.id,
            [{"product_id": 99999, "price": "1", "min_qty": 1, "currency": "CNY"}],
        )


def test_service_amount_matches_recalc_order_amount(session, customer, product, sku):
    """写入 OrderItem 后由统一口径重算，金额必须与定价服务一致。"""
    _allow(session, customer, product, price="12.3456", min_qty=2)
    second = _extra_sku(session, product, "SKU003")
    priced = price_customer_order(session, customer.id, _items(sku, 3, extra=(second, 2)))

    order = Order(customer_id=customer.id, code="ORD-TEST-1", status="pending_confirm")
    order.items = [
        OrderItem(
            line_no=idx,
            sku_id=line.sku_id,
            qty=line.qty,
            unit_price=line.unit_price,
            subtotal=line.subtotal,
        )
        for idx, line in enumerate(priced.lines, start=1)
    ]
    session.add(order)
    session.flush()

    assert recalc_order_amount(session, order) == priced.amount
    assert order.amount == priced.amount
