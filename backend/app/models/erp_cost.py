"""ERP 工单成本核算：实际成本归集 + 报价毛利对比"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkOrderCost(Base):
    """工单实际成本汇总"""
    __tablename__ = "work_order_costs"
    __table_args__ = (UniqueConstraint("tenant_id", "work_order_id", name="uq_work_order_costs_tenant_wo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    sku_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("skus.id", ondelete="SET NULL"), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    material_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    overhead_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0.0000")

    quote_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    gross_margin: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, server_default="0.0000")

    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)  # draft/calculated/closed
    computed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("WorkOrderCostItem", back_populates="cost", cascade="all, delete-orphan")


class WorkOrderCostItem(Base):
    """成本归集明细（可追溯）"""
    __tablename__ = "work_order_cost_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    cost_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_order_costs.id", ondelete="CASCADE"), nullable=False, index=True)
    cost_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # material/labor/overhead
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # material_issue/salary/manual/overhead_rate
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ref_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    cost = relationship("WorkOrderCost", back_populates="items")
