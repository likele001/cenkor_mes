# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""0022_customer_price_tiers - 客户阶梯价

新建 `customer_price_tiers`，在「单价」之上加一层「数量折扣」：
同一产品（或同一型号）可以配置多档 `min_qty → price`，下单时按实际
采购数量命中最高满足档，批量越大单价越低。

设计要点：
- `sku_id = 0` 表示产品通用阶梯（所有型号共用），>0 表示型号专属阶梯。
  不用 NULL 是因为 MySQL 唯一索引里 NULL 互不相等，唯一键会失效，
  同一档位可以被重复插入。
- 档位 `min_qty` 是区间起点（含），同一 scope 内最小的那一档就是起订量。
- 阶梯存在时优先于同维度的单一单价：型号专属档 > 型号单价 > 产品通用档
  > 产品单价。

幂等说明：新库走 0001 的 `Base.metadata.create_all` 已按最新模型建好该表，
这里先 `has_table` 判断再建；存量库只补建表，不碰任何现有数据。
"""
import sqlalchemy as sa

from alembic import op

revision = "0022_customer_price_tiers"
down_revision = "0021_customer_sku_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("customer_price_tiers"):
        return
    op.create_table(
        "customer_price_tiers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 0 = 产品通用；正数 = 型号 ID。故意不建外键，0 在 skus 表里不存在
        sa.Column("sku_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_qty", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "customer_id",
            "product_id",
            "sku_id",
            "min_qty",
            name="uq_customer_price_tiers_scope_qty",
        ),
    )
    op.create_index("ix_customer_price_tiers_customer_id", "customer_price_tiers", ["customer_id"])
    op.create_index("ix_customer_price_tiers_product_id", "customer_price_tiers", ["product_id"])
    op.create_index("ix_customer_price_tiers_sku_id", "customer_price_tiers", ["sku_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("customer_price_tiers"):
        return
    op.drop_index("ix_customer_price_tiers_sku_id", table_name="customer_price_tiers")
    op.drop_index("ix_customer_price_tiers_product_id", table_name="customer_price_tiers")
    op.drop_index("ix_customer_price_tiers_customer_id", table_name="customer_price_tiers")
    op.drop_table("customer_price_tiers")
