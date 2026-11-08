# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""客户型号级价目读写。

语义约定：`price <= 0` 视为「不覆盖」，直接删除该行回落到产品级价目，
而不是存一条 0 元行 —— 0 元行在定价解析里没有意义，还会让管理端误以为配过价。
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.customer_product import (
    SUPPORTED_CURRENCIES,
    UNIT_PRICE_QUANT,
    get_customer_product_map,
)
from app.models.customer_sku_price import CustomerSkuPrice
from app.models.sku import Sku


def list_customer_sku_price_rows(db: Session, customer_id: int) -> list[CustomerSkuPrice]:
    """返回该客户全部型号级价目覆盖行。"""
    return list(
        db.scalars(
            select(CustomerSkuPrice)
            .where(CustomerSkuPrice.customer_id == customer_id)
            .order_by(CustomerSkuPrice.sku_id.asc())
        ).all()
    )


def get_customer_sku_price_map(db: Session, customer_id: int) -> dict[int, CustomerSkuPrice]:
    """按 sku_id 建索引，供 catalog / 下单定价共用，避免逐行查库。"""
    return {row.sku_id: row for row in list_customer_sku_price_rows(db, customer_id)}


def list_customer_skus(db: Session, customer_id: int, product_id: int | None = None) -> list[Sku]:
    """列出客户白名单产品下的可售型号（供管理端型号价目表格展开）。

    Args:
        db: 数据库会话。
        customer_id: 客户 ID。
        product_id: 只取某个产品的型号；None 表示全部白名单产品。

    Returns:
        在售型号列表，按 product_id / id 升序。
    """
    product_map = get_customer_product_map(db, customer_id)
    if product_id is not None:
        ids = [product_id] if product_id in product_map else []
    else:
        ids = list(product_map.keys())
    if not ids:
        return []
    return list(
        db.scalars(
            select(Sku)
            .where(Sku.product_id.in_(ids), Sku.is_active.is_(True))
            .order_by(Sku.product_id.asc(), Sku.id.asc())
        ).all()
    )


def set_customer_sku_prices(
    db: Session,
    customer_id: int,
    items: list[dict],
) -> list[CustomerSkuPrice]:
    """批量写入型号级价目覆盖（增量对齐，不整表重建）。

    Args:
        db: 数据库会话。
        customer_id: 客户 ID。
        items: 每项含 sku_id / price / min_qty / currency。
            `price <= 0` 表示删除覆盖、回落到产品级价目；
            `min_qty` / `currency` 传 None 表示继承产品级。

    Returns:
        更新后的全部覆盖行。

    Raises:
        ValueError: 型号不存在或已停用、型号所属产品不在白名单、
            单价为负、起订量小于 1、币种不支持。
    """
    product_map = get_customer_product_map(db, customer_id)
    existing = get_customer_sku_price_map(db, customer_id)

    for item in items:
        sku_id = int(item["sku_id"])
        sku = db.get(Sku, sku_id)
        if sku is None or not sku.is_active:
            raise ValueError(f"型号#{sku_id} 不存在或已停用")
        if sku.product_id not in product_map:
            raise ValueError(
                f"型号 {sku.code} 所属产品不在该客户的可下单范围内，请先保存产品范围"
            )

        price = Decimal(str(item["price"])).quantize(UNIT_PRICE_QUANT)
        if price < 0:
            raise ValueError("型号单价不能为负数")
        # None 表示继承产品级，不是「取默认值」，两者语义完全不同
        raw_min_qty = item.get("min_qty")
        min_qty = None if raw_min_qty is None else int(raw_min_qty)
        if min_qty is not None and min_qty < 1:
            raise ValueError("起订量至少为 1")
        raw_currency = item.get("currency")
        currency = None if raw_currency is None else str(raw_currency).upper()
        if currency is not None and currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"不支持的币种：{currency}")

        row = existing.get(sku_id)
        if price <= 0:
            if row is not None:
                db.delete(row)
                existing.pop(sku_id, None)
            continue
        if row is None:
            row = CustomerSkuPrice(customer_id=customer_id, sku_id=sku_id)
            db.add(row)
            existing[sku_id] = row
        row.price = price
        row.min_qty = min_qty
        row.currency = currency

    db.flush()
    return list_customer_sku_price_rows(db, customer_id)
