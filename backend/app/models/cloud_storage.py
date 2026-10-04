# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储配置模型（全局单行配置 + 历史附件迁移任务）。

凭据按 provider 分列存储，值为 AES-256-GCM 加密后的密文（Base64），
读取展示时脱敏，见 app/services/cloud_storage_config.py。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CloudStorageConfig(Base):
    """云存储全局配置：当前激活 provider + 各 provider 密文凭据。"""

    __tablename__ = "cloud_storage_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    active_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", server_default="local", comment="当前激活 provider"
    )
    # 各 provider 凭据密文（AES-256-GCM, Base64）；明文为凭据 JSON
    creds_local: Mapped[str | None] = mapped_column(Text, nullable=True)
    creds_aliyun: Mapped[str | None] = mapped_column(Text, nullable=True)
    creds_tencent: Mapped[str | None] = mapped_column(Text, nullable=True)
    creds_qiniu: Mapped[str | None] = mapped_column(Text, nullable=True)
    creds_upyun: Mapped[str | None] = mapped_column(Text, nullable=True)
    keep_local_backup: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", comment="上传云端时是否回写一份本地备份"
    )
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CloudStorageMigrationJob(Base):
    """历史附件迁移任务状态（本地/源云 → 目标云）。"""

    __tablename__ = "cloud_storage_migration_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="local", server_default="local")
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    done: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending", comment="pending/running/done/failed"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
