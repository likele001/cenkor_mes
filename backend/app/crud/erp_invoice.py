# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""ERP 发票 CRUD"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.erp_invoice import Invoice, InvoiceItem


def list_invoices(
    db: Session,
    tenant_id: int,
    *,
    direction: str | None = None,
    invoice_type: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    supplier_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.tenant_id == tenant_id)
    if direction:
        stmt = stmt.where(Invoice.direction == direction)
    if invoice_type:
        stmt = stmt.where(Invoice.invoice_type == invoice_type)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if supplier_id:
        stmt = stmt.where(Invoice.supplier_id == supplier_id)
    if date_from:
        stmt = stmt.where(Invoice.invoice_date >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.invoice_date <= date_to)
    stmt = stmt.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def count_invoices(db: Session, tenant_id: int, **filters) -> int:
    stmt = select(Invoice.id).where(Invoice.tenant_id == tenant_id)
    if filters.get("direction"):
        stmt = stmt.where(Invoice.direction == filters["direction"])
    if filters.get("status"):
        stmt = stmt.where(Invoice.status == filters["status"])
    if filters.get("customer_id"):
        stmt = stmt.where(Invoice.customer_id == filters["customer_id"])
    if filters.get("supplier_id"):
        stmt = stmt.where(Invoice.supplier_id == filters["supplier_id"])
    return len(db.scalars(stmt).all())


def get_invoice(db: Session, tenant_id: int, invoice_id: int) -> Invoice | None:
    return db.scalar(
        select(Invoice)
        .where(Invoice.tenant_id == tenant_id, Invoice.id == invoice_id)
        .options(selectinload(Invoice.items))
    )


def invoice_code_exists(db: Session, tenant_id: int, code: str) -> bool:
    return db.scalar(select(Invoice.id).where(Invoice.tenant_id == tenant_id, Invoice.code == code)) is not None


def create_invoice(
    db: Session,
    tenant_id: int,
    *,
    code: str,
    invoice_no: str | None,
    direction: str,
    invoice_type: str,
    customer_id: int | None,
    supplier_id: int | None,
    statement_id: int | None,
    supplier_statement_id: int | None,
    order_id: int | None,
    purchase_order_id: int | None,
    invoice_date: date,
    tax_rate: Decimal,
    amount: Decimal,
    tax_amount: Decimal,
    total_amount: Decimal,
    remark: str | None,
    items: list[dict],
    created_by: int | None,
) -> Invoice:
    inv = Invoice(
        tenant_id=tenant_id,
        code=code,
        invoice_no=invoice_no,
        direction=direction,
        invoice_type=invoice_type,
        customer_id=customer_id,
        supplier_id=supplier_id,
        statement_id=statement_id,
        supplier_statement_id=supplier_statement_id,
        order_id=order_id,
        purchase_order_id=purchase_order_id,
        invoice_date=invoice_date,
        tax_rate=tax_rate,
        amount=amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        remark=remark,
        status="draft",
        created_by=created_by,
    )
    inv.items = [
        InvoiceItem(tenant_id=tenant_id, **{k: v for k, v in it.items() if k != "id"})
        for it in items
    ]
    db.add(inv)
    db.flush()
    return inv


def update_invoice(db: Session, inv: Invoice, data: dict) -> Invoice:
    for k, v in data.items():
        if k == "items":
            continue
        if hasattr(inv, k) and v is not None:
            setattr(inv, k, v)
    if "items" in data and data["items"] is not None:
        inv.items.clear()
        inv.items = [InvoiceItem(tenant_id=inv.tenant_id, **it) for it in data["items"]]
    db.flush()
    return inv


def set_invoice_status(db: Session, inv: Invoice, status: str) -> Invoice:
    inv.status = status
    db.flush()
    return inv
