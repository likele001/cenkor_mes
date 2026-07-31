from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SalaryAllowance(Base):
    """工资补贴/扣款"""
    __tablename__ = "salary_allowances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    allowance_type: Mapped[str] = mapped_column(String(16), nullable=False)  # bonus/deduction
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
