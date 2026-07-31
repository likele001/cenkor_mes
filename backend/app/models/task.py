from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("task_code", name="uq_tasks_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    process_id: Mapped[int] = mapped_column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    task_code: Mapped[str] = mapped_column(String(32), nullable=False)
    planned_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending", index=True)

    assigned_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assigned_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    equipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    work_order = relationship("WorkOrder", back_populates="tasks")
    process = relationship("Process")
    equipment = relationship("Equipment")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    dispatcher = relationship("User", foreign_keys=[assigned_by])
    assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
