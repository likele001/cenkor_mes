"""企业微信推送目标解析"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.notification import notify_users_with_permission
from app.models.department import Department
from app.models.permission import Permission
from app.models.process import Process
from app.models.role import Role, role_permissions
from app.models.user import User, user_roles
from app.services.wecom.settings import get_wecom_settings_raw, get_group_webhook


def _users_with_role_codes(db: Session, role_codes: set[str]) -> list[int]:
    if not role_codes:
        return []
    stmt = (
        select(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(
            User.is_active.is_(True),
            Role.code.in_(role_codes),
        )
        .distinct()
    )
    return [x[0] for x in db.execute(stmt).all()]


def _users_with_permission(db: Session, permission_code: str) -> list[int]:
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
    return [x[0] for x in db.execute(stmt).all()]


def _dept_leader_user_ids(db: Session, department_id: int | None) -> list[int]:
    if not department_id:
        return []
    dept_ids = [department_id]
    dept = db.get(Department, department_id)
    if dept and dept.parent_id:
        dept_ids.append(dept.parent_id)
    leader_ids = set(_users_with_role_codes(db, {"leader"}))
    audit_ids = set(_users_with_permission(db, "report.audit"))
    candidate = leader_ids & audit_ids
    if not candidate:
        candidate = audit_ids or leader_ids
    if not candidate:
        return []
    stmt = select(User.id).where(
        User.is_active.is_(True),
        User.department_id.in_(dept_ids),
        User.id.in_(candidate),
    )
    return [x[0] for x in db.execute(stmt).all()]


def _dept_manager_user_ids(db: Session, department_id: int | None) -> list[int]:
    if not department_id:
        return _users_with_role_codes(db, {"admin"}) or [
            x[0]
            for x in db.execute(
                select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
            ).all()
        ]
    dept_ids: list[int] = []
    cur = db.get(Department, department_id)
    while cur:
        dept_ids.append(cur.id)
        if not cur.parent_id:
            break
        cur = db.get(Department, cur.parent_id)
    manager_roles = set(_users_with_role_codes(db, {"leader", "admin"}))
    boss_ids = [
        x[0]
        for x in db.execute(
            select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
        ).all()
    ]
    stmt = select(User.id).where(
        User.is_active.is_(True),
        User.department_id.in_(dept_ids),
        User.id.in_(manager_roles),
    )
    ids = list({x[0] for x in db.execute(stmt).all()} | set(boss_ids))
    return ids


def _workshop_leader_user_ids(db: Session, workshop: str | None, department_id: int | None) -> list[int]:
    if not workshop and not department_id:
        return []
    if department_id:
        dept = db.get(Department, department_id)
        if dept and (workshop is None or dept.name == workshop or workshop in dept.name):
            return _dept_leader_user_ids(db, department_id)
    if workshop:
        dept = db.scalar(
            select(Department).where(
                Department.is_active.is_(True),
                Department.name.like(f"%{workshop}%"),
            )
        )
        if dept:
            return _dept_leader_user_ids(db, dept.id)
    return []


def _boss_user_ids(db: Session) -> list[int]:
    ids = [
        x[0]
        for x in db.execute(
            select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
        ).all()
    ]
    ids.extend(_users_with_role_codes(db, {"admin"}))
    return list(dict.fromkeys(ids))


def _dept_auto_webhook(db: Session, department_id: int | None, cfg: dict) -> str:
    if not department_id:
        return ""
    dept = db.get(Department, department_id)
    if not dept or not dept.wecom_chat_group_code:
        return ""
    return get_group_webhook(cfg, dept.wecom_chat_group_code)


def resolve_targets(
    db: Session,
    target_codes: list[str],
    *,
    user_id: int | None = None,
    department_id: int | None = None,
    workshop: str | None = None,
) -> list[dict]:
    """返回 [{kind: user|webhook, ref: userid|webhook_url, user_id?, webhook_code?}]"""
    cfg = get_wecom_settings_raw(db)
    seen: set[str] = set()
    out: list[dict] = []

    def add_user(uid: int) -> None:
        u = db.get(User, uid)
        if not u or not u.is_active:
            return
        uid_str = (u.wecom_userid or "").strip()
        if not uid_str:
            return
        key = f"user:{uid_str}"
        if key in seen:
            return
        seen.add(key)
        out.append({"kind": "user", "ref": uid_str, "user_id": uid})
    def add_webhook(webhook_url: str, webhook_code: str = "") -> None:
        url = (webhook_url or "").strip()
        if not url:
            return
        key = f"webhook:{url}"
        if key in seen:
            return
        seen.add(key)
        out.append({"kind": "webhook", "ref": url, "webhook_code": webhook_code})

    for code in target_codes:
        if code == "assigned_employee":
            if user_id:
                add_user(user_id)
        elif code == "dept_leaders":
            for uid in _dept_leader_user_ids(db, department_id):
                add_user(uid)
        elif code == "dept_managers":
            for uid in _dept_manager_user_ids(db, department_id):
                add_user(uid)
        elif code == "workshop_leaders":
            for uid in _workshop_leader_user_ids(db, workshop, department_id):
                add_user(uid)
        elif code == "boss":
            for uid in _boss_user_ids(db):
                add_user(uid)
        elif code.startswith("group:"):
            gcode = code.split(":", 1)[1]
            if gcode == "dept_auto":
                add_webhook(_dept_auto_webhook(db, department_id, cfg), "dept_auto")
            else:
                add_webhook(get_group_webhook(cfg, gcode), gcode)
        elif code.startswith("permission:"):
            perm = code.split(":", 1)[1]
            for uid in _users_with_permission(db, perm):
                add_user(uid)

    return out


def resolve_alert_targets(
    db: Session,
    level: str,
    *,
    department_id: int | None = None,
) -> list[dict]:
    cfg = get_wecom_settings_raw(db)
    rule = (cfg.get("rules") or {}).get("alert") or {}
    esc = rule.get("escalation") or {}
    lv = level if level in esc else "warning"
    codes = esc.get(lv) or esc.get("warning") or ["dept_managers"]
    return resolve_targets(
        db,
        codes,
        department_id=department_id,
    )


def notify_in_app_for_targets(
    db: Session,
    target_codes: list[str],
    *,
    title: str,
    content: str,
    level: str = "info",
    biz_type: str | None = None,
    biz_id: int | None = None,
    user_id: int | None = None,
    department_id: int | None = None,
    workshop: str | None = None,
) -> int:
    user_ids: set[int] = set()
    for code in target_codes:
        if code == "assigned_employee" and user_id:
            user_ids.add(user_id)
        elif code == "dept_leaders":
            user_ids.update(_dept_leader_user_ids(db, department_id))
        elif code == "dept_managers":
            user_ids.update(_dept_manager_user_ids(db, department_id))
        elif code == "workshop_leaders":
            user_ids.update(_workshop_leader_user_ids(db, workshop, department_id))
        elif code == "boss":
            user_ids.update(_boss_user_ids(db))
        elif code.startswith("permission:"):
            user_ids.update(_users_with_permission(db, code.split(":", 1)[1]))
    n = 0
    from app.crud.notification import create_notification
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


def get_user_department_and_workshop(
    db: Session,
    user_id: int,
    process_id: int | None = None,
) -> tuple[int | None, str | None]:
    u = db.get(User, user_id)
    dept_id = u.department_id if u else None
    workshop = None
    if process_id:
        proc = db.get(Process, process_id)
        if proc:
            workshop = proc.workshop
    return dept_id, workshop


def resolve_user_ids(
    db: Session,
    target_codes: list[str],
    *,
    user_id: int | None = None,
    department_id: int | None = None,
    workshop: str | None = None,
) -> list[int]:
    """按角色/权限解析目标用户 id（不依赖任何具体通道绑定字段）。

    供统一消息分发器在规则事件下解析个人目标，支持飞书/企微/钉钉任意通道组合。
    """
    user_ids: set[int] = set()
    for code in target_codes:
        if code == "assigned_employee":
            if user_id:
                user_ids.add(user_id)
        elif code == "dept_leaders":
            user_ids.update(_dept_leader_user_ids(db, department_id))
        elif code == "dept_managers":
            user_ids.update(_dept_manager_user_ids(db, department_id))
        elif code == "workshop_leaders":
            user_ids.update(_workshop_leader_user_ids(db, workshop, department_id))
        elif code == "boss":
            user_ids.update(_boss_user_ids(db))
        elif code.startswith("permission:"):
            user_ids.update(_users_with_permission(db, code.split(":", 1)[1]))
    return list(user_ids)


def resolve_group_codes(target_codes: list[str]) -> list[str]:
    """从目标编码中提取群目标编码（group:xxx）。"""
    return [c.split(":", 1)[1] for c in target_codes if c.startswith("group:")]
