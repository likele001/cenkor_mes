"""0005_cloud_storage - 云存储配置表 + 迁移任务表

Revision ID: 0005_cloud_storage
Revises: 0004_erp_modules
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_cloud_storage"
down_revision = "0004_erp_modules"
branch_labels = None
depends_on = None

_TABLES = ("cloud_storage_config", "cloud_storage_migration_jobs")


def _has_table(conn, name: str) -> bool:
    # sa.inspect 而非 information_schema：迁移链要能在临时 SQLite 上验证「从零建库」
    return sa.inspect(conn).has_table(name)


def upgrade() -> None:
    conn = op.get_bind()

    # 这两张表同时也是模型表，0001 的 create_all 在空库上已经建好了；
    # 老库里则由本版本补建。守卫让两种来源都只有一份 DDL 生效。
    if not _has_table(conn, "cloud_storage_config"):
        op.create_table(
            "cloud_storage_config",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("active_provider", sa.String(20), nullable=False, server_default="local"),
            sa.Column("creds_local", sa.Text, nullable=True),
            sa.Column("creds_aliyun", sa.Text, nullable=True),
            sa.Column("creds_tencent", sa.Text, nullable=True),
            sa.Column("creds_qiniu", sa.Text, nullable=True),
            sa.Column("creds_upyun", sa.Text, nullable=True),
            sa.Column("keep_local_backup", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("updated_by", sa.Integer, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table(conn, "cloud_storage_migration_jobs"):
        op.create_table(
            "cloud_storage_migration_jobs",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("source", sa.String(20), nullable=False, server_default="local"),
            sa.Column("target", sa.String(20), nullable=False),
            sa.Column("total", sa.Integer, nullable=False, server_default="0"),
            sa.Column("done", sa.Integer, nullable=False, server_default="0"),
            sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("error", sa.Text, nullable=True),
            sa.Column("started_at", sa.DateTime, nullable=True),
            sa.Column("finished_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_table(table, if_exists=True)
