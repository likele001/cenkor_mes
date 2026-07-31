"""模具/工装管理数据模型"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Mold(Base):
    """模具台账"""
    __tablename__ = "molds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mold_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="injection")  # injection/die_casting/stamping/other
    workshop: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")  # active/retired/maintenance

    sku_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("skus.id", ondelete="SET NULL"), nullable=True)
    expected_lifespan: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 预计寿命（模次）
    current_shots: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")  # 当前模次
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_maintenance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_maintenance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    maintenance_interval_shots: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 保养间隔模次
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    sku = relationship("Sku")


class MoldMaintenanceLog(Base):
    """模具维保记录"""
    __tablename__ = "mold_maintenance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mold_id: Mapped[int] = mapped_column(Integer, ForeignKey("molds.id", ondelete="CASCADE"), nullable=False, index=True)
    maintenance_type: Mapped[str] = mapped_column(String(32), nullable=False)  # preventive/corrective/inspection
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    shots_at_maintenance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checked_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    mold = relationship("Mold")


class MoldProcessBinding(Base):
    """模具与工序关联"""
    __tablename__ = "mold_process_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mold_id: Mapped[int] = mapped_column(Integer, ForeignKey("molds.id", ondelete="CASCADE"), nullable=False, index=True)
    process_id: Mapped[int] = mapped_column(Integer, ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True)

    mold = relationship("Mold")
    process = relationship("Process")
