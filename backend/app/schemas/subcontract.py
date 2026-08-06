from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SubcontractOrderItemIn(BaseModel):
    sku_id: int
    process_id: int | None = None
    qty: int
    unit_price: Decimal | None = None
    remark: str | None = None


class SubcontractOrderItemOut(BaseModel):
    id: int
    order_id: int
    sku_id: int
    process_id: int | None
    qty: int
    unit_price: Decimal | None
    sent_qty: int
    received_qty: int
    remark: str | None
    sku_code: str | None = None
    sku_name: str | None = None
    process_name: str | None = None


class SubcontractOrderCreate(BaseModel):
    supplier_id: int
    code: str | None = None
    remark: str | None = None
    items: list[SubcontractOrderItemIn]


class SubcontractOrderOut(BaseModel):
    id: int
    supplier_id: int
    code: str
    status: str
    remark: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    supplier_name: str | None = None
    items: list[SubcontractOrderItemOut] = []


class SubcontractOrderBrief(BaseModel):
    id: int
    code: str
    status: str
    supplier_id: int
    supplier_name: str | None = None
    created_at: datetime


class SendLogIn(BaseModel):
    item_id: int
    qty: int
    remark: str | None = None


class ReceiveLogIn(BaseModel):
    item_id: int
    qty: int
    remark: str | None = None


class SendLogOut(BaseModel):
    id: int
    order_id: int
    item_id: int
    qty: int
    remark: str | None
    sent_by: int | None
    sent_at: datetime


class ReceiveLogOut(BaseModel):
    id: int
    order_id: int
    item_id: int
    qty: int
    remark: str | None
    received_by: int | None
    received_at: datetime
