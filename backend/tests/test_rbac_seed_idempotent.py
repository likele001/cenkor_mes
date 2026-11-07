# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""内置角色播种必须幂等，且不覆盖人工授予的权限。

背景（2026-11-07 现场实测）：`create_default_roles()` 在每次启动都会跑
（`main.py` 的 `DB_AUTO_SEED` 分支）。旧实现对**已存在角色**也做
`role.permissions = preset` 整段替换，于是给内置角色（admin/leader/qc/employee/customer）
在后台手工授的扩展权限，重启后静默消失。证据：内置 `qc` / `leader` 补过的 5 个
`ext.qcode.*` 全部蒸发，权限数精确回落到预设的 14 / 22，日志无任何提示；不在
`DEFAULT_ROLES` 里的自建角色反而保住。

以下用例把「只补不删」钉死：旧实现会让 test_manual_extra_permission_survives_seeding
直接失败。
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.seed import ROLE_PERMISSION_PRESETS
from app.crud.rbac import create_default_roles
from app.models.permission import Permission
from app.models.role import Role


def _codes(role: Role) -> set[str]:
    return {p.code for p in role.permissions}


def _all_codes(session) -> set[str]:
    return {p.code for p in session.scalars(select(Permission)).all()}


def _add_extra_permission(session, code: str) -> Permission:
    perm = Permission(code=code, name=code)
    session.add(perm)
    session.flush()
    return perm


def test_manual_extra_permission_survives_seeding(session):
    """给内置角色手工加的扩展权限，不能被启动播种抹掉。"""
    extra = _add_extra_permission(session, "ext.qcode.view")
    qc = Role(code="qc", name="质检员")
    session.add(qc)
    session.flush()
    qc.permissions.append(extra)
    session.flush()

    create_default_roles(session)

    codes = _codes(session.scalars(select(Role).where(Role.code == "qc")).one())
    assert "ext.qcode.view" in codes, "手工授予的扩展权限被启动播种覆盖了"
    # 预设照旧补齐（新增的内置默认权限仍要能自动落地）
    assert ROLE_PERMISSION_PRESETS["qc"] & _all_codes(session) <= codes


def test_admin_extension_permissions_not_wiped(session):
    """admin 最容易被忽略：扩展同步会给它补 ext.*，播种不能把它打回核心预设。"""
    admin = Role(code="admin", name="管理员")
    session.add(admin)
    session.flush()
    granted = [_add_extra_permission(session, c) for c in
               ("ext.qcode.view", "ext.crm_suite.view")]
    admin.permissions.extend(granted)
    session.flush()

    create_default_roles(session)

    codes = _codes(session.scalars(select(Role).where(Role.code == "admin")).one())
    assert {"ext.qcode.view", "ext.crm_suite.view"} <= codes


def test_new_role_gets_full_preset(session):
    """角色不存在时才按预设全量初始化。"""
    create_default_roles(session)

    qc = session.scalars(select(Role).where(Role.code == "qc")).one()
    assert ROLE_PERMISSION_PRESETS["qc"] & _all_codes(session) <= _codes(qc)


def test_repeated_seeding_is_idempotent(session):
    """连跑两次结果一致（启动可能重复触发）。"""
    create_default_roles(session)
    first = {r.code: _codes(r) for r in session.scalars(select(Role)).all()}

    create_default_roles(session)
    session.expire_all()
    second = {r.code: _codes(r) for r in session.scalars(select(Role)).all()}

    assert first == second


def test_preset_removal_does_not_strip_manual_grant(session):
    """预设以后若删掉某个权限，也不该连带删掉同名的历史人工授权。

    这条是「只补不删」的推论：播种只负责加法，减法必须由后台显式操作。
    """
    extra = _add_extra_permission(session, "supplier_score.view")
    qc = Role(code="qc", name="质检员")
    session.add(qc)
    session.flush()
    qc.permissions.append(extra)
    session.flush()

    create_default_roles(session)

    assert "supplier_score.view" in _codes(
        session.scalars(select(Role).where(Role.code == "qc")).one()
    )
