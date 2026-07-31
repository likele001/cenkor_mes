from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, condecimal


Money = condecimal(max_digits=12, decimal_places=4)


class ProcessPriceCreateIn(BaseModel):
    sku_id: int
    process_id: int
    unit_price: Money
    is_active: bool = True


class ProcessPriceUpdateIn(BaseModel):
    unit_price: Money | None = None
    is_active: bool | None = None


class ProcessPriceBatchItemIn(BaseModel):
    process_id: int
    unit_price: Money | None = None
    is_active: bool = True


class ProcessPriceBatchIn(BaseModel):
    sku_id: int
    items: list[ProcessPriceBatchItemIn] = Field(default_factory=list)


class ProcessPriceOut(BaseModel):
    id: int
    sku_id: int
    process_id: int
    unit_price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
