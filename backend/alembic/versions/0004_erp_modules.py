"""0004_erp_modules - ERP 四模块（发票/总账/成本/资产）

与 lightmes 0070_erp_modules 同构，独立迁移链（cenkormes）。
"""
from alembic import op
import sqlalchemy as sa


revision = '0004_erp_modules'
down_revision = '0003_material_issue_warehouse_entry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============ 财务总账 ============
    op.create_table(
        "account_subjects",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False, server_default="debit"),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("account_subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_account_subjects_tenant_code"),
    )
    op.create_index("ix_account_subjects_tenant_id", "account_subjects", ["tenant_id"])
    op.create_index("ix_account_subjects_subject_type", "account_subjects", ["subject_type"])

    op.create_table(
        "vouchers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("voucher_date", sa.Date, nullable=False),
        sa.Column("voucher_type", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("source_id", sa.Integer, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("posted_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("posted_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_vouchers_tenant_code"),
    )
    op.create_index("ix_vouchers_tenant_id", "vouchers", ["tenant_id"])
    op.create_index("ix_vouchers_voucher_date", "vouchers", ["voucher_date"])
    op.create_index("ix_vouchers_period", "vouchers", ["period"])
    op.create_index("ix_vouchers_status", "vouchers", ["status"])

    op.create_table(
        "voucher_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voucher_id", sa.Integer, sa.ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer, nullable=False, server_default="1"),
        sa.Column("account_subject_id", sa.Integer, sa.ForeignKey("account_subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("debit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("party_type", sa.String(16), nullable=True),
        sa.Column("party_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_voucher_entries_tenant_id", "voucher_entries", ["tenant_id"])
    op.create_index("ix_voucher_entries_voucher_id", "voucher_entries", ["voucher_id"])
    op.create_index("ix_voucher_entries_account_subject_id", "voucher_entries", ["account_subject_id"])
    op.create_index("ix_voucher_entries_party_id", "voucher_entries", ["party_id"])

    op.create_table(
        "period_closings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("closed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("closed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "period", name="uq_period_closings_tenant_period"),
    )
    op.create_index("ix_period_closings_tenant_id", "period_closings", ["tenant_id"])

    # ============ 发票 ============
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("invoice_no", sa.String(64), nullable=True),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("invoice_type", sa.String(16), nullable=False, server_default="special"),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("statement_id", sa.Integer, sa.ForeignKey("statements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("supplier_statement_id", sa.Integer, sa.ForeignKey("supplier_statements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("purchase_order_id", sa.Integer, sa.ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("tax_rate", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_invoices_tenant_code"),
    )
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])
    op.create_index("ix_invoices_direction", "invoices", ["direction"])
    op.create_index("ix_invoices_invoice_type", "invoices", ["invoice_type"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_supplier_id", "invoices", ["supplier_id"])
    op.create_index("ix_invoices_statement_id", "invoices", ["statement_id"])
    op.create_index("ix_invoices_supplier_statement_id", "invoices", ["supplier_statement_id"])
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"])
    op.create_index("ix_invoices_purchase_order_id", "invoices", ["purchase_order_id"])
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer, nullable=False, server_default="1"),
        sa.Column("order_id", sa.Integer, nullable=True),
        sa.Column("purchase_order_id", sa.Integer, nullable=True),
        sa.Column("sku_id", sa.Integer, sa.ForeignKey("skus.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("material_id", sa.Integer, sa.ForeignKey("materials.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("qty", sa.Numeric(14, 4), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_invoice_items_tenant_id", "invoice_items", ["tenant_id"])
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    # ============ 工单成本 ============
    op.create_table(
        "work_order_costs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_order_id", sa.Integer, sa.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sku_id", sa.Integer, sa.ForeignKey("skus.id", ondelete="SET NULL"), nullable=True),
        sa.Column("qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("material_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("labor_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("overhead_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("quote_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gross_profit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gross_margin", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("computed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "work_order_id", name="uq_work_order_costs_tenant_wo"),
    )
    op.create_index("ix_work_order_costs_tenant_id", "work_order_costs", ["tenant_id"])
    op.create_index("ix_work_order_costs_work_order_id", "work_order_costs", ["work_order_id"])
    op.create_index("ix_work_order_costs_order_id", "work_order_costs", ["order_id"])
    op.create_index("ix_work_order_costs_status", "work_order_costs", ["status"])

    op.create_table(
        "work_order_cost_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cost_id", sa.Integer, sa.ForeignKey("work_order_costs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cost_type", sa.String(16), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_id", sa.Integer, nullable=True),
        sa.Column("ref_code", sa.String(64), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_work_order_cost_items_tenant_id", "work_order_cost_items", ["tenant_id"])
    op.create_index("ix_work_order_cost_items_cost_id", "work_order_cost_items", ["cost_id"])
    op.create_index("ix_work_order_cost_items_cost_type", "work_order_cost_items", ["cost_type"])
    op.create_index("ix_work_order_cost_items_source_type", "work_order_cost_items", ["source_type"])
    op.create_index("ix_work_order_cost_items_source_id", "work_order_cost_items", ["source_id"])

    # ============ 固定资产 ============
    op.create_table(
        "fixed_assets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_no", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("equipment_id", sa.Integer, sa.ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workshop", sa.String(64), nullable=True),
        sa.Column("department_id", sa.Integer, sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("original_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("residual_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("useful_life_months", sa.Integer, nullable=False, server_default="0"),
        sa.Column("depreciation_method", sa.String(16), nullable=False, server_default="straight_line"),
        sa.Column("monthly_depreciation", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("start_use_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("accumulated_depreciation", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("book_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "asset_no", name="uq_fixed_assets_tenant_asset_no"),
    )
    op.create_index("ix_fixed_assets_tenant_id", "fixed_assets", ["tenant_id"])
    op.create_index("ix_fixed_assets_category", "fixed_assets", ["category"])
    op.create_index("ix_fixed_assets_equipment_id", "fixed_assets", ["equipment_id"])
    op.create_index("ix_fixed_assets_status", "fixed_assets", ["status"])

    op.create_table(
        "asset_depreciation_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("depreciation_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("accumulated_depreciation", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("book_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "asset_id", "period", name="uq_asset_depr_tenant_asset_period"),
    )
    op.create_index("ix_asset_depreciation_records_tenant_id", "asset_depreciation_records", ["tenant_id"])
    op.create_index("ix_asset_depreciation_records_asset_id", "asset_depreciation_records", ["asset_id"])
    op.create_index("ix_asset_depreciation_records_period", "asset_depreciation_records", ["period"])

    op.create_table(
        "asset_checks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_no", sa.String(32), nullable=False),
        sa.Column("check_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "check_no", name="uq_asset_checks_tenant_check_no"),
    )
    op.create_index("ix_asset_checks_tenant_id", "asset_checks", ["tenant_id"])
    op.create_index("ix_asset_checks_check_date", "asset_checks", ["check_date"])
    op.create_index("ix_asset_checks_status", "asset_checks", ["status"])

    op.create_table(
        "asset_check_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_id", sa.Integer, sa.ForeignKey("asset_checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("fixed_assets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expected_qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("checked_qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("diff_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_asset_check_items_tenant_id", "asset_check_items", ["tenant_id"])
    op.create_index("ix_asset_check_items_check_id", "asset_check_items", ["check_id"])
    op.create_index("ix_asset_check_items_asset_id", "asset_check_items", ["asset_id"])
    op.create_index("ix_asset_check_items_status", "asset_check_items", ["status"])


def downgrade() -> None:
    op.drop_table("asset_check_items")
    op.drop_table("asset_checks")
    op.drop_table("asset_depreciation_records")
    op.drop_table("fixed_assets")
    op.drop_table("work_order_cost_items")
    op.drop_table("work_order_costs")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("period_closings")
    op.drop_table("voucher_entries")
    op.drop_table("vouchers")
    op.drop_table("account_subjects")
