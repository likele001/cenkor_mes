from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseOrderItemIn(BaseModel):
    material_id: int = Field(ge=1)
    qty: int = Field(ge=0)
    unit_price: Decimal | None = None
    remark: str | None = None


class PurchaseOrderCreateIn(BaseModel):
    supplier_id: int = Field(ge=1)
    code: str | None = Field(default=None, max_length=64)
    remark: str | None = None
    items: list[PurchaseOrderItemIn] = Field(default_factory=list)


class PurchaseOrderReceiveItemIn(BaseModel):
    item_id: int = Field(ge=1)
    receive_qty: int = Field(ge=0)
    batch_no: str | None = Field(default=None, max_length=64, description="批次号/炉号")


class PurchaseOrderReceiveIn(BaseModel):
    warehouse_id: int = Field(ge=1)
    items: list[PurchaseOrderReceiveItemIn] | None = None


class PurchaseOrderReturnItemIn(BaseModel):
    item_id: int = Field(ge=1)
    return_qty: int = Field(ge=0)


class PurchaseOrderReturnIn(BaseModel):
    warehouse_id: int = Field(ge=1)
    items: list[PurchaseOrderReturnItemIn]


class PurchaseOrderItemOut(BaseModel):
    id: int
    material_id: int
    material_code: str | None
    material_name: str | None
    qty: int
    received_qty: int
    returned_qty: int
    unit_price: Decimal | None
    remark: str | None


class PurchaseOrderOut(BaseModel):
    id: int
    supplier_id: int
    supplier_code: str | None
    supplier_name: str | None
    code: str
    status: str
    remark: str | None
    confirmed_at: datetime | None
    confirmed_by: int | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseOrderItemOut]
