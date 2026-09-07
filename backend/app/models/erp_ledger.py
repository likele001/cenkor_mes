"""ERP 财务总账：会计科目 / 记账凭证 / 凭证分录 / 会计期间"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AccountSubject(Base):
    """会计科目"""
    __tablename__ = "account_subjects"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_account_subjects_tenant_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # asset/liability/equity/revenue/cost/expense
    direction: Mapped[str] = mapped_column(String(8), nullable=False, server_default="debit")  # debit 借 / credit 贷（余额方向）
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("account_subjects.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())



class Voucher(Base):
    """记账凭证"""
    __tablename__ = "vouchers"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_vouchers_tenant_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # 凭证号
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    voucher_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="normal")  # normal/收/付/转
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")  # 借贷合计
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft", index=True)  # draft/posted
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # invoice/receipt/payment/manual
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    posted_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    entries = relationship("VoucherEntry", back_populates="voucher", cascade="all, delete-orphan")


class VoucherEntry(Base):
    """凭证分录（借贷平衡）"""
    __tablename__ = "voucher_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_id: Mapped[int] = mapped_column(Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    account_subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("account_subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    party_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # customer/supplier/other
    party_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    voucher = relationship("Voucher", back_populates="entries")


class PeriodClosing(Base):
    """会计期间（结账）"""
    __tablename__ = "period_closings"
    __table_args__ = (UniqueConstraint("tenant_id", "period", name="uq_period_closings_tenant_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")  # open/closed
    closed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
