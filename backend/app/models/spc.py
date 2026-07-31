"""SPC 统计过程控制数据模型"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import JSON

from app.models.base import Base


class SpcChart(Base):
    """SPC 控制图配置"""
    __tablename__ = "spc_charts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    chart_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="xbar_r")  # xbar_r / xbar_s / np / c / p
    process_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("processes.id", ondelete="SET NULL"), nullable=True)
    sku_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("skus.id", ondelete="SET NULL"), nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")  # 子组大小
    ucl: Mapped[float | None] = mapped_column(Float, nullable=True)  # 上控制限
    lcl: Mapped[float | None] = mapped_column(Float, nullable=True)  # 下控制限
    target: Mapped[float | None] = mapped_column(Float, nullable=True)  # 目标值
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    process = relationship("Process")
    sku = relationship("Sku")
    samples = relationship("SpcSample", back_populates="chart", cascade="all, delete-orphan")


class SpcSample(Base):
    """SPC 样本数据"""
    __tablename__ = "spc_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chart_id: Mapped[int] = mapped_column(Integer, ForeignKey("spc_charts.id", ondelete="CASCADE"), nullable=False, index=True)
    sample_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 样本序号
    values_json: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 原始测量值 [1.2, 1.3, 1.1, 1.4, 1.2]
    mean: Mapped[float | None] = mapped_column(Float, nullable=True)  # 均值
    range_val: Mapped[float | None] = mapped_column("range", Float, nullable=True)  # 极差
    std_dev: Mapped[float | None] = mapped_column(Float, nullable=True)  # 标准差
    defect_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 不良数（np/c/p 图用）
    collected_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    chart = relationship("SpcChart", back_populates="samples")
