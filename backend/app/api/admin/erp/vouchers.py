# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.erp_ledger import (
    create_voucher,
    get_voucher,
    list_vouchers,
    set_voucher_status,
    update_voucher,
    voucher_code_exists,
)
from app.models.user import User
from app.schemas.erp_ledger import VoucherCreateIn, VoucherUpdateIn
from app.services.code_generator import BizType, resolve_code


router = APIRouter()


def _entry_out(x) -> dict:
    return {
        "id": x.id,
        "line_no": x.line_no,
        "account_subject_id": x.account_subject_id,
        "summary": x.summary,
        "debit_amount": float(x.debit_amount or 0),
        "credit_amount": float(x.credit_amount or 0),
        "party_type": x.party_type,
        "party_id": x.party_id,
    }


def _out(x, with_entries: bool = False) -> dict:
    d = {
        "id": x.id,
        "tenant_id": x.tenant_id,
        "code": x.code,
        "voucher_date": str(x.voucher_date),
        "voucher_type": x.voucher_type,
        "summary": x.summary,
        "amount": float(x.amount or 0),
        "period": x.period,
        "status": x.status,
        "source_type": x.source_type,
        "source_id": x.source_id,
        "created_by": x.created_by,
        "posted_by": x.posted_by,
        "posted_at": x.posted_at,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }
    if with_entries:
        d["entries"] = [_entry_out(e) for e in x.entries]
    return d


def _validate_balanced(entries: list[dict]) -> Decimal:
    total_debit = sum((e.get("debit_amount") or Decimal("0")) for e in entries)
    total_credit = sum((e.get("credit_amount") or Decimal("0")) for e in entries)
    if total_debit != total_credit:
        raise HTTPException(status_code=400, detail=f"借贷不平衡：借 {total_debit} ≠ 贷 {total_credit}")
    if total_debit <= 0:
        raise HTTPException(status_code=400, detail="凭证金额必须大于 0")
    return total_debit


@router.get("")
def list_api(
    period: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_vouchers(
        db, user.tenant_id,
        period=period, status=status, date_from=date_from, date_to=date_to,
        offset=offset, limit=limit,
    )
    return ok({"items": [_out(x) for x in items]})


@router.get("/{voucher_id}")
def detail_api(
    voucher_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = get_voucher(db, user.tenant_id, voucher_id)
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    return ok(_out(v, with_entries=True))


@router.post("")
def create_api(
    body: VoucherCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entries = [e.model_dump() for e in body.entries]
    amount = _validate_balanced(entries)
    code = resolve_code(
        db,
        tenant_id=user.tenant_id,
        biz_type=BizType.VOUCHER,
        code=body.code,
        exists=lambda c: voucher_code_exists(db, user.tenant_id, c),
        duplicate_msg="凭证号已存在",
    )
    period = body.voucher_date.strftime("%Y-%m")
    v = create_voucher(
        db, user.tenant_id,
        code=code, voucher_date=body.voucher_date, voucher_type=body.voucher_type,
        summary=body.summary, amount=amount, period=period, entries=entries,
        source_type=body.source_type, source_id=body.source_id, created_by=user.id,
    )
    db.commit()
    return ok({"id": v.id, "code": v.code}, "创建成功")


@router.put("/{voucher_id}")
def update_api(
    voucher_id: int,
    body: VoucherUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = get_voucher(db, user.tenant_id, voucher_id)
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿可修改")
    data = body.model_dump(exclude_unset=True)
    if data.get("entries") is not None:
        entries = [e.model_dump() for e in data["entries"]]
        _validate_balanced(entries)
        data["entries"] = entries
    if data.get("voucher_date"):
        data["period"] = data["voucher_date"].strftime("%Y-%m")
    v = update_voucher(db, v, data)
    db.commit()
    return ok({"id": v.id}, "已更新")


@router.delete("/{voucher_id}")
def delete_api(
    voucher_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = get_voucher(db, user.tenant_id, voucher_id)
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿可删除")
    db.delete(v)
    db.commit()
    return ok(msg="已删除")


@router.post("/{voucher_id}/post")
def post_api(
    voucher_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = get_voucher(db, user.tenant_id, voucher_id)
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿可过账")
    set_voucher_status(db, v, "posted", posted_by=user.id)
    db.commit()
    return ok({"id": v.id}, "已过账")


@router.post("/{voucher_id}/unpost")
def unpost_api(
    voucher_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = get_voucher(db, user.tenant_id, voucher_id)
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "posted":
        raise HTTPException(status_code=400, detail="仅已过账凭证可反过账")
    set_voucher_status(db, v, "draft")
    db.commit()
    return ok({"id": v.id}, "已反过账")
