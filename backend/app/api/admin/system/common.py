from fastapi import Request
from sqlalchemy.orm import Session

from app.crud.operation_log import create_operation_log
from app.models.user import User


def write_op_log(
    db: Session,
    request: Request,
    user: User,
    *,
    module: str,
    action: str,
    object_type: str | None = None,
    object_id: int | None = None,
    detail: str | None = None,
) -> None:
    ip = None
    if request.client:
        ip = request.client.host
    ua = request.headers.get("user-agent")
    create_operation_log(
        db,
        user_id=user.id,
        username=user.username,
        module=module,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail,
        method=request.method,
        path=str(request.url.path),
        ip=ip,
        user_agent=ua,
    )
