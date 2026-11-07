"""0019_basics - 返工单 + 四项基础台账

本版本补五张表，并给已有的 `inspection_orders` 加两个软引用列：

    rework_orders            返工单（处置单 return_process 明细的可执行载体）
    material_substitutes     物料替代关系
    engineering_changes      工程变更 ECN
    equipment_downtimes      设备停机记录
    supplier_scores          供应商评分
    inspection_orders.report_id / process_id   整批报工终审与 FAI 联动的挂靠点

两个加列都是**普通 Integer + 索引、不带外键**：它们是质量证据上的软引用，
不能因为报工或工序主档被删就把检验单一起带走（见 app/models/basics.py 口径第 3 条）。

幂等要求同 0018：新库走 0001 的 `create_all` 已经建好，存量库在这里建；
加列前先查 information_schema，重复执行不会报 Duplicate column。
DDL 一律取模型元数据，不在迁移里手抄一份表定义。
"""
from alembic import op
import sqlalchemy as sa


revision = "0019_basics"
down_revision = "0018_inspection"
branch_labels = None
depends_on = None

# 父表在前：rework_orders 同时引用 dispositions / disposition_items / reports / tasks
_TABLES = [
    "rework_orders",
    "material_substitutes",
    "engineering_changes",
    "equipment_downtimes",
    "supplier_scores",
]

# (表, 列, 类型) —— 已存在就跳过
_ADD_COLUMNS = [
    ("inspection_orders", "report_id", sa.Integer()),
    ("inspection_orders", "process_id", sa.Integer()),
]


def upgrade() -> None:
    from app.models.base import Base

    # 整包导入，确保被外键引用的表都在 metadata 里，否则编译 DDL 会 NoReferencedTableError
    import app.models  # noqa: F401
    import app.models.basics  # noqa: F401
    import app.models.inspection  # noqa: F401

    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in _TABLES:
        table = Base.metadata.tables.get(name)
        if table is None or insp.has_table(name):
            continue
        table.create(bind=bind, checkfirst=True)

    for table_name, col_name, col_type in _ADD_COLUMNS:
        if not insp.has_table(table_name):
            continue
        existing = {c["name"] for c in insp.get_columns(table_name)}
        if col_name in existing:
            continue
        op.add_column(table_name, sa.Column(col_name, col_type, nullable=True))
        op.create_index(f"ix_{table_name}_{col_name}", table_name, [col_name])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table_name, col_name, _ in _ADD_COLUMNS:
        if not insp.has_table(table_name):
            continue
        if col_name not in {c["name"] for c in insp.get_columns(table_name)}:
            continue
        try:
            op.drop_index(f"ix_{table_name}_{col_name}", table_name=table_name)
        except Exception:
            pass
        op.drop_column(table_name, col_name)
    for name in reversed(_TABLES):
        if insp.has_table(name):
            op.drop_table(name)
