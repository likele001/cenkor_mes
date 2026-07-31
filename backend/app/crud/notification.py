from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.user import User, user_roles


def create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    content: str,
    level: str = "info",
    biz_type: str | None = None,
    biz_id: int | None = None,
    feishu_event: str | None = None,
    feishu_department_id: int | None = None,
    feishu_workshop: str | None = None,
) -> Notification:
    obj = Notification(
        user_id=user_id,
        title=title,
        content=content,
        level=level,
        biz_type=biz_type,
        biz_id=biz_id,
    )
    db.add(obj)
    db.flush()
    if feishu_event:
        try:
            from app.services.feishu.notify import emit_feishu_event

            emit_feishu_event(
                db,
                feishu_event,
                title=title,
                content=content,
                level=level,
                biz_type=biz_type,
                biz_id=biz_id,
                user_id=user_id,
                department_id=feishu_department_id,
                workshop=feishu_workshop,
            )
        except Exception:
            pass
        try:
            from app.services.wecom.notify import emit_wecom_event

            emit_wecom_event(
                db,
                feishu_event,
                title=title,
                content=content,
                level=level,
                biz_type=biz_type,
                biz_id=biz_id,
                user_id=user_id,
                department_id=feishu_department_id,
                workshop=feishu_workshop,
            )
        except Exception:
            pass
        try:
            from app.services.dingtalk.notify import emit_dingtalk_event

            emit_dingtalk_event(
                db,
                feishu_event,
                title=title,
                content=content,
                level=level,
                biz_type=biz_type,
                biz_id=biz_id,
                user_id=user_id,
                department_id=feishu_department_id,
                workshop=feishu_workshop,
            )
        except Exception:
            pass
        try:
            from app.services.wechat_mp.notify import emit_wechat_mp_event

            emit_wechat_mp_event(
                db,
                feishu_event,
                title=title,
                content=content,
                user_id=user_id,
            )
        except Exception:
            pass
    return obj


def notify_users_with_permission(
    db: Session,
    *,
    permission_code: str,
    title: str,
    content: str,
    level: str = "info",
    biz_type: str | None = None,
    biz_id: int | None = None,
) -> int:
    stmt = (
        select(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .join(role_permissions, role_permissions.c.role_id == Role.id)
        .join(Permission, Permission.id == role_permissions.c.permission_id)
        .where(
            User.is_active.is_(True),
            Permission.code == permission_code,
        )
        .distinct()
    )
    user_ids = [x[0] for x in db.execute(stmt).all()]
    n = 0
    for uid in user_ids:
        create_notification(
            db,
            user_id=uid,
            title=title,
            content=content,
            level=level,
            biz_type=biz_type,
            biz_id=biz_id,
        )
        n += 1
    return n


def notify_superusers(
    db: Session,
    *,
    title: str,
    content: str,
    level: str = "info",
    biz_type: str | None = None,
    biz_id: int | None = None,
) -> int:
    user_ids = [x[0] for x in db.execute(select(User.id).where(User.is_superuser.is_(True))).all()]
    n = 0
    for uid in user_ids:
        create_notification(db, user_id=uid, title=title, content=content, level=level, biz_type=biz_type, biz_id=biz_id)
        n += 1
    return n


def list_my_notifications(
    db: Session,
    *,
    user_id: int,
    unread: bool | None = None,
    level: str | None = None,
    biz_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread is True:
        stmt = stmt.where(Notification.read_at.is_(None))
    if unread is False:
        stmt = stmt.where(Notification.read_at.is_not(None))
    if level:
        stmt = stmt.where(Notification.level == level)
    if biz_type:
        stmt = stmt.where(Notification.biz_type == biz_type)
    stmt = stmt.order_by(Notification.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def mark_my_notification_read(db: Session, *, user_id: int, notification_id: int) -> int:
    now = datetime.utcnow()
    res = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.id == notification_id, Notification.read_at.is_(None))
        .values(read_at=now)
    )
    db.flush()
    return int(res.rowcount or 0)


def mark_my_all_read(db: Session, *, user_id: int) -> int:
    now = datetime.utcnow()
    res = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=now)
    )
    db.flush()
    return int(res.rowcount or 0)


def count_my_unread(db: Session, *, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        or 0
    )
