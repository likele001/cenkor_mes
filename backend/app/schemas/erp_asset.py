from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class FixedAssetCreateIn(BaseModel):
    asset_no: str | None = Field(default=None, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    model: str | None = Field(default=None, max_length=64)
    equipment_id: int | None = Field(default=None, ge=1)
    workshop: str | None = Field(default=None, max_length=64)
    department_id: int | None = Field(default=None, ge=1)
    original_value: Decimal = Field(ge=0)
    residual_value: Decimal = Field(default=Decimal("0"), ge=0)
    useful_life_months: int = Field(gt=0, le=600)
    depreciation_method: Literal["straight_line", "double_declining", "sum_of_years"] = "straight_line"
    purchase_date: date | None = None
    start_use_date: date | None = None
    remark: str | None = Field(default=None, max_length=1000)


class FixedAssetUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=64)
    equipment_id: int | None = Field(default=None, ge=1)
    workshop: str | None = Field(default=None, max_length=64)
    department_id: int | None = Field(default=None, ge=1)
    original_value: Decimal | None = Field(default=None, ge=0)
    residual_value: Decimal | None = Field(default=None, ge=0)
    useful_life_months: int | None = Field(default=None, gt=0, le=600)
    depreciation_method: Literal["straight_line", "double_declining", "sum_of_years"] | None = None
    purchase_date: date | None = None
    start_use_date: date | None = None
    status: Literal["active", "retired", "scrapped"] | None = None
    remark: str | None = Field(default=None, max_length=1000)


class DepreciateBatchIn(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")


class AssetCheckCreateIn(BaseModel):
    check_no: str | None = Field(default=None, max_length=32)
    check_date: date
    remark: str | None = Field(default=None, max_length=1000)


class AssetCheckItemIn(BaseModel):
    asset_id: int = Field(ge=1)
    expected_qty: int = Field(default=1, ge=0)
    checked_qty: int = Field(default=1, ge=0)
    remark: str | None = Field(default=None, max_length=500)
