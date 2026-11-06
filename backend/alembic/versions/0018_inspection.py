"""0018_inspection - 检验单（IQC / IPQC / OQC / FAI）

在此之前的缺口：宿主有检验模板（`inspection_templates`）和逐件检验记录
（`inspection_records`），但**按批次的检验单**从来没有——采购收货直接入库，
整批报工终审只改状态，发货前无检验。

本版本补上 `inspection_orders`（表头）与 `inspection_order_items`（明细）两张表。
四类检验共用一套结构，靠 `inspection_type` 区分。

两张表都是新建（存量库、新库都缺），所以这里**必须幂等**：
0001 走 `Base.metadata.create_all`，新库到这一步 `insp.has_table` 会命中并跳过；
存量库则在这里真正建表。DDL 一律取模型元数据，避免同一张表两份定义各改各的。

注意：
- 明细里的 `standard_value` / `upper_limit` / `lower_limit` / `unit` / `is_required`
  是建单时从模板复制来的**快照**，模板日后改动不影响历史判定。
- 表里没有指向库存的外键，也不回写来源单据状态——检验单只出判定，实物出入库走仓储单据。
"""
from alembic import op
import sqlalchemy as sa


revision = "0018_inspection"
down_revision = "0017_disposition"
branch_labels = None
depends_on = None

# 父表在前：inspection_order_items 有指向 inspection_orders 的外键
_TABLES = ["inspection_orders", "inspection_order_items"]


def upgrade() -> None:
    from app.models.base import Base

    # 整包导入，确保 materials/skus/suppliers/customers/users/defect_codes/
    # inspection_templates 这些被外键引用的表都在 metadata 里，
    # 否则 DDL 编译时报 NoReferencedTableError
    import app.models  # noqa: F401
    import app.models.inspection  # noqa: F401

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
