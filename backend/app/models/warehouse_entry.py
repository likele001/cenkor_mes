from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WarehouseEntry(Base):
    """入库单（独立单据化）"""
    __tablename__ = "warehouse_entries"
    __table_args__ = (UniqueConstraint("code", name="uq_warehouse_entries_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)  # draft/confirmed/cancelled
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="other")  # purchase/material_return/other
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)

    purchase_order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    material_return_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("material_returns.id", ondelete="SET NULL"), nullable=True, index=True)

    total_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("WarehouseEntryItem", back_populates="entry", cascade="all, delete-orphan")
    warehouse = relationship("Warehouse")
    purchase_order = relationship("PurchaseOrder")
    material_return = relationship("MaterialReturn")


class WarehouseEntryItem(Base):
    """入库单明细"""
    __tablename__ = "warehouse_entry_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouse_entries.id", ondelete="CASCADE"), nullable=False, index=True)

    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")

    entry = relationship("WarehouseEntry", back_populates="items")
    material = relationship("Material")
    sku = relationship("Sku")
