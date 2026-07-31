from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog


def create_operation_log(
    db: Session,
    user_id: int | None,
    username: str | None,
    module: str,
    action: str,
    object_type: str | None = None,
    object_id: int | None = None,
    detail: str | None = None,
    method: str | None = None,
    path: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> OperationLog:
    item = OperationLog(
        user_id=user_id,
        username=username,
        module=module,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail,
        method=method,
        path=path,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(item)
    db.flush()
    return item


def list_operation_logs(
    db: Session,
    keyword: str | None = None,
    module: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[OperationLog]:
    stmt = select(OperationLog)
    if module:
        stmt = stmt.where(OperationLog.module == module)
    if action:
        stmt = stmt.where(OperationLog.action == action)
    if user_id:
        stmt = stmt.where(OperationLog.user_id == user_id)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(OperationLog.username.like(kw), OperationLog.detail.like(kw), OperationLog.path.like(kw)))
    stmt = stmt.order_by(OperationLog.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()
