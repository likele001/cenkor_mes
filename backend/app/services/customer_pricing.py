# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""客户下单定价服务。

安全口径：**单价只从服务端价目表取**（型号级 `customer_sku_prices` 优先，
回落产品级 `customer_products`），请求体里不带单价字段，客户无法自己报价；
金额算法与 `app.services.production_rollup.recalc_order_amount` 保持一致
（单价 × 数量，按分取整），避免 H5 订单与管理端订单两套口径。

币种不做汇率换算，整单必须同一币种，否则不同币种的数值直接相加没有业务含义。
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.crud.customer_product import SUPPORTED_CURRENCIES, get_customer_product_map
from app.crud.customer_sku_price import get_customer_sku_price_map
from app.models.customer_product import CustomerProduct
from app.models.customer_sku_price import CustomerSkuPrice
from app.models.sku import Sku
from app.schemas.order import CustomerOrderItemIn

CENT = Decimal("0.01")
UNIT_PRICE_QUANT = Decimal("0.0001")

PriceSource = Literal["sku", "product"]


class CustomerPricingError(ValueError):
    """定价或白名单校验失败；路由层转成 HTTP 400 业务错误。"""


@dataclass(frozen=True)
class PriceRule:
    """某个型号对某个客户的**生效**定价（已合并型号级与产品级）。"""

    unit_price: Decimal
    min_qty: int
    currency: str
    source: PriceSource


@dataclass(frozen=True)
class PricedLine:
    sku_id: int
    sku_code: str
    qty: int
    remark: str | None
    unit_price: Decimal
    subtotal: Decimal
    currency: str
    source: PriceSource


@dataclass(frozen=True)
class PricedOrder:
    lines: list[PricedLine]
    amount: Decimal
    currency: str


def resolve_price_rule(
    product_cfg: CustomerProduct | None,
    sku_cfg: CustomerSkuPrice | None,
) -> PriceRule | None:
    """把型号级 / 产品级两条配置合并成一条生效定价。

    型号级覆盖只在 `price > 0` 时生效；`min_qty` / `currency` 为 NULL 时
    逐字段回落到产品级，这样「只改型号单价」不会把产品级起订量重置成 1。

    Args:
        product_cfg: 产品级价目行；None 表示该产品不在客户白名单。
        sku_cfg: 型号级价目行；None 表示没有型号级覆盖。

    Returns:
        PriceRule；返回 None 表示该型号未定价（不允许下单）。
    """
    if product_cfg is None:
        return None

    if sku_cfg is not None:
        sku_price = Decimal(str(sku_cfg.price or 0)).quantize(UNIT_PRICE_QUANT)
        if sku_price > 0:
            return PriceRule(
                unit_price=sku_price,
                min_qty=int(sku_cfg.min_qty) if sku_cfg.min_qty is not None else int(product_cfg.min_qty or 1),
                currency=str(sku_cfg.currency or product_cfg.currency or "CNY").upper(),
                source="sku",
            )

    product_price = Decimal(str(product_cfg.price or 0)).quantize(UNIT_PRICE_QUANT)
    if product_price <= 0:
        return None
    return PriceRule(
        unit_price=product_price,
        min_qty=int(product_cfg.min_qty or 1),
        currency=str(product_cfg.currency or "CNY").upper(),
        source="product",
    )


def price_customer_order(
    db: Session,
    customer_id: int,
    items: list[CustomerOrderItemIn],
) -> PricedOrder:
    """把客户提交的多行购物车解析成带单价、小计、总额的订单行。

    Args:
        db: 数据库会话。
        customer_id: 已认证客户档案 ID（不信任请求体里的客户信息）。
        items: 购物车行，仅含 sku_id / qty / remark。

    Returns:
        PricedOrder：逐行定价结果、整单金额、整单币种。

    Raises:
        CustomerPricingError: 型号不可用 / 不在白名单 / 未定价 /
            低于起订量 / 币种不支持 / 混合币种。
    """
    product_map = get_customer_product_map(db, customer_id=customer_id)
    sku_price_map = get_customer_sku_price_map(db, customer_id=customer_id)
    lines: list[PricedLine] = []
    currencies: set[str] = set()
    total = Decimal("0")

    for row in items:
        sku = db.get(Sku, row.sku_id)
        if sku is None or not sku.is_active:
            raise CustomerPricingError(f"型号#{row.sku_id}不可用")
        if sku.product_id not in product_map:
            raise CustomerPricingError(f"型号 {sku.code} 不在您的可下单范围内")

        rule = resolve_price_rule(product_map[sku.product_id], sku_price_map.get(sku.id))
        if rule is None:
            raise CustomerPricingError(f"型号 {sku.code} 尚未定价，请联系工厂配置价格后再下单")
        if row.qty < rule.min_qty:
            raise CustomerPricingError(f"型号 {sku.code} 起订量为 {rule.min_qty}，当前数量 {row.qty}")
        if rule.currency not in SUPPORTED_CURRENCIES:
            raise CustomerPricingError(f"型号 {sku.code} 的币种 {rule.currency} 不受支持，请联系工厂")
        currencies.add(rule.currency)

        subtotal = (rule.unit_price * Decimal(row.qty)).quantize(CENT)
        total += subtotal
        lines.append(
            PricedLine(
                sku_id=sku.id,
                sku_code=sku.code,
                qty=row.qty,
                remark=row.remark,
                unit_price=rule.unit_price,
                subtotal=subtotal,
                currency=rule.currency,
                source=rule.source,
            )
        )

    if len(currencies) > 1:
        raise CustomerPricingError(
            "同一订单不支持混合币种，请分开下单：" + "、".join(sorted(currencies))
        )
    return PricedOrder(
        lines=lines,
        amount=total.quantize(CENT),
        currency=next(iter(currencies), "CNY"),
    )
