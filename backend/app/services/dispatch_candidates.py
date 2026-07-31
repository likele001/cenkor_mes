"""自动/手动派工：可派工人员筛选（与分工管理页一致）"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.employee_skill import UserSkillLink
from app.models.role import Role
from app.models.user import User, user_roles

DISPATCH_ROLE_EMPLOYEE = "employee"
DISPATCH_ROLE_LEADER = "leader"


def list_dispatch_candidate_users(
    db: Session,
    *,
    user_ids: list[int] | None = None,
    include_leader: bool = False,
    skill_ids: list[int] | None = None,
    skill_match: str = "any",
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 500,
) -> list[User]:
    """
    可派工人员：默认仅「员工」角色，不含管理员/厂长等。
    include_leader=True 时含班组长（与分工页「含班组长」一致）。
    """
    role_codes = [DISPATCH_ROLE_EMPLOYEE]
    if include_leader:
        role_codes.append(DISPATCH_ROLE_LEADER)

    stmt = (
        select(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(
            User.is_active.is_(True),
            User.is_superuser.is_(False),
            Role.code.in_(role_codes),
        )
        .distinct()
    )

    if user_ids:
        stmt = stmt.where(User.id.in_(user_ids))

    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where((User.username.like(kw)) | (User.full_name.like(kw)))

    ids = [x for x in (skill_ids or []) if x > 0]
    ids = list(dict.fromkeys(ids))
    if ids:
        match = skill_match if skill_match in {"all", "any"} else "any"
        if match == "any":
            subq = (
                select(UserSkillLink.user_id)
                .where(UserSkillLink.skill_id.in_(ids))
                .group_by(UserSkillLink.user_id)
                .subquery()
            )
            stmt = stmt.where(User.id.in_(select(subq.c.user_id)))
        else:
            subq = (
                select(UserSkillLink.user_id)
                .where(UserSkillLink.skill_id.in_(ids))
                .group_by(UserSkillLink.user_id)
                .having(func.count(func.distinct(UserSkillLink.skill_id)) == len(ids))
                .subquery()
            )
            stmt = stmt.where(User.id.in_(select(subq.c.user_id)))

    stmt = stmt.order_by(User.id.asc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def build_user_skill_map(db: Session, user_ids: list[int]) -> dict[int, set[int]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(UserSkillLink.user_id, UserSkillLink.skill_id).where(
            UserSkillLink.user_id.in_(user_ids),
        )
    ).all()
    out: dict[int, set[int]] = {}
    for uid, sid in rows:
        out.setdefault(int(uid), set()).add(int(sid))
    return out


def build_user_department_map(db: Session, user_ids: list[int]) -> dict[int, str | None]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(User.id, Department.name)
        .outerjoin(Department, Department.id == User.department_id)
        .where(User.id.in_(user_ids))
    ).all()
    return {int(uid): (name or None) for uid, name in rows}


def filter_candidates_for_task(
    candidates: list[dict],
    *,
    required_skill_ids: list[int],
    user_skill_map: dict[int, set[int]],
    workshop: str | None,
    user_dept_map: dict[int, str | None],
) -> list[dict]:
    """按工序技能（全部匹配）与车间（部门名包含车间名）过滤；无匹配时回退技能过滤结果。"""
    pool = candidates
    req = [x for x in required_skill_ids if x > 0]
    if req:
        matched = []
        for c in pool:
            uid = int(c["id"])
            skills = user_skill_map.get(uid, set())
            if all(s in skills for s in req):
                matched.append(c)
        pool = matched if matched else pool

    ws = (workshop or "").strip()
    if ws and ws not in ("未分车间",):
        ws_matched = []
        for c in pool:
            uid = int(c["id"])
            dept = user_dept_map.get(uid) or ""
            if ws in dept or dept in ws:
                ws_matched.append(c)
        if ws_matched:
            pool = ws_matched
    return pool
