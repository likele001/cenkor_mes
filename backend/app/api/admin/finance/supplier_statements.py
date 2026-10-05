# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.supplier import get_supplier_by_id
from app.crud.purchase_order import get_purchase_order_by_id
from app.crud import statement_payment as sp_crud
from app.crud.supplier_statement import (
    calc_purchase_order_amount,
    create_supplier_statement,
    get_supplier_statement_by_code,
    get_supplier_statement_by_id,
    get_supplier_payables,
    list_supplier_statements,
    update_supplier_statement_status,
)
from app.models.supplier_statement import SupplierStatement
from app.models.user import User
from app.schemas.supplier_statement import SupplierStatementCreateIn
from app.schemas.statement_payment import StatementPaymentCreateIn
from app.services.code_generator import BizType, resolve_code

router = APIRouter(dependencies=[Depends(require_permissions(["finance.manage"]))])


def _out(x: SupplierStatement) -> dict:
    sup = getattr(x, "supplier", None)
    return {
        "id": x.id,
        "supplier_id": x.supplier_id,
        "supplier_code": sup.code if sup else None,
        "supplier_name": sup.name if sup else None,
        "code": x.code,
        "period_start": str(x.period_start) if x.period_start else None,
        "period_end": str(x.period_end) if x.period_end else None,
        "total_amount": float(x.total_amount),
        "paid_amount": float(x.paid_amount or 0),
        "balance": float(Decimal(str(x.total_amount)) - Decimal(str(x.paid_amount or 0))),
        "due_date": str(x.due_date) if x.due_date else None,
        "status": x.status,
        "remark": x.remark,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


@router.get("/supplier-statements")
def list_api(
    supplier_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_supplier_statements(db, supplier_id=supplier_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_out(x) for x in items]})


@router.get("/supplier-statements/payables")
def payables_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ok({"items": get_supplier_payables(db)})


@router.post("/supplier-statements")
def create_api(
    payload: SupplierStatementCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sup = get_supplier_by_id(db, supplier_id=payload.supplier_id)
    if not sup or not sup.is_active:
        raise HTTPException(status_code=400, detail="供应商不存在")

    amounts: list[tuple[int, Decimal]] = []
    for oid in payload.order_ids:
        order = get_purchase_order_by_id(db, order_id=oid, with_items=True)
        if not order:
            raise HTTPException(status_code=400, detail=f"采购单 {oid} 不存在")
        if order.supplier_id != payload.supplier_id:
            raise HTTPException(status_code=400, detail=f"采购单 {oid} 不属于该供应商")
        try:
            amt = calc_purchase_order_amount(db, order=order)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        amounts.append((oid, amt))

    stmt_code = resolve_code(
        db,
        biz_type=BizType.SUPPLIER_STATEMENT,
        code=payload.code,
        exists=lambda c: get_supplier_statement_by_code(db, c) is not None,
        duplicate_msg="供应商对账单号已存在",
    )
    stmt = create_supplier_statement(
        db,
        supplier_id=payload.supplier_id,
        code=stmt_code,
        order_amounts=amounts,
        period_start=payload.period_start,
        period_end=payload.period_end,
        remark=payload.remark,
        created_by=user.id,
        due_date=payload.due_date,
    )
    db.commit()
    stmt2 = get_supplier_statement_by_id(db, statement_id=stmt.id)
    return ok(_out(stmt2 if stmt2 else stmt))


@router.post("/supplier-statements/{statement_id}/confirm")
def confirm_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_supplier_statement_by_id(db, statement_id=statement_id)
    if not item:
        raise HTTPException(status_code=400, detail="供应商对账单不存在")
    if item.status != "draft":
        raise HTTPException(status_code=400, detail="状态不允许确认")
    update_supplier_statement_status(db, item, "confirmed", operator=user.id, action="confirm")
    sp_crud.create_accrual_ledger(
        db,
        statement_type="supplier_statement",
        stmt=item,
        biz_date=datetime.now().date(),
        created_by=user.id,
        remark=f"供应商对账单{item.code}确认应付",
    )
    db.commit()
    return ok({"id": item.id, "status": "confirmed"})


@router.post("/supplier-statements/{statement_id}/mark-paid")
def mark_paid_api(
    statement_id: int,
    paid_date: date | None = Query(default=None, description="付款日，默认今天"),
    method: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_supplier_statement_by_id(db, statement_id=statement_id)
    if not item:
        raise HTTPException(status_code=400, detail="供应商对账单不存在")
    if item.status == "draft":
        raise HTTPException(status_code=400, detail="需先确认对账单")
    if item.status == "paid":
        return ok({"id": item.id, "status": item.status, "updated_at": item.updated_at})
    try:
        sp_crud.settle_statement(
            db,
            statement_type="supplier_statement",
            statement_id=statement_id,
            paid_date=paid_date,
            method=method,
            remark=f"供应商对账单{item.code}整单付款",
            created_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    db.refresh(item)
    return ok({"id": item.id, "status": item.status, "updated_at": item.updated_at})


@router.get("/supplier-statements/{statement_id}")
def get_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_supplier_statement_by_id(db, statement_id=statement_id)
    if not item:
        raise HTTPException(status_code=400, detail="供应商对账单不存在")
    data = _out(item)
    data["supplier"] = {"id": item.supplier.id, "code": item.supplier.code, "name": item.supplier.name} if item.supplier else None
    data["items"] = [
        {
            "purchase_order_id": si.purchase_order_id,
            "purchase_order_code": si.purchase_order.code if si.purchase_order else None,
            "amount": float(si.amount),
        }
        for si in item.items
    ]
    return ok(data)


def _ap_payment_out(p) -> dict:
    return {
        "id": p.id,
        "statement_id": p.statement_id,
        "amount": float(p.amount),
        "paid_date": str(p.paid_date) if p.paid_date else None,
        "method": p.method,
        "remark": p.remark,
        "created_by": p.created_by,
        "created_at": p.created_at,
    }


@router.post("/supplier-statements/{statement_id}/payments")
def ap_create_payment_api(
    statement_id: int,
    payload: StatementPaymentCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        p = sp_crud.create_payment(
            db,
            statement_type="supplier_statement",
            statement_id=statement_id,
            amount=payload.amount,
            paid_date=payload.paid_date,
            method=payload.method,
            remark=payload.remark,
            created_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    item = get_supplier_statement_by_id(db, statement_id=statement_id)
    return ok({"payment": _ap_payment_out(p), "statement": _out(item)})


@router.get("/supplier-statements/{statement_id}/payments")
def ap_list_payments_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = sp_crud.list_payments(db, "supplier_statement", statement_id)
    return ok({"items": [_ap_payment_out(p) for p in rows]})
