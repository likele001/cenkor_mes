from datetime import datetime, time

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (UniqueConstraint("code", name="uq_shift_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    rest_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    shift_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="day")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ShiftSchedule(Base):
    __tablename__ = "shift_schedules"
    __table_args__ = (UniqueConstraint("user_id", "work_date", name="uq_schedule_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    shift_id: Mapped[int] = mapped_column(Integer, ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date: Mapped[str] = mapped_column(String(10), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    shift = relationship("Shift")
    user = relationship("User")
