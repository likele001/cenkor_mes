"""0010_approval_records - 通用审批/状态变更留痕

订单、采购、入库、对账、工资条此前的审核结果只写在 confirmed_by/confirmed_at 这类
列上，改一次覆盖一次，驳回历史无痕。新增只追加的 approval_records。
表可能已由 create_all 建立，故先判存在。
"""
from alembic import op
import sqlalchemy as sa


revision = '0010_approval_records'
down_revision = '0009_salary_payment'
branch_labels = None
depends_on = None

_TABLE = "approval_records"
_INDEXES = [
    ("ix_approval_records_biz", ["biz_type", "biz_id", "id"]),
    ("ix_approval_records_operator_id", ["operator_id"]),
    ("ix_approval_records_created_at", ["created_at"]),
]


def _table_exists(conn, table_name: str) -> bool:
    # sa.inspect 而非 information_schema：迁移链要能在临时 SQLite 上验证「从零建库」
    return sa.inspect(conn).has_table(table_name)


def _index_exists(conn, table: str, index: str) -> bool:
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return False
    return any(ix["name"] == index for ix in insp.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("biz_type", sa.String(length=32), nullable=False),
        sa.Column("biz_id", sa.Integer(), nullable=False),
        sa.Column("biz_code", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("operator_name", sa.String(length=64), nullable=True),
        sa.Column("channel", sa.String(length=16), server_default="web", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], name="fk_approval_records_operator", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for index_name, columns in _INDEXES:
        if not _index_exists(conn, _TABLE, index_name):
            op.create_index(index_name, _TABLE, columns)


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, _TABLE):
        return
    for index_name, _columns in reversed(_INDEXES):
        if _index_exists(conn, _TABLE, index_name):
            op.drop_index(index_name, table_name=_TABLE)
    op.drop_table(_TABLE)
