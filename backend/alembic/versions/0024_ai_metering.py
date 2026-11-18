# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""0024_ai_metering - AI 用量计量与按月配额

两张表：

- `platform_ai_usage`   每次 LLM 调用的 token 流水（成本归因的事实源）
- `platform_ai_quotas`  按月配额：global 一条兜底 + extension 按扩展覆盖

**为什么要这张流水表**

cenkormes 的 AI 能力随「付费扩展」以 license 一口价卖出（22 个付费扩展在
功能市场里按年/按套卖），但 LLM 的 token 成本是按次计费的：license 收入固定，
成本随用量线性上升。没有流水就只能看到渠道商账单总额，无法回答「哪个扩展在烧钱」。
记在 `platform_ai_usage` 里，才能按扩展 / 模型 / 天聚合，并把配额卡在扩展级。

**为什么 scope_key 用空串而不是 NULL**

MySQL 唯一索引里 NULL 互不相等：`(scope, scope_key)` 一旦允许 scope_key 为 NULL，
global 这一行可以插进任意多条，配额兜底就形同虚设。因此 global 的 scope_key 统一写空串。

幂等说明：DDL 直接取模型元数据（与 0023 同一套做法），新库走 0001 的 create_all
时这些表已经在了，这里 has_table 直接跳过；存量库只补建表，不碰任何现有表与数据。

Revision ID: 0024_ai_metering
Revises: 0023_warehouse_bin_batch
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_ai_metering"
down_revision = "0023_warehouse_bin_batch"
branch_labels = None
depends_on = None

_NEW_TABLES = [
    "platform_ai_usage",
    "platform_ai_quotas",
]


def upgrade() -> None:
    from app.models.base import Base

    # 只导入 AI 模块，避免把无关模型的表一起拖进 metadata
    import app.models.ai  # noqa: F401

    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in _NEW_TABLES:
        table = Base.metadata.tables.get(name)
        if table is None:
            raise RuntimeError(
                f"模型未注册 {name}：app/models/ai.py 是否已导入 app.models? "
                "alembic/env.py 需要 import app.models 才能拿到表定义"
            )
        if insp.has_table(name):
            continue
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in reversed(_NEW_TABLES):
        if insp.has_table(name):
            op.drop_table(name)
