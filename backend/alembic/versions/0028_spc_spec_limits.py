"""spc spec limits

SPC 控制图补规格上下限列。

历史问题：spc_charts 只有 ucl / lcl 两列（注释写的是控制限），SPC 扩展为了不改
核心表结构，把这两列挪用来存规格上下限 USL / LSL。数值本身没错，但字段名与语义
相反 —— 任何人看到 ucl 都以为是「算出来的上控制限」，二次开发必然踩坑。

现在独立出 usl / lsl 两个规范列，ucl / lcl 保留为废弃列（读时仅作回退，
不再写入）。控制限不入库，永远由样本按 X̄-R / X̄-s / p / np / c 实时计算。

Revision ID: 0028_spc_spec_limits
Revises: 0027_work_order_entry
"""

import sqlalchemy as sa
from alembic import op

revision = "0028_spc_spec_limits"
down_revision = "0027_work_order_entry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite 仅用于测试：空库由 0001 的 create_all 直接建成最新结构
        return
    insp = sa.inspect(bind)

    cols = {c["name"] for c in insp.get_columns("spc_charts")}
    # 幂等：SPC 扩展自带的 migrations/0001 也会加这两列（扩展先装、核心后升级的场景）
    if "usl" not in cols:
        op.add_column("spc_charts", sa.Column("usl", sa.Float(), nullable=True))
    if "lsl" not in cols:
        op.add_column("spc_charts", sa.Column("lsl", sa.Float(), nullable=True))

    # 回填存量：旧数据把规格限存在 ucl / lcl 里，只填空值，已有值一律不覆盖
    op.execute("UPDATE spc_charts SET usl = ucl WHERE usl IS NULL AND ucl IS NOT NULL")
    op.execute("UPDATE spc_charts SET lsl = lcl WHERE lsl IS NULL AND lcl IS NOT NULL")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    insp = sa.inspect(bind)

    cols = {c["name"] for c in insp.get_columns("spc_charts")}
    if "usl" in cols:
        op.drop_column("spc_charts", "usl")
    if "lsl" in cols:
        op.drop_column("spc_charts", "lsl")
