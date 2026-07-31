from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkOrderPiece(Base):
    """工单件次 — 同一物理件在全工序流转中的统一身份"""

    __tablename__ = "work_order_pieces"
    __table_args__ = (
        UniqueConstraint("work_order_id", "piece_no", name="uq_work_order_pieces_wo_piece"),
        UniqueConstraint("product_code", name="uq_work_order_pieces_product_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    piece_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    last_process_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("processes.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="in_progress")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    last_process = relationship("Process", foreign_keys=[last_process_id])

    work_order = relationship("WorkOrder", back_populates="pieces")
