# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""ERP 发票管理：销项/进项发票登记"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Invoice(Base):
    """发票（销项/进项）"""
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_invoices_tenant_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # 内部单号 INV...
    invoice_no: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 税务发票号

    direction: Mapped[str] = mapped_column(String(8), nullable=False, index=True)  # out 销项 / in 进项
    invoice_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="special", index=True)  # special 专票 / general 普票

    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True)
    supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True)
    statement_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("statements.id", ondelete="SET NULL"), nullable=True, index=True)
    supplier_statement_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("supplier_statements.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True, index=True)

    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, server_default="0.00")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")  # 不含税
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")  # 价税合计

    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)  # draft/posted/void
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    """发票明细"""
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sku_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=True)
    material_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=True)

    qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="1.0000")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, server_default="0.0000")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, server_default="0.00")
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    invoice = relationship("Invoice", back_populates="items")
