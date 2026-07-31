from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.department import get_department_by_id
from app.crud.system_rbac import get_role_by_id
from app.crud.user import (
    create_user,
    get_user_by_id,
    get_user_by_tenant_and_username,
    list_users,
    set_password,
    set_user_roles,
    update_user,
)
from app.models.user import User
from app.schemas.system_rbac import UserCreateIn, UserUpdateIn
from app.tasks._sync_excel import make_excel_response


router = APIRouter(dependencies=[Depends(require_permissions(["user.manage"]))])


def _role_out(x) -> dict:
    return {"id": x.id, "code": x.code, "name": x.name}


def _department_out(x) -> dict | None:
    if not x:
        return None
    return {"id": x.id, "code": x.code, "name": x.name}


def _out(x: User) -> dict:
    return {
        "id": x.id,
        "department_id": x.department_id,
        "username": x.username,
        "full_name": x.full_name,
        "is_active": x.is_active,
        "is_superuser": x.is_superuser,
        "salary_type": x.salary_type,
        "hourly_rate": float(x.hourly_rate) if x.hourly_rate is not None else None,
        "created_at": x.created_at,
        "roles": [_role_out(r) for r in x.roles],
        "department": _department_out(getattr(x, "department", None)),
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_users(db, keyword=keyword, offset=offset, limit=limit, include_inactive=include_inactive)
    return ok({"items": [_out(x) for x in items]})


@router.get("/export")
def export_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_users(db, offset=0, limit=999999, include_inactive=True)
    rows = []
    for x in items:
        dept_name = x.department.name if getattr(x, "department", None) else ""
        rows.append([x.username, x.full_name or "", dept_name, "是" if x.is_active else "否", str(x.created_at) if x.created_at else ""])
    return make_excel_response(
        headers=["用户名", "姓名", "部门", "启用", "创建时间"],
        rows=rows,
        filename="users.xlsx",
        sheet_name="用户",
    )


@router.post("")
def create_api(
    payload: UserCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exists = get_user_by_tenant_and_username(db, username=payload.username)
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    if payload.is_superuser and not user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可创建超管账号")
    if payload.department_id is not None:
        dept = get_department_by_id(db, department_id=payload.department_id)
        if not dept:
            raise HTTPException(status_code=400, detail="部门不存在")
    roles = []
    for rid in payload.role_ids:
        r = get_role_by_id(db, role_id=rid)
        if not r:
            raise HTTPException(status_code=400, detail=f"角色不存在: {rid}")
        roles.append(r)
    item = create_user(db, username=payload.username, password=payload.password, full_name=payload.full_name)
    update_user(
        db, item,
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
        department_id=payload.department_id,
        salary_type=payload.salary_type,
        hourly_rate=payload.hourly_rate,
    )
    if roles:
        set_user_roles(db, item, roles)
    write_op_log(
        db,
        request,
        user,
        module="system.user",
        action="create",
        object_type="user",
        object_id=item.id,
        detail=item.username,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{user_id}")
def get_api(user_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_user_by_id(db, user_id=user_id)
    if not item:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ok(_out(item))


@router.put("/{user_id}")
def update_api(
    user_id: int,
    payload: UserUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_user_by_id(db, user_id=user_id)
    if not item:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 普通管理员不可编辑超级管理员账号
    if item.is_superuser and not user.is_superuser:
        raise HTTPException(status_code=403, detail="普通管理员不可编辑超级管理员账号")
    # 仅超管可授予超管权限
    if payload.is_superuser is not None and payload.is_superuser and not user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可授予超管权限")
    if payload.department_id is not None:
        dept = get_department_by_id(db, department_id=payload.department_id)
        if not dept:
            raise HTTPException(status_code=400, detail="部门不存在")
    if payload.role_ids is not None:
        roles = []
        for rid in payload.role_ids:
            r = get_role_by_id(db, role_id=rid)
            if not r:
                raise HTTPException(status_code=400, detail=f"角色不存在: {rid}")
            roles.append(r)
        set_user_roles(db, item, roles)
    if payload.password is not None:
        set_password(db, item, payload.password)
    update_user(
        db,
        item,
        full_name=payload.full_name,
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
        department_id=payload.department_id,
        salary_type=payload.salary_type,
        hourly_rate=payload.hourly_rate,
    )
    write_op_log(
        db,
        request,
        user,
        module="system.user",
        action="update",
        object_type="user",
        object_id=item.id,
        detail=item.username,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{user_id}")
def delete_api(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_user_by_id(db, user_id=user_id)
    if not item:
        raise HTTPException(status_code=404, detail="用户不存在")
    if item.is_superuser:
        raise HTTPException(status_code=403, detail="不可禁用超级管理员账号")
    update_user(db, item, is_active=False)
    write_op_log(
        db,
        request,
        user,
        module="system.user",
        action="disable",
        object_type="user",
        object_id=item.id,
        detail=item.username,
    )
    db.commit()
    return ok()
