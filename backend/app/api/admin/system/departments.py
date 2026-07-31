from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.department import (
    create_department,
    get_department_by_code,
    get_department_by_id,
    list_departments,
    update_department,
)
from app.models.user import User
from app.schemas.department import DepartmentCreateIn, DepartmentUpdateIn
from app.services.code_generator import BizType, resolve_code


router = APIRouter(dependencies=[Depends(require_permissions(["department.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "name": x.name,
        "parent_id": x.parent_id,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_departments(db, keyword=keyword, offset=offset, limit=limit, include_inactive=include_inactive)
    return ok({"items": [_out(x) for x in items]})


@router.post("")
def create_api(
    payload: DepartmentCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dept_code = resolve_code(
        db,
        biz_type=BizType.DEPARTMENT,
        code=payload.code,
        exists=lambda c: get_department_by_code(db, c) is not None,
        duplicate_msg="部门编码已存在",
    )
    if payload.parent_id is not None:
        parent = get_department_by_id(db, department_id=payload.parent_id)
        if not parent:
            raise HTTPException(status_code=400, detail="上级部门不存在")
    item = create_department(
        db,
        code=dept_code,
        name=payload.name,
        parent_id=payload.parent_id,
        is_active=payload.is_active,
    )
    write_op_log(
        db,
        request,
        user,
        module="system.department",
        action="create",
        object_type="department",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{department_id}")
def get_api(department_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_department_by_id(db, department_id=department_id)
    if not item:
        raise HTTPException(status_code=404, detail="部门不存在")
    return ok(_out(item))


@router.put("/{department_id}")
def update_api(
    department_id: int,
    payload: DepartmentUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_department_by_id(db, department_id=department_id)
    if not item:
        raise HTTPException(status_code=404, detail="部门不存在")
    if payload.code is not None:
        exists = get_department_by_code(db, code=payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="部门编码已存在")
    if payload.parent_id is not None:
        parent = get_department_by_id(db, department_id=payload.parent_id)
        if not parent:
            raise HTTPException(status_code=400, detail="上级部门不存在")
    update_department(
        db,
        item,
        code=payload.code,
        name=payload.name,
        parent_id=payload.parent_id,
        is_active=payload.is_active,
    )
    write_op_log(
        db,
        request,
        user,
        module="system.department",
        action="update",
        object_type="department",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{department_id}")
def delete_api(
    department_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_department_by_id(db, department_id=department_id)
    if not item:
        raise HTTPException(status_code=404, detail="部门不存在")
    update_department(db, item, is_active=False)
    write_op_log(
        db,
        request,
        user,
        module="system.department",
        action="disable",
        object_type="department",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    return ok()
