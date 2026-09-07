from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.erp_invoice import (
    count_invoices,
    create_invoice,
    get_invoice,
    invoice_code_exists,
    list_invoices,
    set_invoice_status,
    update_invoice,
)
from app.models.erp_invoice import Invoice, InvoiceItem
from app.models.user import User
from app.schemas.erp_invoice import InvoiceCreateIn, InvoiceUpdateIn
from app.services.code_generator import BizType, resolve_code


router = APIRouter()


def _item_out(x: InvoiceItem) -> dict:
    return {
        "id": x.id,
        "line_no": x.line_no,
        "order_id": x.order_id,
        "purchase_order_id": x.purchase_order_id,
        "sku_id": x.sku_id,
        "material_id": x.material_id,
        "qty": float(x.qty),
        "unit_price": float(x.unit_price),
        "amount": float(x.amount),
        "tax_rate": float(x.tax_rate),
        "tax_amount": float(x.tax_amount),
        "total_amount": float(x.total_amount),
    }


def _out(x: Invoice, with_items: bool = False) -> dict:
    d = {
        "id": x.id,
        "tenant_id": x.tenant_id,
        "code": x.code,
        "invoice_no": x.invoice_no,
        "direction": x.direction,
        "invoice_type": x.invoice_type,
        "customer_id": x.customer_id,
        "supplier_id": x.supplier_id,
        "statement_id": x.statement_id,
        "supplier_statement_id": x.supplier_statement_id,
        "order_id": x.order_id,
        "purchase_order_id": x.purchase_order_id,
        "invoice_date": str(x.invoice_date),
        "tax_rate": float(x.tax_rate),
        "amount": float(x.amount),
        "tax_amount": float(x.tax_amount),
        "total_amount": float(x.total_amount),
        "status": x.status,
        "remark": x.remark,
        "created_by": x.created_by,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }
    if with_items:
        d["items"] = [_item_out(it) for it in x.items]
    return d


@router.get("")
def list_api(
    direction: str | None = Query(default=None),
    invoice_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: int | None = Query(default=None, ge=1),
    supplier_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_invoices(
        db, user.tenant_id,
        direction=direction, invoice_type=invoice_type, status=status,
        customer_id=customer_id, supplier_id=supplier_id,
        date_from=date_from, date_to=date_to, offset=offset, limit=limit,
    )
    total = count_invoices(
        db, user.tenant_id,
        direction=direction, status=status, customer_id=customer_id, supplier_id=supplier_id,
    )
    return ok({"items": [_out(x) for x in items], "total": total})


@router.get("/{invoice_id}")
def detail_api(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    inv = get_invoice(db, user.tenant_id, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    return ok(_out(inv, with_items=True))


@router.post("")
def create_api(
    body: InvoiceCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = resolve_code(
        db,
        tenant_id=user.tenant_id,
        biz_type=BizType.INVOICE,
        code=body.code,
        exists=lambda c: invoice_code_exists(db, user.tenant_id, c),
        duplicate_msg="发票单号已存在",
    )
    inv = create_invoice(
        db, user.tenant_id,
        code=code, invoice_no=body.invoice_no, direction=body.direction,
        invoice_type=body.invoice_type,
        customer_id=body.customer_id, supplier_id=body.supplier_id,
        statement_id=body.statement_id, supplier_statement_id=body.supplier_statement_id,
        order_id=body.order_id, purchase_order_id=body.purchase_order_id,
        invoice_date=body.invoice_date, tax_rate=body.tax_rate,
        amount=body.amount, tax_amount=body.tax_amount, total_amount=body.total_amount,
        remark=body.remark,
        items=[it.model_dump() for it in body.items],
        created_by=user.id,
    )
    db.commit()
    return ok({"id": inv.id, "code": inv.code}, "创建成功")


@router.put("/{invoice_id}")
def update_api(
    invoice_id: int,
    body: InvoiceUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    inv = get_invoice(db, user.tenant_id, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    if inv.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可修改")
    data = body.model_dump(exclude_unset=True)
    if data.get("items") is not None:
        data["items"] = [it.model_dump() for it in data["items"]]
    inv = update_invoice(db, inv, data)
    db.commit()
    return ok({"id": inv.id}, "已更新")


@router.delete("/{invoice_id}")
def delete_api(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    inv = get_invoice(db, user.tenant_id, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    if inv.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可删除")
    db.delete(inv)
    db.commit()
    return ok(msg="已删除")


@router.post("/{invoice_id}/post")
def post_api(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    inv = get_invoice(db, user.tenant_id, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    if inv.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿可过账")
    set_invoice_status(db, inv, "posted")
    db.commit()
    return ok({"id": inv.id}, "已过账")


@router.post("/{invoice_id}/void")
def void_api(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    inv = get_invoice(db, user.tenant_id, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    if inv.status == "void":
        raise HTTPException(status_code=400, detail="发票已作废")
    set_invoice_status(db, inv, "void")
    db.commit()
    return ok({"id": inv.id}, "已作废")
