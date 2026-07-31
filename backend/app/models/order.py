from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("code", name="uq_orders_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("crm_opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    opportunity = relationship("CrmOpportunity", foreign_keys=[opportunity_id])

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # 老板看板：销售额 / 订单成本 / 实际完成时间
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    cost_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    actual_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    work_orders = relationship("WorkOrder", back_populates="order")
    confirmer = relationship("User", foreign_keys=[confirmed_by])


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "line_no", name="uq_order_items_order_line_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)

    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    # 老板看板：单价 / 小计
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")

    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    order = relationship("Order", back_populates="items")
    sku = relationship("Sku")
    work_orders = relationship("WorkOrder", back_populates="order_item")
