"""溯源查询（MySQL 5.7 兼容排序）"""

from sqlalchemy.orm import Session

from app.crud.trace import get_trace_by_code


def test_get_trace_by_product_code_order_compiles_mysql(session: Session, tenant):
    """product_code 查询不应生成 NULLS LAST（MySQL 5.7 不支持）。"""
    from sqlalchemy.dialects import mysql
    from sqlalchemy import select
    from app.models.trace import TraceCode
    from app.crud.trace import TRACE_TASK_SEQ_ORDER

    stmt = (
        select(TraceCode)
        .where(TraceCode.tenant_id == tenant.id, TraceCode.product_code == "FP001TEST")
        .order_by(*TRACE_TASK_SEQ_ORDER)
        .limit(1)
    )
    sql = str(stmt.compile(dialect=mysql.dialect())).upper()
    assert "NULLS LAST" not in sql
    assert get_trace_by_code(session, tenant.id, "NOTEXIST999") is None
