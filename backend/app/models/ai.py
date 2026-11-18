# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""平台 AI 配置层（开源核心共享）。

单租户形态：仅保留「总开关 + 多网关 + 多模型」三张配置表，
不含 lightmes 的租户级 override（tenant_id）。作为所有 AI 功能
（核心 Pro 路由 + 付费扩展）共用的唯一配置源。

对话/消息/告警事件表随波次 2 的业务功能再建。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlatformAiProfile(Base):
    """平台 AI 总开关（网关与模型在 platform_ai_gateways / platform_ai_models）。

    base_url / api_key / timeout_seconds 为「兜底」配置：当所选网关未填写时回退使用。
    """

    __tablename__ = "platform_ai_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformAiGateway(Base):
    """AI 网关（OpenAI 兼容服务端点）：一个网关 = 一组 base_url + api_key。"""

    __tablename__ = "platform_ai_gateways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformAiModel(Base):
    """网关下的模型条目：code 为业务引用名，model_id 为服务端真实模型标识。"""

    __tablename__ = "platform_ai_models"
    __table_args__ = (UniqueConstraint("gateway_id", "code", name="uq_platform_ai_models_gateway_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gateway_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    is_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformAiUsage(Base):
    """一次 LLM 调用的用量流水（计量与成本归因的唯一事实源）。

    为什么单独建表而不是塞进 PlatformAiProfile：AI 扩展是按 license 一口价卖的，
    但每次调用的 token 成本是真实的，账单必须能按「扩展 / 模型 / 天」聚合出来，
    否则 AI 卖得越多亏得越多。写入走独立事务（见 services/ai/metering.py），
    不跟随业务事务回滚——业务失败也要记成本。
    """

    __tablename__ = "platform_ai_usage"
    __table_args__ = (
        Index("ix_platform_ai_usage_month", "created_at", "scope_key"),
    )

    # 流水是增长最快的表，主键用 BIGINT；SQLite（测试库）不支持 BIGINT 自增，
    # 用 with_variant 降到 INTEGER，避免单测 INSERT 时报 NOT NULL constraint。
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)
    # core = 核心内置调用；extension = 付费扩展发起（scope_key 为扩展 key）
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="core")
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    # chat / stream / vision / test
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="chat")
    model_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 超出配额但仍放行（policy=warn）时打标，便于事后算“该收紧哪个扩展”
    over_quota: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    path: Mapped[str | None] = mapped_column(String(200), nullable=True)


class PlatformAiQuota(Base):
    """AI 用量配额（按月）。

    scope=global 一条兜底；scope=extension 按扩展覆盖（scope_key 为空串占位，
    因为 MySQL 唯一索引里 NULL 互不相等，用空串才能让唯一约束真正生效）。
    limit_tokens 为空或 0 表示不限；policy=warn 只标记放行，block 直接拒绝调用。
    """

    __tablename__ = "platform_ai_quotas"
    __table_args__ = (UniqueConstraint("scope", "scope_key", name="uq_platform_ai_quotas_scope_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="global")
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    limit_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    policy: Mapped[str] = mapped_column(String(16), nullable=False, default="warn")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

