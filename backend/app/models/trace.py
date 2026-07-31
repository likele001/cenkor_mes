from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TraceCode(Base):
    """工序追溯记录；成品码 product_code 在首工序赋码，全工序共用"""
    __tablename__ = "trace_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    work_order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"), nullable=True, index=True)
    piece_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("work_order_pieces.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_trace_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trace_codes.id", ondelete="SET NULL"), nullable=True, index=True)
    task_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)

    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False)
    process_id: Mapped[int] = mapped_column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False)
    report_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reports.id", ondelete="RESTRICT"), nullable=True)
    report_unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("report_units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    order = relationship("Order")
    sku = relationship("Sku")
    process = relationship("Process")
    work_order = relationship("WorkOrder")
    piece = relationship("WorkOrderPiece")
    parent_trace = relationship("TraceCode", remote_side="TraceCode.id", foreign_keys=[parent_trace_id])
    report = relationship("Report")
    report_unit = relationship("ReportUnit", foreign_keys=[report_unit_id])
    user = relationship("User", foreign_keys=[user_id])
