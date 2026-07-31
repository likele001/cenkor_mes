from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.operation_log import list_operation_logs
from app.models.user import User


router = APIRouter(dependencies=[Depends(require_permissions(["operation_log.view"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "user_id": x.user_id,
        "username": x.username,
        "module": x.module,
        "action": x.action,
        "object_type": x.object_type,
        "object_id": x.object_id,
        "detail": x.detail,
        "method": x.method,
        "path": x.path,
        "ip": x.ip,
        "user_agent": x.user_agent,
        "created_at": x.created_at,
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    module: str | None = Query(default=None),
    action: str | None = Query(default=None),
    user_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_operation_logs(
        db,
        keyword=keyword,
        module=module,
        action=action,
        user_id=user_id,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_out(x) for x in items]})
