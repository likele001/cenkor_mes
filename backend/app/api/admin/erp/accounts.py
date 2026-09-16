# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.erp_ledger import (
    account_code_exists,
    account_has_vouchers,
    create_account,
    delete_account,
    get_account,
    list_accounts,
    update_account,
)
from app.models.user import User
from app.schemas.erp_ledger import AccountSubjectCreateIn, AccountSubjectUpdateIn


router = APIRouter()


def _out(x) -> dict:
    return {
        "id": x.id,
        "tenant_id": x.tenant_id,
        "code": x.code,
        "name": x.name,
        "subject_type": x.subject_type,
        "direction": x.direction,
        "parent_id": x.parent_id,
        "is_active": bool(x.is_active),
        "opening_balance": float(x.opening_balance or 0),
        "remark": x.remark,
        "created_at": x.created_at,
    }


@router.get("")
def list_api(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_accounts(db, user.tenant_id, active_only=active_only)
    return ok({"items": [_out(x) for x in items]})


@router.get("/options")
def options_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_accounts(db, user.tenant_id, active_only=True)
    return ok([{"id": x.id, "code": x.code, "name": x.name, "direction": x.direction} for x in items])


@router.post("")
def create_api(
    body: AccountSubjectCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if account_code_exists(db, user.tenant_id, body.code):
        raise HTTPException(status_code=400, detail="科目编码已存在")
    acct = create_account(db, user.tenant_id, body.model_dump())
    db.commit()
    return ok({"id": acct.id}, "创建成功")


@router.put("/{account_id}")
def update_api(
    account_id: int,
    body: AccountSubjectUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    acct = get_account(db, user.tenant_id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="科目不存在")
    data = body.model_dump(exclude_unset=True)
    if "code" in data and account_code_exists(db, user.tenant_id, data["code"], exclude_id=acct.id):
        raise HTTPException(status_code=400, detail="科目编码已存在")
    acct = update_account(db, acct, data)
    db.commit()
    return ok({"id": acct.id}, "已更新")


@router.delete("/{account_id}")
def delete_api(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    acct = get_account(db, user.tenant_id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="科目不存在")
    if account_has_vouchers(db, user.tenant_id, account_id):
        raise HTTPException(status_code=400, detail="科目已被凭证引用，无法删除")
    delete_account(db, acct)
    db.commit()
    return ok(msg="已删除")
