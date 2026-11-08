# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""客户型号级价目（产品级价目的精细覆盖）。

定价优先级：`customer_sku_prices`（型号级）→ `customer_products`（产品级）。
型号级只解决「同一产品下不同颜色/尺寸/规格价格不同」的场景，
产品白名单仍然是唯一的准入入口 —— 产品不在白名单里，即使配了型号价也不可下单。

`min_qty` / `currency` 为 NULL 表示**继承产品级**，而不是取默认值 1 / CNY：
否则管理员只改型号单价，起订量会被悄悄重置成 1，把产品级的起订限制抹掉。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CustomerSkuPrice(Base):
    """客户 + 型号级别的单价 / 起订量 / 币种覆盖。"""

    __tablename__ = "customer_sku_prices"
    __table_args__ = (
        UniqueConstraint("customer_id", "sku_id", name="uq_customer_sku_prices_customer_sku"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 与产品级价目同精度：单价 4 位小数，避免规格价差被截断
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    min_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
