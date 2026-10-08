"""0014_platform_ai_config - 平台 AI 配置层三表

波次 0：把 lightmes 平台 AI 配置移植进 cenkormes 核心（单租户，去 tenant_id）。
建 platform_ai_profiles / platform_ai_gateways / platform_ai_models 三表，
作为所有 AI 功能（核心 Pro 路由 + 付费扩展）共用的唯一配置源。

DDL 直接取模型元数据，避免同一张表两份定义各改各的。
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_platform_ai_config"
down_revision = "0013_orphan_model_tables"
branch_labels = None
depends_on = None

_TABLES = [
    "platform_ai_profiles",
    "platform_ai_gateways",
    "platform_ai_models",
]


def upgrade() -> None:
    from app.models.base import Base

    import app.models.ai  # noqa: F401  确保三表注册进 metadata

    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in _TABLES:
        table = Base.metadata.tables.get(name)
        if table is None or insp.has_table(name):
            continue
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in reversed(_TABLES):
        if insp.has_table(name):
            op.drop_table(name)
