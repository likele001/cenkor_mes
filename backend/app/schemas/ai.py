# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""平台 AI 配置层请求 schema（网关 / 模型 / 总开关 / 连通性测试 / Prompt）。"""
from pydantic import BaseModel, Field


class AiGatewaySettingsIn(BaseModel):
    """平台总开关 + 兜底 base_url/api_key/timeout（单租户，对应 PlatformAiProfile）。"""

    enabled: bool | None = None
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=10, le=600)


class PlatformAiGatewayIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str | None = None
    enabled: bool = True
    timeout_seconds: int = Field(default=120, ge=10, le=600)
    sort_order: int = 0
    is_default: bool = False


class PlatformAiGatewayUpdateIn(BaseModel):
    code: str | None = None
    display_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=10, le=600)
    sort_order: int | None = None
    is_default: bool | None = None


class PlatformAiModelIn(BaseModel):
    gateway_id: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    is_vision: bool = False
    is_active: bool = True
    sort_order: int = 0
    is_default: bool = False


class PlatformAiModelUpdateIn(BaseModel):
    gateway_id: int | None = Field(default=None, ge=1)
    code: str | None = None
    display_name: str | None = None
    model_id: str | None = None
    is_vision: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    is_default: bool | None = None


class AiPromptSettingsIn(BaseModel):
    prompt: str | None = Field(default=None, max_length=2000)


class AiTestIn(BaseModel):
    gateway_id: int | None = Field(default=None, ge=1)
    model_code: str | None = None
