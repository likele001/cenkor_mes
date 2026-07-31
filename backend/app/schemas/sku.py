from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, condecimal


Money = condecimal(max_digits=12, decimal_places=4)


class SkuCreateIn(BaseModel):
    product_id: int
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    color: str | None = Field(default=None, max_length=64)
    material: str | None = Field(default=None, max_length=128)
    spec: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool = True


class SkuUpdateIn(BaseModel):
    product_id: int | None = None
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    color: str | None = Field(default=None, max_length=64)
    material: str | None = Field(default=None, max_length=128)
    spec: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool | None = None


class SkuBatchPriceItemIn(BaseModel):
    process_id: int
    unit_price: Money | None = None
    is_active: bool = True


class SkuBatchItemIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    color: str | None = Field(default=None, max_length=64)
    material: str | None = Field(default=None, max_length=128)
    spec: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool = True
    prices: list[SkuBatchPriceItemIn] = Field(default_factory=list)


class SkuBatchWithPricesIn(BaseModel):
    product_id: int
    items: list[SkuBatchItemIn] = Field(min_length=1, max_length=50)


class SkuOut(BaseModel):
    id: int
    product_id: int
    code: str
    name: str
    color: str | None
    material: str | None
    spec: str | None
    remark: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
