from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MrpPlan(Base):
    """MRP 物料需求计划批次"""
    __tablename__ = "mrp_plans"
    __table_args__ = (UniqueConstraint("code", name="uq_mrp_plans_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="computed", index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="work_order")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_skus: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_materials: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_purchase_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("MrpItem", back_populates="plan", cascade="all, delete-orphan", order_by="MrpItem.id")
    creator = relationship("User", foreign_keys=[created_by])


class MrpItem(Base):
    """MRP 计划明细行：一个工单 × 一个物料的净需求计算结果"""
    __tablename__ = "mrp_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("mrp_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True)
    bom_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("material_boms.id", ondelete="SET NULL"), nullable=True)
    bom_scope: Mapped[str | None] = mapped_column(String(16), nullable=True)

    wo_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    qty_per: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    gross_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    net_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    suggested_purchase_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    plan = relationship("MrpPlan", back_populates="items")
    work_order = relationship("WorkOrder")
    order = relationship("Order")
    sku = relationship("Sku")
    material = relationship("Material")
    supplier = relationship("Supplier")
