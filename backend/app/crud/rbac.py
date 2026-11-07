# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
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
    """创建内置角色；**已存在的角色只补不删**。

    这里踩过一个很隐蔽的坑（2026-11-07 实测）：原先对已存在角色也做
    ``role.permissions = preset``（整段替换），而本函数在每次启动都会跑
    （``main.py`` 的 ``DB_AUTO_SEED`` 分支）——于是**给内置角色手工授的权限，
    下次重启就静默消失**。现场证据：给内置 ``qc`` / ``leader`` 补了 5 个
    ``ext.qcode.*``，重启后两个角色的权限数精确回落到 ``ROLE_PERMISSION_PRESETS``
    的 14 / 22，日志里一个字都没有；自建角色（不在 ``DEFAULT_ROLES`` 里）反而
    保住了。管理员会误判成"后台授权没生效"。

    现在：新角色按 preset 全量初始化，已存在角色只把 preset 里**还缺的**补上。
    这样既保留「新版本内置角色自动获得新增默认权限」的能力，又不会覆盖人工配置。
    """
    perms_by_code = {p.code: p for p in ensure_permissions(db)}
    existing = {
        r.code: r
        for r in db.scalars(select(Role)).all()
    }
    roles: list[Role] = []
    for code, name in DEFAULT_ROLES:
        preset = ROLE_PERMISSION_PRESETS.get(code, set())
        role = existing.get(code)
        if role is None:
            role = Role(code=code, name=name)
            db.add(role)
            db.flush()
            if preset:
                role.permissions = [perms_by_code[c] for c in preset if c in perms_by_code]
        elif preset:
            owned = {p.code for p in role.permissions}
            missing = [perms_by_code[c] for c in preset if c in perms_by_code and c not in owned]
            if missing:
                role.permissions.extend(missing)
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
