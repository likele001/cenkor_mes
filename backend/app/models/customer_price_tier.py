# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""客户阶梯价（按采购数量分档定价）。

定价优先级（越具体越优先）：
`customer_price_tiers`(型号专属档) → `customer_sku_prices`(型号单价)
→ `customer_price_tiers`(产品通用档) → `customer_products`(产品单价)。

`sku_id = 0` 表示**产品通用阶梯**（该产品下所有型号共用一套档位），
不用 NULL 的原因是一条硬约束：MySQL 的唯一索引里 NULL 互不相等，
`UNIQUE(customer_id, product_id, sku_id, min_qty)` 在 sku_id 为 NULL 时
根本不生效，同一档位能被重复插入。用 0 占位保住唯一性，代价是这个列
不能建外键（0 在 skus 表里不存在），型号有效性由 CRUD 层校验。

档位语义：`min_qty` 是**该档的起订数量（含）**，不是额外增量。
同一 scope 内最小的一档即该型号/产品的起订量。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CustomerPriceTier(Base):
    """客户 × 产品（× 型号）的阶梯单价。"""

    __tablename__ = "customer_price_tiers"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "product_id",
            "sku_id",
            "min_qty",
            name="uq_customer_price_tiers_scope_qty",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 0 = 产品通用阶梯；>0 = 该型号专属阶梯（无外键，见模块 docstring）
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", index=True)
    # 档位起点（含），同 scope 内最小档即起订量
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
