"""work order finished goods entry

完工入库：仓库加成品仓标记，入库单加工单来源，明细允许不带物料主档。

Revision ID: 0027_work_order_entry
Revises: 0026_statement_shipment
"""

import sqlalchemy as sa
from alembic import op

revision = "0027_work_order_entry"
down_revision = "0026_statement_shipment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite 仅用于测试：空库由 0001 的 create_all 直接建成最新结构
        return
    insp = sa.inspect(bind)

    wh_cols = {c["name"] for c in insp.get_columns("warehouses")}
    if "is_finished" not in wh_cols:
        op.add_column(
            "warehouses",
            sa.Column("is_finished", sa.Boolean(), nullable=False, server_default="0"),
        )

    entry_cols = {c["name"]: c for c in insp.get_columns("warehouse_entries")}
    if "work_order_id" not in entry_cols:
        op.add_column("warehouse_entries", sa.Column("work_order_id", sa.Integer(), nullable=True))

    entry_indexes = {i["name"] for i in insp.get_indexes("warehouse_entries")}
    if "ix_warehouse_entries_work_order_id" not in entry_indexes:
        op.create_index(
            "ix_warehouse_entries_work_order_id",
            "warehouse_entries",
            ["work_order_id"],
            unique=False,
        )

    entry_fks = {f["name"] for f in insp.get_foreign_keys("warehouse_entries") if f.get("name")}
    if "fk_warehouse_entries_work_order_id" not in entry_fks:
        op.create_foreign_key(
            "fk_warehouse_entries_work_order_id",
            "warehouse_entries",
            "work_orders",
            ["work_order_id"],
            ["id"],
            ondelete="SET NULL",
        )

    item_cols = {c["name"]: c for c in insp.get_columns("warehouse_entry_items")}
    if not item_cols.get("material_id", {}).get("nullable", True):
        op.alter_column(
            "warehouse_entry_items", "material_id",
            existing_type=sa.Integer(), nullable=True,
        )

    # 回填成品仓：老库靠编码/名称约定识别，避免升级后第一张完工入库单无处可落
    op.execute(
        "UPDATE warehouses SET is_finished = 1 "
        "WHERE (code = 'WH-FIN' OR name LIKE '%成品%') AND is_finished = 0"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    insp = sa.inspect(bind)

    entry_fks = {f["name"] for f in insp.get_foreign_keys("warehouse_entries") if f.get("name")}
    if "fk_warehouse_entries_work_order_id" in entry_fks:
        op.drop_constraint("fk_warehouse_entries_work_order_id", "warehouse_entries", type_="foreignkey")
    entry_indexes = {i["name"] for i in insp.get_indexes("warehouse_entries")}
    if "ix_warehouse_entries_work_order_id" in entry_indexes:
        op.drop_index("ix_warehouse_entries_work_order_id", table_name="warehouse_entries")
    entry_cols = {c["name"] for c in insp.get_columns("warehouse_entries")}
    if "work_order_id" in entry_cols:
        op.drop_column("warehouse_entries", "work_order_id")

    wh_cols = {c["name"] for c in insp.get_columns("warehouses")}
    if "is_finished" in wh_cols:
        op.drop_column("warehouses", "is_finished")
