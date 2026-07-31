from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.system_rbac import (
    create_permission,
    delete_permission,
    get_permission_by_code,
    get_permission_by_id,
    list_permissions,
    update_permission,
)
from app.models.user import User
from app.schemas.system_rbac import PermissionCreateIn, PermissionUpdateIn


router = APIRouter(dependencies=[Depends(require_permissions(["permission.manage"]))])


def _out(x) -> dict:
    return {"id": x.id, "code": x.code, "name": x.name}


@router.get("")
def list_api(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = list_permissions(db, offset=offset, limit=limit)
    return ok({"items": [_out(x) for x in items]})


@router.post("")
def create_api(
    payload: PermissionCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限")
    exists = get_permission_by_code(db, payload.code)
    if exists:
        raise HTTPException(status_code=400, detail="权限点编码已存在")
    item = create_permission(db, payload.code, payload.name)
    write_op_log(
        db,
        request,
        user,
        module="system.permission",
        action="create",
        object_type="permission",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.put("/{permission_id}")
def update_api(
    permission_id: int,
    payload: PermissionUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限")
    item = get_permission_by_id(db, permission_id)
    if not item:
        raise HTTPException(status_code=404, detail="权限点不存在")
    if payload.code is not None:
        exists = get_permission_by_code(db, payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="权限点编码已存在")
    update_permission(db, item, code=payload.code, name=payload.name)
    write_op_log(
        db,
        request,
        user,
        module="system.permission",
        action="update",
        object_type="permission",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{permission_id}")
def delete_api(
    permission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="无权限")
    item = get_permission_by_id(db, permission_id)
    if not item:
        raise HTTPException(status_code=404, detail="权限点不存在")
    write_op_log(
        db,
        request,
        user,
        module="system.permission",
        action="delete",
        object_type="permission",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    delete_permission(db, item)
    db.commit()
    return ok()
