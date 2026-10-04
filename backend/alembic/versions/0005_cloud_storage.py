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


def upgrade() -> None:
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
    op.drop_table("cloud_storage_migration_jobs")
    op.drop_table("cloud_storage_config")
