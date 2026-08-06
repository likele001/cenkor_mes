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
    from app.models import Base
    from app.core.db import engine

    Base.metadata.create_all(bind=engine, checkfirst=True)


def downgrade() -> None:
    pass
