from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ReportUnit(Base):
    """报工件次 — 派工 N 件则 N 个槽位，逐件报工与审核"""

    __tablename__ = "report_units"
    __table_args__ = (
        UniqueConstraint("task_assignment_id", "unit_seq", name="uq_report_units_assignment_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_assignment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("task_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    unit_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    piece_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("work_order_pieces.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_trace_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trace_codes.id", ondelete="SET NULL"), nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # good / bad，提交后填写
    employee_attachment_ids: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qc_attachment_ids: Mapped[str | None] = mapped_column(String(512), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # draft → submitted → leader_approved → qc_approved / rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft", index=True)

    prescreen_level: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    prescreen_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    prescreen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    task_assignment = relationship("TaskAssignment", back_populates="report_units")
    task = relationship("Task")
    piece = relationship("WorkOrderPiece")
    parent_trace = relationship("TraceCode", foreign_keys=[parent_trace_id])
    user = relationship("User", foreign_keys=[user_id])
    audits = relationship("ReportUnitAudit", back_populates="report_unit", cascade="all, delete-orphan", order_by="ReportUnitAudit.id")


class ReportUnitAudit(Base):
    """件次审核流水"""

    __tablename__ = "report_unit_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("report_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    auditor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    audit_level: Mapped[str] = mapped_column(String(16), nullable=False)  # leader / qc
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # approve / reject
    attachment_ids: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    report_unit = relationship("ReportUnit", back_populates="audits")
    auditor = relationship("User", foreign_keys=[auditor_id])
