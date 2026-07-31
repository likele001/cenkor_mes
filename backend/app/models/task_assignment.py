from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TaskAssignment(Base):
    """工序任务派工明细：同一任务可派多名员工，每人有独立派工数量。"""

    __tablename__ = "task_assignments"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_assignments_task_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_qty: Mapped[int] = mapped_column(Integer, nullable=False)

    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    assigned_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    task = relationship("Task", back_populates="assignments")
    user = relationship("User", foreign_keys=[user_id])
    dispatcher = relationship("User", foreign_keys=[assigned_by])
    report_units = relationship("ReportUnit", back_populates="task_assignment", cascade="all, delete-orphan")
