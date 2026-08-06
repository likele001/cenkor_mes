"""0002_add_mrp_subcontract - MRP 物料需求计划 + 外协工序管理

Revision ID: 0002_mrp_subcontract
Revises: 0001_init
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_mrp_subcontract"
down_revision = "0001_init"
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

    # === MRP 物料需求计划 ===

    if not _table_exists(conn, "mrp_plans"):
        op.create_table(
            "mrp_plans",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="computed"),
            sa.Column("source_type", sa.String(length=32), nullable=False, server_default="work_order"),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("total_skus", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_materials", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_purchase_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("code", name="uq_mrp_plans_code"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_mrp_plans_status", "mrp_plans", ["status"])
        op.create_index("ix_mrp_plans_created_by", "mrp_plans", ["created_by"])

    if not _table_exists(conn, "mrp_items"):
        op.create_table(
            "mrp_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("work_order_id", sa.Integer(), nullable=True),
            sa.Column("order_id", sa.Integer(), nullable=True),
            sa.Column("sku_id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("bom_id", sa.Integer(), nullable=True),
            sa.Column("bom_scope", sa.String(length=16), nullable=True),
            sa.Column("wo_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("qty_per", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("gross_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("stock_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("net_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("suggested_purchase_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("supplier_id", sa.Integer(), nullable=True),
            sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.ForeignKeyConstraint(["plan_id"], ["mrp_plans.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["bom_id"], ["material_boms.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_mrp_items_plan_id", "mrp_items", ["plan_id"])
        op.create_index("ix_mrp_items_work_order_id", "mrp_items", ["work_order_id"])
        op.create_index("ix_mrp_items_order_id", "mrp_items", ["order_id"])
        op.create_index("ix_mrp_items_sku_id", "mrp_items", ["sku_id"])
        op.create_index("ix_mrp_items_material_id", "mrp_items", ["material_id"])
        op.create_index("ix_mrp_items_supplier_id", "mrp_items", ["supplier_id"])

    # === 外协工序管理 ===

    if not _table_exists(conn, "subcontract_orders"):
        op.create_table(
            "subcontract_orders",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("supplier_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_subcontract_orders_supplier_id", "subcontract_orders", ["supplier_id"])
        op.create_index("ix_subcontract_orders_created_by", "subcontract_orders", ["created_by"])

    if not _table_exists(conn, "subcontract_order_items"):
        op.create_table(
            "subcontract_order_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("sku_id", sa.Integer(), nullable=False),
            sa.Column("process_id", sa.Integer(), nullable=True),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("sent_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("received_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["order_id"], ["subcontract_orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["process_id"], ["processes.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_subcontract_order_items_order_id", "subcontract_order_items", ["order_id"])
        op.create_index("ix_subcontract_order_items_sku_id", "subcontract_order_items", ["sku_id"])
        op.create_index("ix_subcontract_order_items_process_id", "subcontract_order_items", ["process_id"])

    if not _table_exists(conn, "subcontract_send_logs"):
        op.create_table(
            "subcontract_send_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("sent_by", sa.Integer(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["order_id"], ["subcontract_orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["item_id"], ["subcontract_order_items.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sent_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_subcontract_send_logs_order_id", "subcontract_send_logs", ["order_id"])
        op.create_index("ix_subcontract_send_logs_item_id", "subcontract_send_logs", ["item_id"])

    if not _table_exists(conn, "subcontract_receive_logs"):
        op.create_table(
            "subcontract_receive_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("received_by", sa.Integer(), nullable=True),
            sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["order_id"], ["subcontract_orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["item_id"], ["subcontract_order_items.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["received_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            mysql_collate="utf8mb4_general_ci",
            mysql_default_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index("ix_subcontract_receive_logs_order_id", "subcontract_receive_logs", ["order_id"])
        op.create_index("ix_subcontract_receive_logs_item_id", "subcontract_receive_logs", ["item_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "subcontract_receive_logs"):
        op.drop_table("subcontract_receive_logs")
    if _table_exists(conn, "subcontract_send_logs"):
        op.drop_table("subcontract_send_logs")
    if _table_exists(conn, "subcontract_order_items"):
        op.drop_table("subcontract_order_items")
    if _table_exists(conn, "subcontract_orders"):
        op.drop_table("subcontract_orders")
    if _table_exists(conn, "mrp_items"):
        op.drop_table("mrp_items")
    if _table_exists(conn, "mrp_plans"):
        op.drop_table("mrp_plans")
