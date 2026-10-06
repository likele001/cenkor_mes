"""0007_ar_ap_settlement - AR/AP 账龄与部分核销

对账单（statements/supplier_statements）新增到期日 due_date 与已核销金额 paid_amount；
新增核销流水表 statement_payments（多态区分应收/应付，逐笔登记收款/付款）。
核销层独立于 FinanceLedger 总账，不影响利润/GL 口径。

这些表/列同时由模型定义，空库上 0001 的 create_all 已按最终形态建好，
所以每条 DDL 都要先查再建——否则「从零跑迁移链」会在第一个模型表上撞重复列。
"""
from alembic import op
import sqlalchemy as sa


revision = '0007_ar_ap_settlement'
down_revision = '0006_drop_erp_modules'
branch_labels = None
depends_on = None

_NEW_COLUMNS = [
    ('statements', 'paid_amount', lambda: sa.Column('paid_amount', sa.Numeric(14, 4), nullable=False, server_default='0')),
    ('statements', 'due_date', lambda: sa.Column('due_date', sa.Date(), nullable=True)),
    ('supplier_statements', 'paid_amount', lambda: sa.Column('paid_amount', sa.Numeric(14, 4), nullable=False, server_default='0')),
    ('supplier_statements', 'due_date', lambda: sa.Column('due_date', sa.Date(), nullable=True)),
]

_PAYMENT_INDEXES = [
    ('ix_statement_payments_statement_type', ['statement_type']),
    ('ix_statement_payments_statement_id', ['statement_id']),
    ('ix_statement_payments_party_type', ['party_type']),
    ('ix_statement_payments_party_id', ['party_id']),
    ('ix_statement_payments_paid_date', ['paid_date']),
    ('ix_statement_payments_created_by', ['created_by']),
]


def _has_table(conn, name: str) -> bool:
    return sa.inspect(conn).has_table(name)


def _has_column(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_index(conn, table: str, index: str) -> bool:
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return False
    return any(ix["name"] == index for ix in insp.get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()

    # 应收（客户对账单）+ 应付（供应商对账单）
    for table, column, make in _NEW_COLUMNS:
        if not _has_table(conn, table) or _has_column(conn, table, column):
            continue
        op.add_column(table, make())
        if column == "due_date" and not _has_index(conn, table, f"ix_{table}_due_date"):
            op.create_index(f"ix_{table}_due_date", table, ["due_date"])

    # 核销流水
    if not _has_table(conn, 'statement_payments'):
        op.create_table(
            'statement_payments',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('statement_type', sa.String(32), nullable=False),
            sa.Column('statement_id', sa.Integer, nullable=False),
            sa.Column('party_type', sa.String(16), nullable=False),
            sa.Column('party_id', sa.Integer, nullable=False),
            sa.Column('amount', sa.Numeric(14, 4), nullable=False),
            sa.Column('paid_date', sa.Date(), nullable=False),
            sa.Column('method', sa.String(32), nullable=True),
            sa.Column('remark', sa.String(500), nullable=True),
            sa.Column('created_by', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        for index, columns in _PAYMENT_INDEXES:
            op.create_index(index, 'statement_payments', columns)
    else:
        for index, columns in _PAYMENT_INDEXES:
            if not _has_index(conn, 'statement_payments', index):
                op.create_index(index, 'statement_payments', columns)


def downgrade() -> None:
    op.drop_table('statement_payments', if_exists=True)  # 连带删除其索引
    for table in ('supplier_statements', 'statements'):
        op.drop_index(f'ix_{table}_due_date', table_name=table)
        for column in ('due_date', 'paid_amount'):
            if _has_column(op.get_bind(), table, column):
                op.drop_column(table, column)
