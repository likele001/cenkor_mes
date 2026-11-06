# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""库存盘点单

在此之前，账实不符只能用 `POST /stocks/adjust` 直接改数字：谁改的、改了多少、
为什么改，全靠流水 remark 里那句自由文本。盘点单把这件事补成单据：

    制单（账面快照）→ 录实盘 → 看差异 → 确认入账 → 差异可查

口径上有两个必须区分开的量：

- `book_qty`：**制单那一刻**的账面数，快照下来就不再动，用于展示「账实差异」；
- `adjusted_qty`：**确认那一刻**实际写进库存的变动量 = 实盘 − 当时的当前账面。

两者可能不等。盘点期间（制单到确认之间）仓库往往还在正常收发，如果确认时按
「实盘 − 快照账面」入账，就会把这段时间的真实出入库一并抹掉。所以确认入账一律按
「实盘 − 当前账面」，且必须走 `crud.warehouse.adjust_stock`，不允许直接改 `stocks.qty`
——否则库存流水断链，安全库存、成本核算这些下游全都跟着错。
"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# draft 制单中 / counting 盘点中 / confirmed 已确认 / cancelled 已作废
STOCKTAKE_STATUSES = ("draft", "counting", "confirmed", "cancelled")


class Stocktake(Base):
    """库存盘点单"""
    __tablename__ = "stocktakes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_stocktakes_code"),
        CheckConstraint(
            "status IN ('draft','counting','confirmed','cancelled')",
            name="ck_stocktakes_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)
    # 盘点范围：all 全仓 / product 成品 / material 物料 / selected 指定型号
    scope: Mapped[str] = mapped_column(String(16), nullable=False, server_default="all")

    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # 冗余计数：列表页不必把明细全捞出来（每次增删改盘点行时由 crud 重算）
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    counted_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    diff_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    counted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("StocktakeItem", back_populates="stocktake", cascade="all, delete-orphan")
    warehouse = relationship("Warehouse")


class StocktakeItem(Base):
    """盘点单明细：一行一个型号（SKU）"""
    __tablename__ = "stocktake_items"
    __table_args__ = (
        UniqueConstraint("stocktake_id", "sku_id", name="uq_stocktake_items_stocktake_sku"),
        # 实盘数可以为 0（盘亏到底），但不能是负数：负数不是"没盘到"，是录错了
        CheckConstraint(
            "counted_qty IS NULL OR counted_qty >= 0",
            name="ck_stocktake_items_counted_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stocktake_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocktakes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    book_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")  # 制单快照
    counted_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = 未盘
    diff_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)  # counted - book
    adjusted_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 确认时实际入账变动

    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    stocktake = relationship("Stocktake", back_populates="items")
    sku = relationship("Sku")
