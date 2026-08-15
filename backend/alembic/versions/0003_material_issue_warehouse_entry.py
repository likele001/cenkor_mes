"""0003_material_issue_warehouse_entry - 领料/退料/入库单（Phase2+Phase4 补迁移）

Phase 2（领料/退料+库存成本）与 Phase 4（入库单独立单据化）的表
最初由 Base.metadata.create_all 自动创建，现补入正式 alembic 迁移链，
对已有库幂等（checkfirst=True），不动数据。

Revision ID: 0003_material_issue_warehouse_entry
Revises: 0002_mrp_subcontract
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_material_issue_warehouse_entry"
down_revision = "0002_mrp_subcontract"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
    ), {"t": table_name})
    return result.scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()

    # === Phase 2: 领料单 ===
    if not _table_exists(conn, "material_issues"):
        op.create_table(
            "material_issues",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("warehouse_id", sa.Integer(), nullable=False),
            sa.Column("work_order_id", sa.Integer(), nullable=True),
            sa.Column("issue_by", sa.Integer(), nullable=True),
            sa.Column("issued_at", sa.DateTime(), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["issue_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("code", name="uq_material_issues_code"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_material_issues_status", "material_issues", ["status"])
        op.create_index("ix_material_issues_warehouse_id", "material_issues", ["warehouse_id"])
        op.create_index("ix_material_issues_work_order_id", "material_issues", ["work_order_id"])
        op.create_index("ix_material_issues_issue_by", "material_issues", ["issue_by"])
        op.create_index("ix_material_issues_created_by", "material_issues", ["created_by"])

    if not _table_exists(conn, "material_issue_items"):
        op.create_table(
            "material_issue_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("issue_id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("sku_id", sa.Integer(), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"),
            sa.Column("cost_amount", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["issue_id"], ["material_issues.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_material_issue_items_issue_id", "material_issue_items", ["issue_id"])
        op.create_index("ix_material_issue_items_material_id", "material_issue_items", ["material_id"])
        op.create_index("ix_material_issue_items_sku_id", "material_issue_items", ["sku_id"])

    # === Phase 2: 退料单 ===
    if not _table_exists(conn, "material_returns"):
        op.create_table(
            "material_returns",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("warehouse_id", sa.Integer(), nullable=False),
            sa.Column("work_order_id", sa.Integer(), nullable=True),
            sa.Column("issue_id", sa.Integer(), nullable=True),
            sa.Column("return_by", sa.Integer(), nullable=True),
            sa.Column("returned_at", sa.DateTime(), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["issue_id"], ["material_issues.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["return_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("code", name="uq_material_returns_code"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_material_returns_status", "material_returns", ["status"])
        op.create_index("ix_material_returns_warehouse_id", "material_returns", ["warehouse_id"])
        op.create_index("ix_material_returns_work_order_id", "material_returns", ["work_order_id"])
        op.create_index("ix_material_returns_issue_id", "material_returns", ["issue_id"])
        op.create_index("ix_material_returns_return_by", "material_returns", ["return_by"])
        op.create_index("ix_material_returns_created_by", "material_returns", ["created_by"])

    if not _table_exists(conn, "material_return_items"):
        op.create_table(
            "material_return_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("return_id", sa.Integer(), nullable=False),
            sa.Column("issue_item_id", sa.Integer(), nullable=True),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("sku_id", sa.Integer(), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"),
            sa.Column("cost_amount", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["return_id"], ["material_returns.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["issue_item_id"], ["material_issue_items.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_material_return_items_return_id", "material_return_items", ["return_id"])
        op.create_index("ix_material_return_items_issue_item_id", "material_return_items", ["issue_item_id"])
        op.create_index("ix_material_return_items_material_id", "material_return_items", ["material_id"])
        op.create_index("ix_material_return_items_sku_id", "material_return_items", ["sku_id"])

    # === Phase 4: 入库单 ===
    if not _table_exists(conn, "warehouse_entries"):
        op.create_table(
            "warehouse_entries",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
            sa.Column("source_type", sa.String(length=32), nullable=False, server_default="other"),
            sa.Column("warehouse_id", sa.Integer(), nullable=False),
            sa.Column("purchase_order_id", sa.Integer(), nullable=True),
            sa.Column("material_return_id", sa.Integer(), nullable=True),
            sa.Column("total_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_cost", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("confirmed_by", sa.Integer(), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["material_return_id"], ["material_returns.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("code", name="uq_warehouse_entries_code"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_warehouse_entries_status", "warehouse_entries", ["status"])
        op.create_index("ix_warehouse_entries_warehouse_id", "warehouse_entries", ["warehouse_id"])
        op.create_index("ix_warehouse_entries_purchase_order_id", "warehouse_entries", ["purchase_order_id"])
        op.create_index("ix_warehouse_entries_material_return_id", "warehouse_entries", ["material_return_id"])

    if not _table_exists(conn, "warehouse_entry_items"):
        op.create_table(
            "warehouse_entry_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("sku_id", sa.Integer(), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(precision=14, scale=4), nullable=False, server_default="0"),
            sa.Column("cost_amount", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["entry_id"], ["warehouse_entries.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_warehouse_entry_items_entry_id", "warehouse_entry_items", ["entry_id"])
        op.create_index("ix_warehouse_entry_items_material_id", "warehouse_entry_items", ["material_id"])
        op.create_index("ix_warehouse_entry_items_sku_id", "warehouse_entry_items", ["sku_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "warehouse_entry_items"):
        op.drop_table("warehouse_entry_items")
    if _table_exists(conn, "warehouse_entries"):
        op.drop_table("warehouse_entries")
    if _table_exists(conn, "material_return_items"):
        op.drop_table("material_return_items")
    if _table_exists(conn, "material_returns"):
        op.drop_table("material_returns")
    if _table_exists(conn, "material_issue_items"):
        op.drop_table("material_issue_items")
    if _table_exists(conn, "material_issues"):
        op.drop_table("material_issues")
