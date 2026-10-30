# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UpgradeJob(Base):
    """后台在线升级 / 回滚任务记录（全局，不绑定租户）。"""

    __tablename__ = "upgrade_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False, comment="upgrade / rollback")
    from_version: Mapped[str] = mapped_column(String(32), nullable=False, comment="升级前版本")
    to_version: Mapped[str] = mapped_column(String(32), nullable=False, comment="目标版本")
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="pending",
        index=True,
        comment="pending/running/awaiting_restart/success/failed/rolled_back",
    )
    stage: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default="backup",
        comment="backup/fetch/checkout/deps/migrate/build/restart/verify/done",
    )
    from_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="升级前 git commit sha（回滚用）")
    alembic_rev: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="升级前 alembic revision")
    backup_path: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="数据库备份文件路径")
    log_path: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="执行日志文件路径")
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="操作人用户 ID")
    error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
