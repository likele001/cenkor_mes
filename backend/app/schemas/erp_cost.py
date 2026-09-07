from decimal import Decimal

from pydantic import BaseModel, Field


class OverheadIn(BaseModel):
    amount: Decimal = Field(gt=0)
    remark: str | None = Field(default=None, max_length=500)


class CostCalculateIn(BaseModel):
    work_order_id: int | None = Field(default=None, ge=1)
    period: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
