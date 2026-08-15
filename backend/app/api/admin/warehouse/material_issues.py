from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.warehouse import get_stock
from app.crud.material_issue import (
    cancel_issue,
    cancel_return,
    confirm_return,
    create_issue,
    create_return,
    get_issue_by_id,
    get_return_by_id,
    issue_materials,
    list_issues,
    list_returns,
)
from app.models.material_issue import MaterialIssue, MaterialReturn
from app.models.user import User
from app.services.code_generator import BizType, resolve_code

router = APIRouter(dependencies=[Depends(require_permissions(["warehouse.manage"]))])


class IssueItemIn(BaseModel):
    material_id: int = Field(ge=1)
    sku_id: int = Field(ge=1)
    qty: int = Field(ge=1)


class IssueCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    warehouse_id: int = Field(ge=1)
    work_order_id: int | None = Field(default=None, ge=1)
    remark: str | None = Field(default=None, max_length=255)
    items: list[IssueItemIn] = Field(min_length=1)


class ReturnItemIn(BaseModel):
    material_id: int = Field(ge=1)
    sku_id: int = Field(ge=1)
    qty: int = Field(ge=1)
    issue_item_id: int | None = Field(default=None, ge=1)


class ReturnCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    warehouse_id: int = Field(ge=1)
    work_order_id: int | None = Field(default=None, ge=1)
    issue_id: int | None = Field(default=None, ge=1)
    remark: str | None = Field(default=None, max_length=255)
    items: list[ReturnItemIn] = Field(min_length=1)


def _issue_out(x: MaterialIssue) -> dict:
    wo = getattr(x, "work_order", None)
    wh = getattr(x, "warehouse", None)
    total_qty = sum(it.qty for it in x.items) if x.items else 0
    total_cost = sum(it.cost_amount for it in x.items) if x.items else 0
    return {
        "id": x.id,
        "code": x.code,
        "status": x.status,
        "warehouse_id": x.warehouse_id,
        "warehouse_name": wh.name if wh else None,
        "work_order_id": x.work_order_id,
        "work_order_code": f"WO#{wo.id}" if wo else None,
        "total_qty": total_qty,
        "total_cost": float(total_cost),
        "issued_at": x.issued_at,
        "remark": x.remark,
        "created_at": x.created_at,
    }


def _issue_detail_out(x: MaterialIssue) -> dict:
    d = _issue_out(x)
    d["items"] = [
        {
            "id": it.id,
            "material_id": it.material_id,
            "material_code": it.material.code if it.material else None,
            "material_name": it.material.name if it.material else None,
            "sku_id": it.sku_id,
            "sku_code": it.sku.code if it.sku else None,
            "qty": it.qty,
            "unit_cost": float(it.unit_cost),
            "cost_amount": float(it.cost_amount),
        }
        for it in (x.items or [])
    ]
    return d


def _return_out(x: MaterialReturn) -> dict:
    wo = getattr(x, "work_order", None)
    wh = getattr(x, "warehouse", None)
    iss = getattr(x, "issue", None)
    total_qty = sum(it.qty for it in x.items) if x.items else 0
    total_cost = sum(it.cost_amount for it in x.items) if x.items else 0
    return {
        "id": x.id,
        "code": x.code,
        "status": x.status,
        "warehouse_id": x.warehouse_id,
        "warehouse_name": wh.name if wh else None,
        "work_order_id": x.work_order_id,
        "work_order_code": f"WO#{wo.id}" if wo else None,
        "issue_id": x.issue_id,
        "issue_code": iss.code if iss else None,
        "total_qty": total_qty,
        "total_cost": float(total_cost),
        "returned_at": x.returned_at,
        "remark": x.remark,
        "created_at": x.created_at,
    }


def _return_detail_out(x: MaterialReturn) -> dict:
    d = _return_out(x)
    d["items"] = [
        {
            "id": it.id,
            "issue_item_id": it.issue_item_id,
            "material_id": it.material_id,
            "material_code": it.material.code if it.material else None,
            "material_name": it.material.name if it.material else None,
            "sku_id": it.sku_id,
            "sku_code": it.sku.code if it.sku else None,
            "qty": it.qty,
            "unit_cost": float(it.unit_cost),
            "cost_amount": float(it.cost_amount),
        }
        for it in (x.items or [])
    ]
    return d


# ── 领料单 ──

@router.get("/issues")
def list_issues_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    work_order_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_issues(db, warehouse_id=warehouse_id, work_order_id=work_order_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_issue_out(x) for x in items]})


@router.get("/issues/{issue_id}")
def get_issue_api(
    issue_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    x = get_issue_by_id(db, issue_id=issue_id)
    if not x:
        raise HTTPException(status_code=404, detail="领料单不存在")
    return ok(_issue_detail_out(x))


@router.post("/issues")
def create_issue_api(
    payload: IssueCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = resolve_code(
        db,
        biz_type=BizType.MATERIAL_ISSUE,
        code=payload.code,
        exists=lambda c: db.scalar(__import__("sqlalchemy").select(MaterialIssue.id).where(MaterialIssue.code == c)) is not None,
        duplicate_msg="领料单号已存在",
    )
    issue = create_issue(
        db,
        code=code,
        warehouse_id=payload.warehouse_id,
        items=[it.model_dump() for it in payload.items],
        work_order_id=payload.work_order_id,
        remark=payload.remark,
        created_by=user.id,
    )
    db.commit()
    x = get_issue_by_id(db, issue_id=issue.id)
    return ok(_issue_detail_out(x if x else issue))


@router.post("/issues/{issue_id}/issue")
def issue_api(
    issue_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    x = get_issue_by_id(db, issue_id=issue_id)
    if not x:
        raise HTTPException(status_code=404, detail="领料单不存在")
    try:
        x = issue_materials(db, issue=x, issued_by=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    x2 = get_issue_by_id(db, issue_id=issue_id)
    return ok(_issue_detail_out(x2 if x2 else x))


@router.post("/issues/{issue_id}/cancel")
def cancel_issue_api(
    issue_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    x = get_issue_by_id(db, issue_id=issue_id)
    if not x:
        raise HTTPException(status_code=404, detail="领料单不存在")
    try:
        x = cancel_issue(db, issue=x)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return ok(_issue_out(x))


# ── 退料单 ──

@router.get("/returns")
def list_returns_api(
    warehouse_id: int | None = Query(default=None, ge=1),
    work_order_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_returns(db, warehouse_id=warehouse_id, work_order_id=work_order_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_return_out(x) for x in items]})


@router.get("/returns/{return_id}")
def get_return_api(
    return_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    x = get_return_by_id(db, return_id=return_id)
    if not x:
        raise HTTPException(status_code=404, detail="退料单不存在")
    return ok(_return_detail_out(x))


@router.post("/returns")
def create_return_api(
    payload: ReturnCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = resolve_code(
        db,
        biz_type=BizType.MATERIAL_RETURN,
        code=payload.code,
        exists=lambda c: db.scalar(__import__("sqlalchemy").select(MaterialReturn.id).where(MaterialReturn.code == c)) is not None,
        duplicate_msg="退料单号已存在",
    )
    ret = create_return(
        db,
        code=code,
        warehouse_id=payload.warehouse_id,
        items=[it.model_dump() for it in payload.items],
        work_order_id=payload.work_order_id,
        issue_id=payload.issue_id,
        remark=payload.remark,
        created_by=user.id,
    )
    db.commit()
    x = get_return_by_id(db, return_id=ret.id)
    return ok(_return_detail_out(x if x else ret))


@router.post("/returns/{return_id}/confirm")
def confirm_return_api(
    return_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    x = get_return_by_id(db, return_id=return_id)
    if not x:
        raise HTTPException(status_code=404, detail="退料单不存在")
    try:
        x = confirm_return(db, ret=x, returned_by=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    x2 = get_return_by_id(db, return_id=return_id)
    return ok(_return_detail_out(x2 if x2 else x))


@router.post("/returns/{return_id}/cancel")
def cancel_return_api(
    return_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    x = get_return_by_id(db, return_id=return_id)
    if not x:
        raise HTTPException(status_code=404, detail="退料单不存在")
    try:
        x = cancel_return(db, ret=x)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return ok(_return_out(x))
