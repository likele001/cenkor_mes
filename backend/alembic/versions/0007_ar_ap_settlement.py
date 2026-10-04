"""0007_ar_ap_settlement - AR/AP 账龄与部分核销

对账单（statements/supplier_statements）新增到期日 due_date 与已核销金额 paid_amount；
新增核销流水表 statement_payments（多态区分应收/应付，逐笔登记收款/付款）。
核销层独立于 FinanceLedger 总账，不影响利润/GL 口径。
"""
from alembic import op
import sqlalchemy as sa


revision = '0007_ar_ap_settlement'
down_revision = '0006_drop_erp_modules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 应收（客户对账单）
    op.add_column('statements', sa.Column('paid_amount', sa.Numeric(14, 4), nullable=False, server_default='0'))
    op.add_column('statements', sa.Column('due_date', sa.Date(), nullable=True))
    op.create_index('ix_statements_due_date', 'statements', ['due_date'])

    # 应付（供应商对账单）
    op.add_column('supplier_statements', sa.Column('paid_amount', sa.Numeric(14, 4), nullable=False, server_default='0'))
    op.add_column('supplier_statements', sa.Column('due_date', sa.Date(), nullable=True))
    op.create_index('ix_supplier_statements_due_date', 'supplier_statements', ['due_date'])

    # 核销流水
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
    op.create_index('ix_statement_payments_statement_type', 'statement_payments', ['statement_type'])
    op.create_index('ix_statement_payments_statement_id', 'statement_payments', ['statement_id'])
    op.create_index('ix_statement_payments_party_type', 'statement_payments', ['party_type'])
    op.create_index('ix_statement_payments_party_id', 'statement_payments', ['party_id'])
    op.create_index('ix_statement_payments_paid_date', 'statement_payments', ['paid_date'])
    op.create_index('ix_statement_payments_created_by', 'statement_payments', ['created_by'])


def downgrade() -> None:
    op.drop_table('statement_payments')  # 连带删除其索引
    op.drop_index('ix_supplier_statements_due_date', table_name='supplier_statements')
    op.drop_column('supplier_statements', 'due_date')
    op.drop_column('supplier_statements', 'paid_amount')
    op.drop_index('ix_statements_due_date', table_name='statements')
    op.drop_column('statements', 'due_date')
    op.drop_column('statements', 'paid_amount')
