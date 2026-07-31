from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (UniqueConstraint("order_item_id", name="uq_work_orders_order_item_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="open", index=True)

    # 老板看板：产能利用率（标准工时 / 实际工时 / 开工完工时间）
    standard_hours: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    actual_hours: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    order = relationship("Order", back_populates="work_orders")
    order_item = relationship("OrderItem", back_populates="work_orders")
    product = relationship("Product")
    sku = relationship("Sku")
    tasks = relationship("Task", back_populates="work_order", cascade="all, delete-orphan", order_by="Task.seq")
    pieces = relationship("WorkOrderPiece", back_populates="work_order", cascade="all, delete-orphan", order_by="WorkOrderPiece.piece_no")
