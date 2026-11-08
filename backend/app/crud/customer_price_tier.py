# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""客户阶梯价读写。

保存语义是「**按 scope 整组替换**」：一次提交针对某个 (product_id, sku_id)
给出完整的档位列表，不在列表里的档位即被删除。用整组替换而不是逐档 diff，
是因为档位之间天然是一组有序区间，逐档 diff 需要额外一套身份标识，
反而更容易出现「改了数量起点后留下孤儿档位」的脏数据。

`sku_id = 0` 表示产品通用阶梯，>0 表示型号专属阶梯（详见模型 docstring）。
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.customer_product import (
    UNIT_PRICE_QUANT,
    get_customer_product_map,
)
from app.models.customer_price_tier import CustomerPriceTier
from app.models.sku import Sku

PRODUCT_WIDE_SKU_ID = 0


def list_price_tier_rows(db: Session, customer_id: int) -> list[CustomerPriceTier]:
    """返回该客户全部阶梯价行，按产品 / 型号 / 档位起点升序。"""
    return list(
        db.scalars(
            select(CustomerPriceTier)
            .where(CustomerPriceTier.customer_id == customer_id)
            .order_by(
                CustomerPriceTier.product_id.asc(),
                CustomerPriceTier.sku_id.asc(),
                CustomerPriceTier.min_qty.asc(),
            )
        ).all()
    )


def get_price_tier_map(
    db: Session, customer_id: int
) -> dict[tuple[int, int], list[CustomerPriceTier]]:
    """按 (product_id, sku_id) 分组建索引，每组内档位按 min_qty 升序。

    分组后的列表本身就是「从最小起订量到大宗量」的阶梯，
    定价解析只需线性扫一遍取最高满足档。
    """
    grouped: dict[tuple[int, int], list[CustomerPriceTier]] = {}
    for row in list_price_tier_rows(db, customer_id):
        grouped.setdefault((row.product_id, row.sku_id), []).append(row)
    return grouped


def replace_price_tiers(
    db: Session,
    customer_id: int,
    items: list[dict],
) -> list[CustomerPriceTier]:
    """按 scope 整组替换阶梯价。

    Args:
        db: 数据库会话。
        customer_id: 客户 ID。
        items: 每项含 product_id / sku_id（0 = 产品通用）/ tiers：
            `[{"min_qty": int, "price": Decimal}]`。`tiers` 传空列表表示
            清空该 scope 的全部档位、回落到单一单价。

    Returns:
        该客户更新后的全部阶梯价行。

    Raises:
        ValueError: 产品不在白名单、型号不属于该产品、档位为空、
            档位数量 < 1、单价 <= 0、档位起点重复、价格未随数量递减。
    """
    product_map = get_customer_product_map(db, customer_id)
    existing = get_price_tier_map(db, customer_id)

    for item in items:
        product_id = int(item["product_id"])
        sku_id = int(item.get("sku_id") or PRODUCT_WIDE_SKU_ID)
        if product_id not in product_map:
            raise ValueError(f"产品#{product_id} 不在该客户的可下单范围内，请先保存产品范围")

        if sku_id != PRODUCT_WIDE_SKU_ID:
            sku = db.get(Sku, sku_id)
            if sku is None or not sku.is_active:
                raise ValueError(f"型号#{sku_id} 不存在或已停用")
            if sku.product_id != product_id:
                raise ValueError(f"型号 {sku.code} 不属于产品#{product_id}")

        normalized = _normalize_tiers(db_sku_label=sku_id, tiers=item.get("tiers") or [])

        # 按 min_qty 对齐而不是「全删再插」：SQLAlchemy 的 unit of work 会先 INSERT
        # 后 DELETE，全删再插会撞 (scope, min_qty) 唯一键。按档位对齐还能保住
        # 既有行的 id / created_at，管理员改价不会把档位「重建」一遍。
        old_rows = {int(r.min_qty): r for r in existing.pop((product_id, sku_id), [])}
        for min_qty, price in normalized:
            row = old_rows.pop(min_qty, None)
            if row is not None:
                row.price = price
                continue
            db.add(
                CustomerPriceTier(
                    customer_id=customer_id,
                    product_id=product_id,
                    sku_id=sku_id,
                    min_qty=min_qty,
                    price=price,
                )
            )
        for row in old_rows.values():
            db.delete(row)

    db.flush()
    return list_price_tier_rows(db, customer_id)


def _normalize_tiers(db_sku_label: int, tiers: list[dict]) -> list[tuple[int, Decimal]]:
    """校验并规范化一组档位，返回按 min_qty 升序的 (min_qty, price)。"""
    scope = "产品通用" if db_sku_label == PRODUCT_WIDE_SKU_ID else f"型号#{db_sku_label}"
    if not tiers:
        return []

    parsed: dict[int, Decimal] = {}
    for tier in tiers:
        min_qty = int(tier["min_qty"])
        if min_qty < 1:
            raise ValueError(f"{scope} 的阶梯起点必须至少为 1")
        if min_qty in parsed:
            raise ValueError(f"{scope} 的阶梯起点 {min_qty} 重复，请合并为一行")
        price = Decimal(str(tier["price"])).quantize(UNIT_PRICE_QUANT)
        if price <= 0:
            raise ValueError(f"{scope} 的阶梯价必须大于 0；要取消阶梯请提交空档位列表")
        parsed[min_qty] = price

    ordered = sorted(parsed.items())
    # 数量越大单价越高说明档位填反了，直接拦住：这种配置会算错整单金额，
    # 且下单时不会报错，只能等对账才发现
    for (prev_qty, prev_price), (cur_qty, cur_price) in zip(ordered, ordered[1:]):
        if cur_price > prev_price:
            raise ValueError(
                f"{scope} 的阶梯价必须随数量递减：{cur_qty} 件单价 {cur_price} "
                f"高于 {prev_qty} 件单价 {prev_price}"
            )
    return ordered
