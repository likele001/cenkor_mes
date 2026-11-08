# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""0020_customer_product_pricing - 客户可下单产品价目

给 `customer_products` 加 price / min_qty / currency 三列，让 H5 客户下单
能写入真实的单价、小计与订单金额（此前 orders.amount 恒为 0）。

幂等说明：新库走 0001 的 `Base.metadata.create_all` 已按最新模型建好三列，
存量库在这里补；加列前逐列查 information_schema，重复执行不会报 Duplicate column。
默认值选择：price=0 表示「尚未定价」（下单会被拒绝，不生成 0 元订单），
min_qty=1、currency=CNY 保证存量配置行为不变。
"""
from alembic import op
import sqlalchemy as sa


revision = "0020_customer_product_pricing"
down_revision = "0019_basics"
branch_labels = None
depends_on = None

# (列名, 类型, server_default)
_ADD_COLUMNS = [
    ("price", sa.Numeric(12, 4), "0"),
    ("min_qty", sa.Integer(), "1"),
    ("currency", sa.String(8), "CNY"),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("customer_products"):
        return
    existing = {c["name"] for c in insp.get_columns("customer_products")}
    for col_name, col_type, default in _ADD_COLUMNS:
        if col_name in existing:
            continue
        # 交给 SQLAlchemy 做字面量转义：sa.text("CNY") 会渲染成 DEFAULT CNY（MySQL 语法错）
        op.add_column(
            "customer_products",
            sa.Column(col_name, col_type, nullable=False, server_default=default),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("customer_products"):
        return
    existing = {c["name"] for c in insp.get_columns("customer_products")}
    for col_name, _, _ in reversed(_ADD_COLUMNS):
        if col_name in existing:
            op.drop_column("customer_products", col_name)
