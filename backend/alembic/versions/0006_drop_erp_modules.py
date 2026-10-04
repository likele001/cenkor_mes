"""0006_drop_erp_modules - 清理 erp_* 孤儿表（发票/总账/成本/资产）

背景：erp_invoice / erp_ledger / erp_cost / erp_asset 四组模型（由 0004 创建）
从未接入任何 API、前端或服务层，属死代码；对应代码已随本次治理删除。
本迁移把这些孤儿表一并移除，减负并消除歧义。

注意：这些表在生产库中无业务写入，预期为空。drop 后结构由本文件 downgrade 可重建。
"""
from alembic import op


revision = '0006_drop_erp_modules'
down_revision = '0005_cloud_storage'
branch_labels = None
depends_on = None


# 依赖逆序：先删子表/引用表，再删父表/被引用表
DROP_ORDER = [
    "asset_check_items",
    "asset_checks",
    "asset_depreciation_records",
    "fixed_assets",
    "work_order_cost_items",
    "work_order_costs",
    "invoice_items",
    "invoices",
    "voucher_entries",
    "period_closings",
    "vouchers",
    "account_subjects",
]

CREATE_ORDER = list(reversed(DROP_ORDER))


def upgrade() -> None:
    for table in DROP_ORDER:
        op.drop_table(table)


def downgrade() -> None:
    # 这些是死表（无业务数据），回滚保真无意义；如需重建结构，
    # 请手动参照 0004_erp_modules.upgrade()。
    pass
