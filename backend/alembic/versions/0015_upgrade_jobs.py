"""0015_upgrade_jobs - 后台在线升级 / 回滚任务表

建 upgrade_jobs 表，记录每次升级（upgrade）或回滚（rollback）任务的
版本、阶段、备份路径与执行结果，供「关于页」的在线升级面板查询。
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_upgrade_jobs"
down_revision = "0014_platform_ai_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("upgrade_jobs"):
        return

    op.create_table(
        "upgrade_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("from_version", sa.String(length=32), nullable=False),
        sa.Column("to_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("stage", sa.String(length=24), nullable=False, server_default="backup"),
        sa.Column("from_ref", sa.String(length=64), nullable=True),
        sa.Column("alembic_rev", sa.String(length=64), nullable=True),
        sa.Column("backup_path", sa.String(length=255), nullable=True),
        sa.Column("log_path", sa.String(length=255), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_upgrade_jobs_status", "upgrade_jobs", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("upgrade_jobs"):
        op.drop_index("ix_upgrade_jobs_status", table_name="upgrade_jobs")
        op.drop_table("upgrade_jobs")
