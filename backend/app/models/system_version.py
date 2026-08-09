from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SystemVersion(Base):
    """系统版本记录（全局，不绑定租户）。"""

    __tablename__ = "system_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="版本号，如 v1.0.0")
    release_date: Mapped[date] = mapped_column(Date, nullable=False, comment="发布日期")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="更新说明 / 开发日志")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())