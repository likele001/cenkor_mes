from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.system_rbac import (
    get_permission_by_code,
    get_role_by_code,
    get_role_by_id,
    list_roles,
    create_role,
    delete_role,
    set_role_permissions,
    update_role,
)
from app.models.user import User
from app.schemas.system_rbac import RoleCreateIn, RoleSetPermissionsIn, RoleUpdateIn
from app.tasks._sync_excel import make_excel_response


router = APIRouter(dependencies=[Depends(require_permissions(["role.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "name": x.name,
        "permission_codes": [p.code for p in x.permissions],
    }


@router.get("")
def list_api(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_roles(db, offset=offset, limit=limit)
    return ok({"items": [_out(x) for x in items]})


@router.get("/export")
def export_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_roles(db, offset=0, limit=999999)
    rows = []
    for x in items:
        rows.append([x.name, x.code, "", "是"])
    return make_excel_response(
        headers=["角色名称", "角色编码", "描述", "启用"],
        rows=rows,
        filename="roles.xlsx",
        sheet_name="角色",
    )


@router.post("")
def create_api(
    payload: RoleCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exists = get_role_by_code(db, code=payload.code)
    if exists:
        raise HTTPException(status_code=400, detail="角色编码已存在")
    item = create_role(db, code=payload.code, name=payload.name)
    write_op_log(
        db,
        request,
        user,
        module="system.role",
        action="create",
        object_type="role",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{role_id}")
def get_api(role_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_role_by_id(db, role_id=role_id)
    if not item:
        raise HTTPException(status_code=404, detail="角色不存在")
    return ok(_out(item))


@router.put("/{role_id}")
def update_api(
    role_id: int,
    payload: RoleUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_role_by_id(db, role_id=role_id)
    if not item:
        raise HTTPException(status_code=404, detail="角色不存在")
    if payload.code is not None:
        exists = get_role_by_code(db, code=payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="角色编码已存在")
    update_role(db, item, code=payload.code, name=payload.name)
    write_op_log(
        db,
        request,
        user,
        module="system.role",
        action="update",
        object_type="role",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.put("/{role_id}/permissions")
def set_permissions_api(
    role_id: int,
    payload: RoleSetPermissionsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role = get_role_by_id(db, role_id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    perms = []
    for code in payload.permission_codes:
        p = get_permission_by_code(db, code)
        if not p:
            raise HTTPException(status_code=400, detail=f"权限点不存在: {code}")
        perms.append(p)
    set_role_permissions(db, role, perms)
    write_op_log(
        db,
        request,
        user,
        module="system.role",
        action="set_permissions",
        object_type="role",
        object_id=role.id,
        detail=",".join(sorted(payload.permission_codes)),
    )
    db.commit()
    db.refresh(role)
    return ok(_out(role))


@router.delete("/{role_id}")
def delete_api(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_role_by_id(db, role_id=role_id)
    if not item:
        raise HTTPException(status_code=404, detail="角色不存在")
    write_op_log(
        db,
        request,
        user,
        module="system.role",
        action="delete",
        object_type="role",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    delete_role(db, item)
    db.commit()
    return ok()
