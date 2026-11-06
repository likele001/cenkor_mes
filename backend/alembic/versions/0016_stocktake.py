"""0016_stocktake - 库存盘点单

在此之前，账实差异只能靠 `POST /stocks/adjust` 直接改库存数字：没有单据、
没有快照、没有"谁盘的、盘了多少、差异去哪了"。本版本补上盘点单与盘点明细两张表。

两张表都是新建（存量库、新库都缺），所以这里**必须幂等**：
0001 走的是 `Base.metadata.create_all`，新库在 0001 就把这两张表建好了，
到这一步 `insp.has_table` 会命中并跳过；存量库则在这里真正建表。

DDL 取模型元数据，避免同一张表有两份定义各改各的。
"""
from alembic import op
import sqlalchemy as sa


revision = "0016_stocktake"
down_revision = "0015_upgrade_jobs"
branch_labels = None
depends_on = None

# 父表在前：stocktake_items 有指向 stocktakes 的外键
_TABLES = ["stocktakes", "stocktake_items"]


def upgrade() -> None:
    from app.models.base import Base

    import app.models.warehouse  # noqa: F401  确保 warehouses 等被引用的表在 metadata 里
    import app.models.stocktake  # noqa: F401

    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in _TABLES:
        table = Base.metadata.tables.get(name)
        if table is None or insp.has_table(name):
            continue
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in reversed(_TABLES):
        if insp.has_table(name):
            op.drop_table(name)
