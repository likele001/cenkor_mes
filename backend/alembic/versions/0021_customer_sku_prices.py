# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""0021_customer_sku_prices - 客户型号级价目

新建 `customer_sku_prices`，把客户定价从「产品级」细化到「型号级」：
同一产品下不同颜色/尺寸/规格可以各自定价，产品级价目继续作为兜底。

定价优先级：型号级（`price > 0`）> 产品级；型号级的 `min_qty` / `currency`
为 NULL 时逐字段继承产品级 —— 这样只改型号单价不会顺手把起订量重置成 1。

幂等说明：新库走 0001 的 `Base.metadata.create_all` 已按最新模型建好该表，
这里先 `has_table` 判断再建；存量库补建表，不触碰任何现有数据。
"""
from alembic import op
import sqlalchemy as sa


revision = "0021_customer_sku_prices"
down_revision = "0020_customer_product_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("customer_sku_prices"):
        return
    op.create_table(
        "customer_sku_prices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sku_id",
            sa.Integer(),
            sa.ForeignKey("skus.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("min_qty", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("customer_id", "sku_id", name="uq_customer_sku_prices_customer_sku"),
    )
    op.create_index("ix_customer_sku_prices_customer_id", "customer_sku_prices", ["customer_id"])
    op.create_index("ix_customer_sku_prices_sku_id", "customer_sku_prices", ["sku_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("customer_sku_prices"):
        return
    op.drop_index("ix_customer_sku_prices_sku_id", table_name="customer_sku_prices")
    op.drop_index("ix_customer_sku_prices_customer_id", table_name="customer_sku_prices")
    op.drop_table("customer_sku_prices")
