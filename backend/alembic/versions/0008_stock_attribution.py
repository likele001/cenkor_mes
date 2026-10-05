"""0008_stock_attribution - 出货仓与外协出入库归属

账实一致第三批：
- shipments 增加 warehouse_id，发货扣的是哪个仓必须留在单据上（此前是运行时猜最低 ID 的启用仓）；
- subcontract_send_logs / subcontract_receive_logs 增加 warehouse_id，外协发出/收回开始记库存流水。

新增列均可空，历史行不回填：老单据读到的仓库为空即表示"当时没记"，不做伪造。
"""
from alembic import op
import sqlalchemy as sa


revision = '0008_stock_attribution'
down_revision = '0007_ar_ap_settlement'
branch_labels = None
depends_on = None

_TARGETS = [
    ("shipments", "warehouse_id"),
    ("subcontract_send_logs", "warehouse_id"),
    ("subcontract_receive_logs", "warehouse_id"),
]


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
    ), {"t": table, "c": column})
    return result.scalar() > 0


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
    ), {"t": table_name})
    return result.scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()
    for table, column in _TARGETS:
        if not _table_exists(conn, table) or _column_exists(conn, table, column):
            continue
        op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))
        op.create_index(f"ix_{table}_{column}", table, [column])
        op.create_foreign_key(
            f"fk_{table}_{column}", table, "warehouses",
            [column], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    conn = op.get_bind()
    for table, column in reversed(_TARGETS):
        if not _table_exists(conn, table) or not _column_exists(conn, table, column):
            continue
        op.drop_constraint(f"fk_{table}_{column}", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_column(table, column)
