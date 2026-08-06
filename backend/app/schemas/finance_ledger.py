from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class FinanceLedgerCreateIn(BaseModel):
    direction: Literal["in", "out"]
    category: Literal["ar", "ap", "receipt", "payment", "adjust"]
    party_type: Literal["customer", "supplier", "other"]
    party_id: int | None = Field(default=None, ge=1)
    statement_type: str | None = Field(default=None, max_length=32)
    statement_id: int | None = Field(default=None, ge=1)
    amount: Decimal = Field(gt=0)
    biz_date: date
    remark: str | None = Field(default=None, max_length=500)
