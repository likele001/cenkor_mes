"""0011_mrp_landing - MRP 净需求补在途量、建议行可追溯到采购单

此前 MRP 只看库存、不看已下单未到货的量，同一批料会被反复建议再买一遍；
建议算完也就停在页面上，没有落成采购单的路。加 on_order_qty 与 purchase_order_id。
表可能已由 create_all 建立，逐列判存在。
"""
from alembic import op
import sqlalchemy as sa


revision = '0011_mrp_landing'
down_revision = '0010_approval_records'
branch_labels = None
depends_on = None

_TABLE = "mrp_items"
_INDEX = ("ix_mrp_items_purchase_order_id", ["purchase_order_id"])
_FK = "fk_mrp_items_purchase_order"
_FK_COL = "purchase_order_id"


def _table_exists(conn, table_name: str) -> bool:
    # sa.inspect 而非 information_schema：迁移链要能在临时 SQLite 上验证「从零建库」
    return sa.inspect(conn).has_table(table_name)


def _column_exists(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def _index_exists(conn, table: str, index: str) -> bool:
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return False
    return any(ix["name"] == index for ix in insp.get_indexes(table))


def _fk_on_column(conn, table: str, column: str) -> str | None:
    """返回该列上已存在的外键名。

    create_all 建的表，外键名是 MySQL 自动生成的（mrp_items_ibfk_N），按名字查不出来，
    所以按列查——否则这里会再叠一个同列外键。
    """
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return None
    for fk in insp.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []):
            return fk.get("name")
    return None


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, _TABLE):
        return
    if not _column_exists(conn, _TABLE, "on_order_qty"):
        op.add_column(_TABLE, sa.Column("on_order_qty", sa.Integer(), server_default="0", nullable=False))
    new_col = not _column_exists(conn, _TABLE, _FK_COL)
    if new_col:
        op.add_column(_TABLE, sa.Column(_FK_COL, sa.Integer(), nullable=True))
        if not _index_exists(conn, _TABLE, _INDEX[0]):
            op.create_index(_INDEX[0], _TABLE, _INDEX[1])
    if new_col and _fk_on_column(conn, _TABLE, _FK_COL) is None:
        op.create_foreign_key(_FK, _TABLE, "purchase_orders", [_FK_COL], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, _TABLE):
        return
    if not _column_exists(conn, _TABLE, _FK_COL):
        return
    existing_fk = _fk_on_column(conn, _TABLE, _FK_COL)
    if existing_fk:
        op.drop_constraint(existing_fk, _TABLE, type_="foreignkey")
    if _index_exists(conn, _TABLE, _INDEX[0]):
        op.drop_index(_INDEX[0], table_name=_TABLE)
    op.drop_column(_TABLE, _FK_COL)
    if _column_exists(conn, _TABLE, "on_order_qty"):
        op.drop_column(_TABLE, "on_order_qty")
