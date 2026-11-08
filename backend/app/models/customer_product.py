# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CustomerProduct(Base):
    """客户可下单产品 + 客户专属价目（未配置时 H5 不可浏览/下单任何产品）。

    单价挂在「客户 × 产品」上而不是 SKU 上：同一产品的不同型号通常同价，
    按产品维护价目比按型号维护少一个数量级的配置工作；若将来出现型号差价，
    再单独扩一张「客户 × SKU」例外价目表，不要改动本表语义。

    price 默认 0 表示「尚未定价」，H5 下单会拒绝该行，避免生成 0 元订单
    污染老板看板的销售额 / 毛利（与 SaaS 版口径一致）。
    """

    __tablename__ = "customer_products"
    __table_args__ = (UniqueConstraint("customer_id", "product_id", name="uq_customer_products"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
