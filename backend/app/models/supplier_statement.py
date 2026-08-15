from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SupplierStatement(Base):
    """供应商对账单（应付）"""
    __tablename__ = "supplier_statements"
    __table_args__ = (UniqueConstraint("code", name="uq_supplier_statements_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")  # draft → confirmed → paid
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier")
    items = relationship("SupplierStatementItem", back_populates="statement", cascade="all, delete-orphan")


class SupplierStatementItem(Base):
    """供应商对账单明细（按采购单）"""
    __tablename__ = "supplier_statement_items"
    __table_args__ = (UniqueConstraint("statement_id", "purchase_order_id", name="uq_supplier_statement_items_stmt_po"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    statement_id: Mapped[int] = mapped_column(Integer, ForeignKey("supplier_statements.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    statement = relationship("SupplierStatement", back_populates="items")
    purchase_order = relationship("PurchaseOrder")
