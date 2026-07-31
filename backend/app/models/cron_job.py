"""定时任务调度配置（Beat 部署级单例，非租户隔离）"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CronJob(Base):
    __tablename__ = "cron_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True,
        comment="调度唯一标识，如 crm-public-pool-auto-recycle",
    )
    task_name: Mapped[str] = mapped_column(
        String(256), nullable=False,
        comment="Celery 任务路径，如 crm.public_pool.auto_recycle",
    )
    description: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="中文描述",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True,
        comment="是否启用",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="是否系统默认任务（不可删除，task_name/description 只读）",
    )

    cron_minute: Mapped[str] = mapped_column(
        String(64), nullable=False, default="0",
        comment="分钟：0-59 或 */5 等",
    )
    cron_hour: Mapped[str] = mapped_column(
        String(64), nullable=False, default="*",
        comment="小时：0-23 或 8,12,16,20 等",
    )
    cron_day_of_month: Mapped[str] = mapped_column(
        String(64), nullable=False, default="*",
        comment="日：1-31",
    )
    cron_month_of_year: Mapped[str] = mapped_column(
        String(64), nullable=False, default="*",
        comment="月：1-12",
    )
    cron_day_of_week: Mapped[str] = mapped_column(
        String(64), nullable=False, default="*",
        comment="星期：0-6 (0=周日) 或 mon,tue 等",
    )

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "task_name": self.task_name,
            "description": self.description,
            "enabled": self.enabled,
            "is_system": self.is_system,
            "cron_minute": self.cron_minute,
            "cron_hour": self.cron_hour,
            "cron_day_of_month": self.cron_day_of_month,
            "cron_month_of_year": self.cron_month_of_year,
            "cron_day_of_week": self.cron_day_of_week,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
