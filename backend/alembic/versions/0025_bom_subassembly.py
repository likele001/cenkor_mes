"""bom sub assembly flag

Revision ID: 0025_bom_subassembly
Revises: 0024_ai_metering
"""

import sqlalchemy as sa
from alembic import op

revision = "0025_bom_subassembly"
down_revision = "0024_ai_metering"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 用 Base.metadata.create_all 建库，新库里该列已存在，这里跳过
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("material_bom_items")}
    if "is_sub_assembly" not in cols:
        op.add_column(
            "material_bom_items",
            sa.Column("is_sub_assembly", sa.Boolean(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("material_bom_items")}
    if "is_sub_assembly" in cols:
        op.drop_column("material_bom_items", "is_sub_assembly")
