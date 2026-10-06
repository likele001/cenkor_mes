"""0012_stock_qty_non_negative - 给 stocks.qty 加数据库级非负约束

库存非负此前只有应用层 adjust_stock 一道校验，补数脚本、迁移补数据、并发出库都能绕过
它把库存写成负数，而账实一致那一整批工作的前提就是这个数不为负。

stocks 表可能由启动时的 create_all 建立，所以先判表、判约束是否存在。
"""
from alembic import op
import sqlalchemy as sa


revision = '0012_stock_qty_non_negative'
down_revision = '0011_mrp_landing'
branch_labels = None
depends_on = None

_TABLE = "stocks"
_CHECK = "ck_stocks_qty_non_negative"


def _table_exists(conn) -> bool:
    return sa.inspect(conn).has_table(_TABLE)


def _check_exists(conn) -> bool:
    insp = sa.inspect(conn)
    if not insp.has_table(_TABLE):
        return False
    return any(c["name"] == _CHECK for c in insp.get_check_constraints(_TABLE))


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn):
        return
    if _check_exists(conn):
        return

    bad = conn.execute(sa.text(f"SELECT COUNT(*) FROM `{_TABLE}` WHERE qty < 0")).scalar()
    if bad:
        raise RuntimeError(
            f"{_TABLE} 里有 {bad} 行 qty < 0，加不上非负约束。"
            "先查清这些是漏记的入库还是重复出库（对照 stock_logs 余额），补正后再跑本迁移。"
        )

    op.execute(f"ALTER TABLE `{_TABLE}` ADD CONSTRAINT `{_CHECK}` CHECK (qty >= 0)")


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn) or not _check_exists(conn):
        return
    op.execute(f"ALTER TABLE `{_TABLE}` DROP CONSTRAINT `{_CHECK}`")
