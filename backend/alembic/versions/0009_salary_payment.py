"""0009_salary_payment - 工资发放状态

第四批·工资落账：SalarySlip 此前只有员工签收（confirm_status），没有「厂里是否已付钱」
这一层，所以工资从来没进过总账。新增发放四列，历史行一律按 unpaid 处理——没记过发放
就是没记过，不回填成「已发」。

salary_slips 由 create_all 建立，不在本 migration 的建表链里，故逐列判存在再 ALTER。
"""
from alembic import op
import sqlalchemy as sa


revision = '0009_salary_payment'
down_revision = '0008_stock_attribution'
branch_labels = None
depends_on = None

_COLUMNS = [
    ("pay_status", sa.String(length=16), "unpaid", False),
    ("paid_at", sa.DateTime(), None, True),
    ("paid_by", sa.Integer(), None, True),
    ("paid_remark", sa.String(length=255), None, True),
]
_INDEXES = [("ix_salary_slips_pay_status", "pay_status"), ("ix_salary_slips_paid_by", "paid_by")]
_TABLE = "salary_slips"


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
    ), {"t": table, "c": column})
    return result.scalar() > 0


def _index_exists(conn, table: str, index: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND INDEX_NAME = :i"
    ), {"t": table, "i": index})
    return result.scalar() > 0


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
    ), {"t": table_name})
    return result.scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, _TABLE):
        return
    for name, col_type, default, nullable in _COLUMNS:
        if _column_exists(conn, _TABLE, name):
            continue
        op.add_column(_TABLE, sa.Column(name, col_type, nullable=nullable, server_default=default))
    for index_name, column in _INDEXES:
        if _column_exists(conn, _TABLE, column) and not _index_exists(conn, _TABLE, index_name):
            op.create_index(index_name, _TABLE, [column])


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, _TABLE):
        return
    for index_name, _column in reversed(_INDEXES):
        if _index_exists(conn, _TABLE, index_name):
            op.drop_index(index_name, table_name=_TABLE)
    for name, _type, _default, _nullable in reversed(_COLUMNS):
        if _column_exists(conn, _TABLE, name):
            op.drop_column(_TABLE, name)
