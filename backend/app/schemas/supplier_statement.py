from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class SupplierStatementItemIn(BaseModel):
    purchase_order_id: int = Field(ge=1)


class SupplierStatementCreateIn(BaseModel):
    supplier_id: int = Field(ge=1)
    code: str | None = Field(default=None, max_length=64)
    period_start: date | None = None
    period_end: date | None = None
    remark: str | None = Field(default=None, max_length=500)
    order_ids: list[int] = Field(min_length=1, description="采购单ID列表")
