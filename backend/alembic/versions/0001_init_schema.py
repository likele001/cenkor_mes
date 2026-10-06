# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""0001_init_schema - 初始化所有现有表

对已有库执行时幂等（checkfirst=True）；
对新库执行时通过 create_all 建所有已注册模型的表。
cenkormes 项目从此版本开始正式使用 alembic 管理迁移。

Revision ID: 0001_init
Revises:
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import context

    from app.models.base import Base

    if context.is_offline_mode():
        raise RuntimeError(
            "0001_init 依赖 metadata 建表，无法在 `--sql` 离线模式下渲染。"
            "离线出 SQL 请先用一个空库在线执行，或改用 autogenerate 生成的显式版本。"
        )

    # 用 alembic 的 bind，而不是 app.core.db.engine：
    # 后者读 settings.DB_URL，会绕过 `alembic -x` / ALEMBIC_DB_URL 指定的目标库。
    # env.py 已把 app/models 下所有模块导入完，这里建的就是全套模型表。
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    pass
