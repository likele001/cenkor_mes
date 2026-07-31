from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductionCalendarDay(Base):
    __tablename__ = "production_calendar_days"
    __table_args__ = (UniqueConstraint("day", name="uq_production_calendar_days_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_workday: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    capacity_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

