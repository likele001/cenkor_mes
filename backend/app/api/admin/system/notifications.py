from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.notification import count_my_unread, list_my_notifications, mark_my_all_read, mark_my_notification_read
from app.models.user import User


router = APIRouter(dependencies=[Depends(require_permissions(["notification.view"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "title": x.title,
        "content": x.content,
        "level": x.level,
        "biz_type": x.biz_type,
        "biz_id": x.biz_id,
        "read_at": x.read_at,
        "created_at": x.created_at,
    }


@router.get("")
def list_my_api(
    unread: bool | None = Query(default=None),
    level: str | None = Query(default=None, max_length=16),
    biz_type: str | None = Query(default=None, max_length=32),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_my_notifications(
        db,
        user_id=user.id,
        unread=unread,
        level=level,
        biz_type=biz_type,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_out(x) for x in items]})


@router.post("/read")
def mark_read_api(
    notification_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = mark_my_notification_read(db, user_id=user.id, notification_id=notification_id)
    db.commit()
    return ok({"updated": n})


@router.post("/read-all")
def mark_all_read_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = mark_my_all_read(db, user_id=user.id)
    db.commit()
    return ok({"updated": n})


@router.get("/unread-count")
def unread_count_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = count_my_unread(db, user_id=user.id)
    return ok({"count": n})
