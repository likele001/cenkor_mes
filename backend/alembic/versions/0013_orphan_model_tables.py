"""0013_orphan_model_tables - 补齐模型定义但从未被建出来的表

这些表在模型里有定义，但从来没有进过任何一版迁移；`app/models/__init__.py`
也没导入它们的模块，所以应用启动时的 create_all 同样不会建它们——
结果是「新库（0001 create_all 现在会建，因为 env.py 已注册全部模型）」
和「老库（一直缺）」不一致。

DDL 直接取模型元数据：避免同一张表有两份定义各改各的。
molds / quotations / spc / wechat 目前只是脚手架（mold_shot_tracker 还是 stub），
本版本只负责让库结构对齐，不代表这些功能已可用。
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_orphan_model_tables"
down_revision = "0012_stock_qty_non_negative"
branch_labels = None
depends_on = None

# 按依赖顺序列出（父表在前）：不用 metadata.sorted_tables，因为全量排序会在
# crm_opportunities/orders/report_units/trace_codes 的互相引用上报 unresolvable cycle。
_MISSING_TABLES = [
    "molds",
    "mold_process_bindings",
    "mold_maintenance_logs",
    "quotations",
    "quotation_items",
    "spc_charts",
    "spc_samples",
    "user_wechat_subscriptions",
    "wechat_mp_push_logs",
]


def upgrade() -> None:
    from app.models.base import Base

    # 只导入确实需要的模块，避免把无关模型的表一起拖进来
    import app.models.mold  # noqa: F401
    import app.models.quotation  # noqa: F401
    import app.models.spc  # noqa: F401
    import app.models.user_wechat_subscription  # noqa: F401
    import app.models.wechat_mp_push_log  # noqa: F401

    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in _MISSING_TABLES:
        table = Base.metadata.tables.get(name)
        if table is None or insp.has_table(name):
            continue
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for name in reversed(_MISSING_TABLES):
        if insp.has_table(name):
            op.drop_table(name)
