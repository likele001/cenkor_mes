from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Report(Base):
    """报工记录"""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False, index=True)
    report_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    good_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bad_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 附件 ID 列表，逗号分隔（兼容 MySQL 5.7 无 JSON 列）
    attachment_ids: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # submitted → leader_approved → qc_approved / rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="submitted", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    task = relationship("Task")
    report_user = relationship("User", foreign_keys=[report_user_id])
    audits = relationship("ReportAudit", back_populates="report", cascade="all, delete-orphan", order_by="ReportAudit.id")


class ReportAudit(Base):
    """审核流水"""
    __tablename__ = "report_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    auditor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    audit_level: Mapped[str] = mapped_column(String(16), nullable=False)  # leader / qc
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # approve / reject
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    report = relationship("Report", back_populates="audits")
    auditor = relationship("User", foreign_keys=[auditor_id])
