from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SalarySlip(Base):
    __tablename__ = "salary_slips"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_salary_slips_user_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)

    item_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    hourly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    hourly_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    bonus_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    deduction_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    signature_attachment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("attachments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirm_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending", index=True)
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    signature_attachment = relationship("Attachment", foreign_keys=[signature_attachment_id])
