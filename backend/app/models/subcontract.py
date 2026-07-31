from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SubcontractOrder(Base):
    """委外单"""
    __tablename__ = "subcontract_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")  # draft/sent/partial_received/received/settled
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier")
    items = relationship("SubcontractOrderItem", back_populates="order", cascade="all, delete-orphan")
    send_logs = relationship("SubcontractSendLog", back_populates="order", cascade="all, delete-orphan")
    receive_logs = relationship("SubcontractReceiveLog", back_populates="order", cascade="all, delete-orphan")


class SubcontractOrderItem(Base):
    """委外明细"""
    __tablename__ = "subcontract_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False, index=True)
    process_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("processes.id", ondelete="SET NULL"), nullable=True, index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sent_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    order = relationship("SubcontractOrder", back_populates="items")
    sku = relationship("Sku")
    process = relationship("Process")


class SubcontractSendLog(Base):
    """委外发料记录"""
    __tablename__ = "subcontract_send_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("subcontract_order_items.id", ondelete="CASCADE"), nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    order = relationship("SubcontractOrder", back_populates="send_logs")
    item = relationship("SubcontractOrderItem")


class SubcontractReceiveLog(Base):
    """委外收货记录"""
    __tablename__ = "subcontract_receive_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("subcontract_order_items.id", ondelete="CASCADE"), nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    received_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    order = relationship("SubcontractOrder", back_populates="receive_logs")
    item = relationship("SubcontractOrderItem")
