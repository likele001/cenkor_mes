# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""客户型号级价目（customer_sku_prices）回归。

覆盖的核心风险：
- 型号级覆盖必须优先于产品级，且同类不同型号可以不同价；
- 只改型号单价时，起订量/币种必须继承产品级，不能被默认值悄悄重置成 1/CNY；
- 型号价不能成为白名单后门：产品不在白名单时，配了型号价也不能下单；
- `price=0` 必须删除覆盖回落产品级，而不是把型号变成 0 元。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.crud.customer_product import get_customer_product_map, set_customer_products
from app.crud.customer_sku_price import (
    get_customer_sku_price_map,
    set_customer_sku_prices,
)
from app.models.customer_product import CustomerProduct
from app.models.customer_sku_price import CustomerSkuPrice
from app.models.product import Product
from app.models.sku import Sku
from app.schemas.order import CustomerOrderItemIn
from app.services.customer_pricing import (
    CustomerPricingError,
    price_customer_order,
    resolve_price_rule,
)


def _allow_product(session, customer, product, *, price: str, min_qty: int = 1, currency: str = "CNY"):
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


def _new_sku(session, product, code: str) -> Sku:
    s = Sku(product_id=product.id, code=code, name=f"型号{code}", is_active=True)
    session.add(s)
    session.flush()
    return s


def test_sku_price_overrides_product_price(session, customer, product, sku):
    """同产品两个型号：一个走型号价，一个回落产品价。"""
    _allow_product(session, customer, product, price="10.00")
    red = sku
    blue = _new_sku(session, product, "SKU-BLUE")
    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": red.id, "price": "13.50", "min_qty": None, "currency": None}],
    )

    priced = price_customer_order(
        session,
        customer.id,
        [CustomerOrderItemIn(sku_id=red.id, qty=2), CustomerOrderItemIn(sku_id=blue.id, qty=2)],
    )

    by_sku = {line.sku_id: line for line in priced.lines}
    assert by_sku[red.id].unit_price == Decimal("13.5000")
    assert by_sku[red.id].source == "sku"
    assert by_sku[blue.id].unit_price == Decimal("10.0000")
    assert by_sku[blue.id].source == "product"
    assert priced.amount == Decimal("47.00")


def test_inherited_min_qty_is_not_reset_by_sku_override(session, customer, product, sku):
    """产品级起订 10，只改型号单价时起订量必须继续是 10。"""
    _allow_product(session, customer, product, price="10.00", min_qty=10)
    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": sku.id, "price": "12.00", "min_qty": None, "currency": None}],
    )

    rule = resolve_price_rule(
        product_cfg=get_customer_product_map(session, customer.id)[product.id],
        sku_cfg=get_customer_sku_price_map(session, customer.id)[sku.id],
    )
    assert rule is not None
    assert rule.unit_price == Decimal("12.0000")
    assert rule.min_qty == 10

    with pytest.raises(CustomerPricingError, match="起订量为 10"):
        price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=9)])


def test_inherited_currency_follows_product(session, customer, product, sku):
    _allow_product(session, customer, product, price="10.00", currency="USD")
    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": sku.id, "price": "11.00", "min_qty": None, "currency": None}],
    )

    priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=1)])
    assert priced.currency == "USD"
    assert priced.lines[0].currency == "USD"


def test_explicit_sku_min_qty_and_currency_win(session, customer, product, sku):
    _allow_product(session, customer, product, price="10.00", min_qty=5, currency="CNY")
    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": sku.id, "price": "9.00", "min_qty": 50, "currency": "EUR"}],
    )

    priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=50)])
    assert priced.lines[0].unit_price == Decimal("9.0000")
    assert priced.currency == "EUR"

    with pytest.raises(CustomerPricingError, match="起订量为 50"):
        price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=49)])


def test_zero_price_removes_override_and_falls_back(session, customer, product, sku):
    """price=0 表示删除覆盖，不能留一条 0 元行把型号变成免费。"""
    _allow_product(session, customer, product, price="10.00")
    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": sku.id, "price": "13.00", "min_qty": None, "currency": None}],
    )
    assert sku.id in get_customer_sku_price_map(session, customer.id)

    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": sku.id, "price": "0", "min_qty": None, "currency": None}],
    )
    assert sku.id not in get_customer_sku_price_map(session, customer.id)

    priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=1)])
    assert priced.lines[0].unit_price == Decimal("10.0000")
    assert priced.lines[0].source == "product"


def test_sku_price_cannot_bypass_whitelist(session, customer, product, sku):
    """产品不在白名单时，即使库里已有型号价也不能下单（白名单是唯一准入）。

    直接写表模拟历史脏数据 / 手工改库，绕开配置接口的校验，
    确保定价解析这一层仍然把关。
    """
    session.add(CustomerSkuPrice(customer_id=customer.id, sku_id=sku.id, price=Decimal("5.00")))
    session.flush()

    with pytest.raises(CustomerPricingError, match="可下单范围"):
        price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=1)])


def test_sku_pricing_rejects_sku_outside_whitelist(session, customer, product):
    other = Product(code="P997", name="未授权产品", is_active=True)
    session.add(other)
    session.flush()
    foreign = _new_sku(session, other, "SKU997")

    with pytest.raises(ValueError, match="可下单范围"):
        set_customer_sku_prices(
            session,
            customer_id=customer.id,
            items=[{"sku_id": foreign.id, "price": "5", "min_qty": None, "currency": None}],
        )


def test_sku_pricing_validation(session, customer, product, sku):
    _allow_product(session, customer, product, price="10.00")

    with pytest.raises(ValueError, match="负数"):
        set_customer_sku_prices(
            session, customer.id,
            [{"sku_id": sku.id, "price": "-1", "min_qty": None, "currency": None}],
        )
    with pytest.raises(ValueError, match="起订量"):
        set_customer_sku_prices(
            session, customer.id,
            [{"sku_id": sku.id, "price": "1", "min_qty": 0, "currency": None}],
        )
    with pytest.raises(ValueError, match="币种"):
        set_customer_sku_prices(
            session, customer.id,
            [{"sku_id": sku.id, "price": "1", "min_qty": None, "currency": "XXX"}],
        )
    with pytest.raises(ValueError, match="不存在或已停用"):
        set_customer_sku_prices(
            session, customer.id,
            [{"sku_id": 999999, "price": "1", "min_qty": None, "currency": None}],
        )


def test_sku_override_survives_product_scope_resave(session, customer, product, sku):
    """保存产品范围不能连带清空型号级覆盖。"""
    _allow_product(session, customer, product, price="10.00")
    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": sku.id, "price": "15.00", "min_qty": None, "currency": None}],
    )
    set_customer_products(session, customer_id=customer.id, product_ids=[product.id])

    assert get_customer_sku_price_map(session, customer.id)[sku.id].price == Decimal("15.0000")
