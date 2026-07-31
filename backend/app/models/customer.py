from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("code", name="uq_customers_code"),
        UniqueConstraint("user_id", name="uq_customers_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    # 画像与销售字段
    lifecycle_stage: Mapped[str] = mapped_column(String(16), nullable=False, server_default="prospect")
    health_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    health_level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    risk_flag: Mapped[str] = mapped_column(String(16), nullable=False, server_default="none")
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scale: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    total_lifetime_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    last_order_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_order_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    last_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    open_opportunity_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    open_opportunity_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    active_contract_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    overdue_payment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    owner = relationship("User", foreign_keys=[owner_user_id])
    orders = relationship("Order", back_populates="customer")
