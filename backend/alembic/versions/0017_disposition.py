"""0017_disposition - 不良品处置单

在此之前的缺口：报工只记了不良多少件（`reports.bad_qty`），不良品去哪了没有记录。
本版本补上 `dispositions`（表头）与 `disposition_items`（明细）两张表。

两张表都是新建（存量库、新库都缺），所以这里**必须幂等**：
0001 走 `Base.metadata.create_all`，新库到这一步 `insp.has_table` 会命中并跳过；
存量库则在这里真正建表。DDL 一律取模型元数据，避免同一张表两份定义各改各的。

注意表里没有指向库存的外键，也没有任何回写 `reports.good_qty` 的触发器——处置单只记
「决定 + 损失金额」，实物报废出库走仓储出库单，报工是既成事实不改写。
"""
from alembic import op
import sqlalchemy as sa


revision = "0017_disposition"
down_revision = "0016_stocktake"
branch_labels = None
depends_on = None

# 父表在前：disposition_items 有指向 dispositions 的外键
_TABLES = ["dispositions", "disposition_items"]


def upgrade() -> None:
    from app.models.base import Base

    # 整包导入，确保 reports/tasks/work_orders/skus/processes/defect_codes
    # 这些被外键引用的表都在 metadata 里，否则 DDL 编译时报 NoReferencedTableError
    import app.models  # noqa: F401
    import app.models.disposition  # noqa: F401

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
