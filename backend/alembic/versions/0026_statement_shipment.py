"""statement item shipment source

Revision ID: 0026_statement_shipment
Revises: 0025_bom_subassembly
"""

import sqlalchemy as sa
from alembic import op

revision = "0026_statement_shipment"
down_revision = "0025_bom_subassembly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 的 create_all 在空库上已包含新列/约束，逐项跳过即可重复执行
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite 仅用于测试：空库由 0001 的 create_all 直接建成最新结构
        return
    insp = sa.inspect(bind)
    cols = {c["name"]: c for c in insp.get_columns("statement_items")}
    if "source_type" not in cols:
        op.add_column(
            "statement_items",
            sa.Column("source_type", sa.String(length=16), nullable=False, server_default="order"),
        )
    if "shipment_id" not in cols:
        op.add_column("statement_items", sa.Column("shipment_id", sa.Integer(), nullable=True))
    if not cols.get("order_id", {}).get("nullable", True):
        op.alter_column("statement_items", "order_id", existing_type=sa.Integer(), nullable=True)

    indexes = {i["name"] for i in insp.get_indexes("statement_items")}
    if "ix_statement_items_shipment_id" not in indexes:
        op.create_index(
            "ix_statement_items_shipment_id", "statement_items", ["shipment_id"], unique=False
        )

    fks = {f["name"] for f in insp.get_foreign_keys("statement_items") if f.get("name")}
    if "fk_statement_items_shipment_id" not in fks:
        op.create_foreign_key(
            "fk_statement_items_shipment_id",
            "statement_items",
            "shipments",
            ["shipment_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    uniques = {u["name"] for u in insp.get_unique_constraints("statement_items")}
    if "uq_statement_items_stmt_shipment" not in uniques:
        op.create_unique_constraint(
            "uq_statement_items_stmt_shipment",
            "statement_items",
            ["statement_id", "shipment_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    uniques = {u["name"] for u in insp.get_unique_constraints("statement_items")}
    if "uq_statement_items_stmt_shipment" in uniques:
        op.drop_constraint("uq_statement_items_stmt_shipment", "statement_items", type_="unique")
    fks = {f["name"] for f in insp.get_foreign_keys("statement_items") if f.get("name")}
    if "fk_statement_items_shipment_id" in fks:
        op.drop_constraint("fk_statement_items_shipment_id", "statement_items", type_="foreignkey")
    indexes = {i["name"] for i in insp.get_indexes("statement_items")}
    if "ix_statement_items_shipment_id" in indexes:
        op.drop_index("ix_statement_items_shipment_id", table_name="statement_items")
    cols = {c["name"] for c in insp.get_columns("statement_items")}
    if "shipment_id" in cols:
        op.drop_column("statement_items", "shipment_id")
    if "source_type" in cols:
        op.drop_column("statement_items", "source_type")
