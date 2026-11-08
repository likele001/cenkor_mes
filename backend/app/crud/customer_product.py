# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer_product import CustomerProduct
from app.models.product import Product

# 币种白名单：金额只做数值累加、不做汇率换算，因此整单必须同一币种。
# 必须与管理端币种下拉保持一致，否则选了 HKD 保存会 400。
SUPPORTED_CURRENCIES = frozenset({"CNY", "USD", "EUR", "KRW", "JPY", "HKD", "GBP"})
UNIT_PRICE_QUANT = Decimal("0.0001")


def list_customer_product_ids(db: Session, customer_id: int) -> list[int]:
    return [row.product_id for row in list_customer_product_rows(db, customer_id)]


def list_customer_product_rows(db: Session, customer_id: int) -> list[CustomerProduct]:
    """返回该客户全部可下单产品配置行（含价目），按产品 ID 升序。"""
    return list(
        db.scalars(
            select(CustomerProduct)
            .where(CustomerProduct.customer_id == customer_id)
            .order_by(CustomerProduct.product_id.asc())
        ).all()
    )


def get_customer_product_map(db: Session, customer_id: int) -> dict[int, CustomerProduct]:
    """按 product_id 建索引，供 catalog / 下单定价共用，避免逐行查库。"""
    return {row.product_id: row for row in list_customer_product_rows(db, customer_id)}


def list_customer_products_with_detail(db: Session, customer_id: int) -> list[Product]:
    ids = list_customer_product_ids(db, customer_id)
    if not ids:
        return []
    return list(
        db.scalars(
            select(Product)
            .where(Product.id.in_(ids), Product.is_active.is_(True))
            .order_by(Product.id.asc())
        ).all()
    )


def set_customer_products(db: Session, customer_id: int, product_ids: list[int]) -> list[int]:
    """保存可下单产品范围，但**保留已有行的价目**。

    历史实现是「整表删除 + 重建」，加了 price/min_qty/currency 后会把管理员
    维护的价格全部清零，所以改成增量对齐：删除移出的行、新增移入的行、
    仍在范围内的行原样保留。
    """
    wanted: set[int] = set()
    for pid in product_ids:
        prod = db.scalar(select(Product).where(Product.id == pid, Product.is_active.is_(True)))
        if prod:
            wanted.add(pid)

    existing = get_customer_product_map(db, customer_id)
    for pid, row in existing.items():
        if pid not in wanted:
            db.delete(row)
    for pid in sorted(wanted - set(existing)):
        db.add(CustomerProduct(customer_id=customer_id, product_id=pid))
    db.flush()
    return list_customer_product_ids(db, customer_id)


def set_customer_product_pricing(
    db: Session,
    customer_id: int,
    items: list[dict],
) -> list[CustomerProduct]:
    """批量更新客户专属价目。

    Args:
        db: 数据库会话。
        customer_id: 客户 ID。
        items: 每项含 product_id / price / min_qty / currency。

    Returns:
        更新后的全部配置行。

    Raises:
        ValueError: 产品不在白名单、数量为负、起订量小于 1 或币种不支持。
    """
    rows = get_customer_product_map(db, customer_id)
    for item in items:
        pid = int(item["product_id"])
        row = rows.get(pid)
        if row is None:
            raise ValueError(f"产品#{pid} 不在该客户的可下单范围内，请先保存产品范围")
        price = Decimal(str(item["price"])).quantize(UNIT_PRICE_QUANT)
        if price < 0:
            raise ValueError("销售单价不能为负数")
        min_qty = int(item["min_qty"])
        if min_qty < 1:
            raise ValueError("起订量至少为 1")
        currency = str(item["currency"]).upper()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"不支持的币种：{currency}")
        row.price = price
        row.min_qty = min_qty
        row.currency = currency
    db.flush()
    return list_customer_product_rows(db, customer_id)
