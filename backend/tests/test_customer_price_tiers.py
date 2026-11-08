# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""客户阶梯价（customer_price_tiers）回归。

覆盖的核心风险：
- 按数量命中档位必须取「满足 min_qty 的最大档」，不能命中第一档就停；
- 起订量必须取**最小档起点**，不是命中档起点，否则大批量档会变成新的门槛；
- 优先级必须是 型号阶梯 > 型号单价 > 产品通用阶梯 > 产品单价，
  型号单价不能被产品通用阶梯抢走；
- 保存是「按 scope 整组替换」，不能误删别的 scope 的档位；
- 阶梯不能成为白名单后门，价格非法配置（不递减/重复/0 元）必须报错。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.crud.customer_price_tier import (
    PRODUCT_WIDE_SKU_ID,
    get_price_tier_map,
    replace_price_tiers,
)
from app.crud.customer_product import get_customer_product_map
from app.crud.customer_sku_price import set_customer_sku_prices
from app.models.customer_price_tier import CustomerPriceTier
from app.models.customer_product import CustomerProduct
from app.models.product import Product
from app.models.sku import Sku
from app.schemas.order import CustomerOrderItemIn
from app.services.customer_pricing import (
    CustomerPricingError,
    price_customer_order,
    resolve_price_rule,
    to_price_tiers,
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


def _set_tiers(session, customer_id: int, *, product_id: int, sku_id: int = 0, tiers: list):
    return replace_price_tiers(
        session,
        customer_id=customer_id,
        items=[{"product_id": product_id, "sku_id": sku_id, "tiers": tiers}],
    )


TIERS = [
    {"min_qty": 1, "price": "12.50"},
    {"min_qty": 100, "price": "11.80"},
    {"min_qty": 500, "price": "10.90"},
]


def test_product_tier_picks_highest_satisfied_bracket(session, customer, product, sku):
    _allow_product(session, customer, product, price="15.00")
    _set_tiers(session, customer.id, product_id=product.id, tiers=TIERS)

    cases = {1: "12.5000", 99: "12.5000", 100: "11.8000", 499: "11.8000", 500: "10.9000", 800: "10.9000"}
    for qty, expected in cases.items():
        priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=qty)])
        line = priced.lines[0]
        assert line.unit_price == Decimal(expected), f"qty={qty} 命中了错误的档位"
        assert line.source == "product_tier"
        assert line.subtotal == (line.unit_price * qty).quantize(Decimal("0.01"))


def test_min_qty_comes_from_smallest_tier_not_hit_tier(session, customer, product, sku):
    """最小档 10 件即起订量；命中 100 件档时起订量不能跟着变成 100。"""
    _allow_product(session, customer, product, price="15.00", min_qty=1)
    _set_tiers(
        session,
        customer.id,
        product_id=product.id,
        tiers=[{"min_qty": 10, "price": "12.00"}, {"min_qty": 100, "price": "11.00"}],
    )

    with pytest.raises(CustomerPricingError, match="起订量为 10"):
        price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=9)])

    priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=10)])
    assert priced.lines[0].unit_price == Decimal("12.0000")
    assert priced.lines[0].tier_min_qty == 10


def test_sku_tier_beats_everything(session, customer, product, sku):
    _allow_product(session, customer, product, price="15.00")
    _set_tiers(session, customer.id, product_id=product.id, tiers=TIERS)
    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": sku.id, "price": "20.00", "min_qty": None, "currency": None}],
    )
    _set_tiers(
        session,
        customer.id,
        product_id=product.id,
        sku_id=sku.id,
        tiers=[{"min_qty": 1, "price": "18.00"}, {"min_qty": 50, "price": "16.00"}],
    )

    priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=60)])
    assert priced.lines[0].unit_price == Decimal("16.0000")
    assert priced.lines[0].source == "sku_tier"


def test_sku_price_beats_product_wide_tier(session, customer, product, sku):
    """型号单价更具体，不能被产品通用阶梯抢走。"""
    _allow_product(session, customer, product, price="15.00")
    _set_tiers(session, customer.id, product_id=product.id, tiers=TIERS)
    set_customer_sku_prices(
        session,
        customer_id=customer.id,
        items=[{"sku_id": sku.id, "price": "14.00", "min_qty": None, "currency": None}],
    )

    priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=200)])
    assert priced.lines[0].unit_price == Decimal("14.0000")
    assert priced.lines[0].source == "sku"


def test_clearing_tier_scope_falls_back_to_flat_price(session, customer, product, sku):
    _allow_product(session, customer, product, price="15.00")
    _set_tiers(session, customer.id, product_id=product.id, tiers=TIERS)
    assert get_price_tier_map(session, customer.id)[(product.id, PRODUCT_WIDE_SKU_ID)]

    _set_tiers(session, customer.id, product_id=product.id, tiers=[])
    assert (product.id, PRODUCT_WIDE_SKU_ID) not in get_price_tier_map(session, customer.id)

    priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=200)])
    assert priced.lines[0].unit_price == Decimal("15.0000")
    assert priced.lines[0].source == "product"


def test_tier_scope_replace_does_not_touch_other_scope(session, customer, product, sku):
    _allow_product(session, customer, product, price="15.00")
    _set_tiers(session, customer.id, product_id=product.id, tiers=TIERS)
    _set_tiers(
        session,
        customer.id,
        product_id=product.id,
        sku_id=sku.id,
        tiers=[{"min_qty": 1, "price": "18.00"}],
    )

    # 只重写产品通用档，型号专属档必须原样保留
    _set_tiers(session, customer.id, product_id=product.id, tiers=[{"min_qty": 1, "price": "13.00"}])

    tier_map = get_price_tier_map(session, customer.id)
    assert [r.price for r in tier_map[(product.id, PRODUCT_WIDE_SKU_ID)]] == [Decimal("13.0000")]
    assert [r.price for r in tier_map[(product.id, sku.id)]] == [Decimal("18.0000")]


def test_tier_currency_inherits_product_level(session, customer, product, sku):
    _allow_product(session, customer, product, price="15.00", currency="USD")
    _set_tiers(session, customer.id, product_id=product.id, tiers=TIERS)

    priced = price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=100)])
    assert priced.currency == "USD"
    assert priced.lines[0].currency == "USD"


def test_tier_validation(session, customer, product, sku):
    _allow_product(session, customer, product, price="15.00")

    with pytest.raises(ValueError, match="起点"):
        _set_tiers(session, customer.id, product_id=product.id, tiers=[{"min_qty": 0, "price": "1"}])
    with pytest.raises(ValueError, match="大于 0"):
        _set_tiers(session, customer.id, product_id=product.id, tiers=[{"min_qty": 1, "price": "0"}])
    with pytest.raises(ValueError, match="重复"):
        _set_tiers(
            session,
            customer.id,
            product_id=product.id,
            tiers=[{"min_qty": 10, "price": "12"}, {"min_qty": 10, "price": "11"}],
        )
    # 数量越大单价越高 = 档位填反，必须拦住：落库后下单金额会静默算错
    with pytest.raises(ValueError, match="递减"):
        _set_tiers(
            session,
            customer.id,
            product_id=product.id,
            tiers=[{"min_qty": 1, "price": "10"}, {"min_qty": 100, "price": "12"}],
        )


def test_tier_rejects_product_outside_whitelist(session, customer, product):
    other = Product(code="P996", name="未授权产品", is_active=True)
    session.add(other)
    session.flush()

    with pytest.raises(ValueError, match="可下单范围"):
        _set_tiers(session, customer.id, product_id=other.id, tiers=[{"min_qty": 1, "price": "10"}])


def test_tier_rejects_sku_of_another_product(session, customer, product, sku):
    _allow_product(session, customer, product, price="15.00")
    other = Product(code="P995", name="另一产品", is_active=True)
    session.add(other)
    session.flush()
    foreign = _new_sku(session, other, "SKU995")

    with pytest.raises(ValueError, match="不属于产品"):
        _set_tiers(
            session,
            customer.id,
            product_id=product.id,
            sku_id=foreign.id,
            tiers=[{"min_qty": 1, "price": "10"}],
        )


def test_tier_dirty_data_cannot_bypass_whitelist(session, customer, product, sku):
    """直接写表模拟手工改库：产品不在白名单时，阶梯价也不能放行下单。"""
    session.add(
        CustomerPriceTier(
            customer_id=customer.id,
            product_id=product.id,
            sku_id=sku.id,
            min_qty=1,
            price=Decimal("5.00"),
        )
    )
    session.flush()

    with pytest.raises(CustomerPricingError, match="可下单范围"):
        price_customer_order(session, customer.id, [CustomerOrderItemIn(sku_id=sku.id, qty=1)])


def test_multi_line_order_mixes_tier_and_flat(session, customer, product, sku):
    """同一订单里两个型号各走阶梯，金额必须逐行独立计算后相加。"""
    _allow_product(session, customer, product, price="15.00")
    tiered = sku
    flat = _new_sku(session, product, "SKU-FLAT")
    _set_tiers(session, customer.id, product_id=product.id, sku_id=tiered.id, tiers=TIERS)

    priced = price_customer_order(
        session,
        customer.id,
        [CustomerOrderItemIn(sku_id=tiered.id, qty=100), CustomerOrderItemIn(sku_id=flat.id, qty=2)],
    )

    by_sku = {line.sku_id: line for line in priced.lines}
    assert by_sku[tiered.id].unit_price == Decimal("11.8000")
    assert by_sku[tiered.id].subtotal == Decimal("1180.00")
    assert by_sku[flat.id].unit_price == Decimal("15.0000")
    assert by_sku[flat.id].subtotal == Decimal("30.00")
    assert priced.amount == Decimal("1210.00")


def test_resolve_price_rule_without_qty_returns_starting_price(session, customer, product, sku):
    """展示路径不传数量：应给最小档价格，让 H5 能显示「起价」。"""
    _allow_product(session, customer, product, price="15.00")
    _set_tiers(session, customer.id, product_id=product.id, tiers=TIERS)

    rule = resolve_price_rule(
        product_cfg=get_customer_product_map(session, customer.id)[product.id],
        sku_cfg=None,
        product_tiers=to_price_tiers(get_price_tier_map(session, customer.id)[(product.id, 0)]),
    )
    assert rule is not None
    assert rule.unit_price == Decimal("12.5000")
    assert rule.min_qty == 1
    assert rule.tier_min_qty == 1
    assert [t.min_qty for t in rule.tiers] == [1, 100, 500]
