from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FinanceLedger(Base):
    __tablename__ = "finance_ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    direction: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    party_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    party_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    statement_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    statement_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    biz_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
