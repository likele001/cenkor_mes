from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ApprovalFlow(Base):
    __tablename__ = "approval_flows"
    __table_args__ = (UniqueConstraint("biz_type", "name", name="uq_approval_flows_biz_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    steps = relationship("ApprovalStep", back_populates="flow", cascade="all, delete-orphan", order_by="ApprovalStep.step_order")


class ApprovalStep(Base):
    __tablename__ = "approval_steps"
    __table_args__ = (UniqueConstraint("flow_id", "step_order", name="uq_approval_steps_flow_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_flows.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    can_skip: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)

    flow = relationship("ApprovalFlow", back_populates="steps")