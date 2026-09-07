from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class InvoiceItemIn(BaseModel):
    line_no: int = Field(default=1, ge=1)
    order_id: int | None = Field(default=None, ge=1)
    purchase_order_id: int | None = Field(default=None, ge=1)
    sku_id: int | None = Field(default=None, ge=1)
    material_id: int | None = Field(default=None, ge=1)
    qty: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    total_amount: Decimal = Field(default=Decimal("0"), ge=0)


class InvoiceCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    invoice_no: str | None = Field(default=None, max_length=64)
    direction: Literal["out", "in"]
    invoice_type: Literal["special", "general"] = "special"
    customer_id: int | None = Field(default=None, ge=1)
    supplier_id: int | None = Field(default=None, ge=1)
    statement_id: int | None = Field(default=None, ge=1)
    supplier_statement_id: int | None = Field(default=None, ge=1)
    order_id: int | None = Field(default=None, ge=1)
    purchase_order_id: int | None = Field(default=None, ge=1)
    invoice_date: date
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0)
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    total_amount: Decimal = Field(default=Decimal("0"), ge=0)
    remark: str | None = Field(default=None, max_length=1000)
    items: list[InvoiceItemIn] = Field(default_factory=list)


class InvoiceUpdateIn(BaseModel):
    invoice_no: str | None = Field(default=None, max_length=64)
    invoice_type: Literal["special", "general"] | None = None
    customer_id: int | None = Field(default=None, ge=1)
    supplier_id: int | None = Field(default=None, ge=1)
    statement_id: int | None = Field(default=None, ge=1)
    supplier_statement_id: int | None = Field(default=None, ge=1)
    order_id: int | None = Field(default=None, ge=1)
    purchase_order_id: int | None = Field(default=None, ge=1)
    invoice_date: date | None = None
    tax_rate: Decimal | None = Field(default=None, ge=0)
    amount: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal | None = Field(default=None, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)
    remark: str | None = Field(default=None, max_length=1000)
    items: list[InvoiceItemIn] | None = None
