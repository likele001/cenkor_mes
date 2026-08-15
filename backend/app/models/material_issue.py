from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MaterialIssue(Base):
    """领料单：工单领料出库"""
    __tablename__ = "material_issues"
    __table_args__ = (UniqueConstraint("code", name="uq_material_issues_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft", index=True)  # draft / issued / cancelled
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    issue_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("MaterialIssueItem", back_populates="issue", cascade="all, delete-orphan", order_by="MaterialIssueItem.id")
    warehouse = relationship("Warehouse")
    work_order = relationship("WorkOrder")


class MaterialIssueItem(Base):
    """领料明细"""
    __tablename__ = "material_issue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    issue = relationship("MaterialIssue", back_populates="items")
    material = relationship("Material")
    sku = relationship("Sku")


class MaterialReturn(Base):
    """退料单：领料后多余物料退回仓库"""
    __tablename__ = "material_returns"
    __table_args__ = (UniqueConstraint("code", name="uq_material_returns_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft", index=True)  # draft / returned / cancelled
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    issue_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("material_issues.id", ondelete="SET NULL"), nullable=True, index=True)
    return_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("MaterialReturnItem", back_populates="return_doc", cascade="all, delete-orphan", order_by="MaterialReturnItem.id")
    warehouse = relationship("Warehouse")
    work_order = relationship("WorkOrder")
    issue = relationship("MaterialIssue")


class MaterialReturnItem(Base):
    """退料明细"""
    __tablename__ = "material_return_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_returns.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_item_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("material_issue_items.id", ondelete="SET NULL"), nullable=True, index=True)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    return_doc = relationship("MaterialReturn", back_populates="items")
    issue_item = relationship("MaterialIssueItem")
    material = relationship("Material")
    sku = relationship("Sku")
