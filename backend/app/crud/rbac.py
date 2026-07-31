from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.seed import DEFAULT_PERMISSIONS, DEFAULT_ROLES, ROLE_PERMISSION_PRESETS
from app.models.permission import Permission
from app.models.role import Role


def ensure_permissions(db: Session) -> list[Permission]:
    existing = {p.code: p for p in db.scalars(select(Permission)).all()}
    items: list[Permission] = []
    for code, name in DEFAULT_PERMISSIONS:
        if code in existing:
            p = existing[code]
        else:
            p = Permission(code=code, name=name)
            db.add(p)
            existing[code] = p
        items.append(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = {p.code: p for p in db.scalars(select(Permission)).all()}
        items = [existing.get(code) for code, _ in DEFAULT_PERMISSIONS if code in existing]

    perms_by_code = {p.code: p for p in items}
    for role in db.scalars(select(Role)).all():
        preset = ROLE_PERMISSION_PRESETS.get(role.code, set())
        if not preset:
            continue
        owned = {p.code for p in role.permissions}
        missing = [perms_by_code[c] for c in preset if c in perms_by_code and c not in owned]
        if missing:
            role.permissions.extend(missing)
    db.flush()
    return items


def create_default_roles(db: Session) -> list[Role]:
    perms_by_code = {p.code: p for p in ensure_permissions(db)}
    existing = {
        r.code: r
        for r in db.scalars(select(Role)).all()
    }
    roles: list[Role] = []
    for code, name in DEFAULT_ROLES:
        if code in existing:
            role = existing[code]
        else:
            role = Role(code=code, name=name)
            db.add(role)
            db.flush()
        preset = ROLE_PERMISSION_PRESETS.get(code, set())
        if preset:
            role.permissions = [perms_by_code[c] for c in preset if c in perms_by_code]
        roles.append(role)
    db.flush()
    return roles


def get_user_permission_codes(db: Session, user_id: int) -> list[str]:
    from app.models.user import User

    user = db.get(User, user_id)
    if not user:
        return []
    codes: set[str] = set()
    for r in user.roles:
        for p in r.permissions:
            codes.add(p.code)
    return sorted(codes)
