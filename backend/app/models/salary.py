from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SalaryItem(Base):
    """工资明细 — 审核通过的报工(计件) or 每日工时(计时)"""
    __tablename__ = "salary_items"
    __table_args__ = (
        UniqueConstraint("report_id", name="uq_salary_items_report"),
        UniqueConstraint("report_unit_id", name="uq_salary_items_report_unit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reports.id", ondelete="RESTRICT"), nullable=True, index=True)
    report_unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("report_units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    sku_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=True)
    process_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=True)

    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    good_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    item_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="piece")  # piece / hourly / absent
    work_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    work_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    report = relationship("Report")
    report_unit = relationship("ReportUnit")
    user = relationship("User", foreign_keys=[user_id])
    sku = relationship("Sku")
    process = relationship("Process")
