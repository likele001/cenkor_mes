from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.employee_skill import (
    create_skill,
    get_skill_by_code,
    get_skill_by_id,
    list_skills,
    list_user_skill_ids,
    set_user_skills,
    update_skill,
)
from app.models.role import Role
from app.models.user import User, user_roles
from app.schemas.employee_skill import SkillCreateIn, SkillUpdateIn, UserSkillsSetIn
from app.services.code_generator import BizType, resolve_code

# 可维护技能的岗位：一线员工 + 班组长（不含管理员、客户等）
_SKILL_USER_ROLE_CODES = ("employee", "leader")


router = APIRouter(dependencies=[Depends(require_permissions(["skill.manage"]))])


def _skill_assignable_users_stmt():
    return (
        select(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(
            User.is_active.is_(True),
            Role.code.in_(_SKILL_USER_ROLE_CODES),
        )
        .distinct()
    )


def _get_skill_assignable_user(db: Session, user_id: int) -> User | None:
    stmt = _skill_assignable_users_stmt().where(User.id == user_id)
    return db.scalar(stmt)


def _skill_out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "name": x.name,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


@router.get("")
def list_skills_api(
    keyword: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_skills(db, keyword=keyword, include_inactive=include_inactive, offset=offset, limit=limit)
    return ok({"items": [_skill_out(x) for x in items]})


@router.post("")
def create_skill_api(
    payload: SkillCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    skill_code = resolve_code(
        db,
        biz_type=BizType.SKILL,
        code=payload.code,
        exists=lambda c: get_skill_by_code(db, c) is not None,
        duplicate_msg="技能编码已存在",
    )
    item = create_skill(db, code=skill_code, name=payload.name, is_active=payload.is_active)
    write_op_log(
        db,
        request,
        user,
        module="system.skill",
        action="create",
        object_type="skill",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_skill_out(item))


@router.put("/{skill_id}")
def update_skill_api(
    skill_id: int,
    payload: SkillUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_skill_by_id(db, skill_id=skill_id)
    if not item:
        raise HTTPException(status_code=404, detail="技能不存在")
    if payload.code is not None:
        exists = get_skill_by_code(db, code=payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="技能编码已存在")
    update_skill(db, item, code=payload.code, name=payload.name, is_active=payload.is_active)
    write_op_log(
        db,
        request,
        user,
        module="system.skill",
        action="update",
        object_type="skill",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_skill_out(item))


@router.delete("/{skill_id}")
def disable_skill_api(
    skill_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_skill_by_id(db, skill_id=skill_id)
    if not item:
        raise HTTPException(status_code=404, detail="技能不存在")
    update_skill(db, item, is_active=False)
    write_op_log(
        db,
        request,
        user,
        module="system.skill",
        action="disable",
        object_type="skill",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    return ok()


@router.get("/users")
def list_users_api(
    keyword: str | None = Query(default=None, max_length=50),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = _skill_assignable_users_stmt()
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where((User.username.like(kw)) | (User.full_name.like(kw)))
    stmt = stmt.order_by(User.id.desc()).offset(offset).limit(limit)
    items = db.scalars(stmt).all()
    return ok({"items": [{"id": u.id, "username": u.username, "full_name": u.full_name} for u in items]})


@router.get("/users/{user_id}/skills")
def get_user_skills_api(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = _get_skill_assignable_user(db, user_id)
    if not target:
        raise HTTPException(status_code=400, detail="用户不存在或不是可派工员工/班组长")
    ids = list_user_skill_ids(db, user_id=user_id)
    return ok({"user_id": user_id, "skill_ids": ids})


@router.put("/users/{user_id}/skills")
def set_user_skills_api(
    user_id: int,
    payload: UserSkillsSetIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = _get_skill_assignable_user(db, user_id)
    if not target:
        raise HTTPException(status_code=400, detail="用户不存在或不是可派工员工/班组长")
    try:
        set_user_skills(db, user_id=user_id, skill_ids=payload.skill_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    write_op_log(
        db,
        request,
        user,
        module="system.skill",
        action="set_user_skills",
        object_type="user",
        object_id=user_id,
        detail=",".join(str(x) for x in payload.skill_ids),
    )
    db.commit()
    return ok({"user_id": user_id, "skill_ids": payload.skill_ids})
