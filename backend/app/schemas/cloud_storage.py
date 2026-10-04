# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储配置接口的输入 Schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CloudCredsIn(BaseModel):
    """某 provider 的凭据。留空/掩码字段将保留原值（避免编辑时误清空密钥）。"""

    endpoint: str | None = Field(default=None, max_length=200)
    region: str | None = Field(default=None, max_length=100)
    bucket: str | None = Field(default=None, max_length=200)
    access_key: str | None = Field(default=None, max_length=200)
    secret_key: str | None = Field(default=None, max_length=200)
    custom_domain: str | None = Field(default=None, max_length=200)
    prefix: str | None = Field(default=None, max_length=100)

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ActivateIn(BaseModel):
    provider: str = Field(min_length=1, max_length=20)


class SettingsIn(BaseModel):
    keep_local_backup: bool


class MigrationIn(BaseModel):
    """历史附件迁移：把 source（当前仅 local）的存量附件批量搬到目标云 provider。"""

    target: str = Field(min_length=1, max_length=20)
    source: str = Field(default="local", max_length=20)
