from datetime import datetime

from pydantic import BaseModel, Field


class MaterialCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    unit: str | None = Field(default=None, max_length=32)
    spec: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    supplier_id: int | None = Field(default=None, ge=1)
    is_active: bool = True


class MaterialUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    unit: str | None = Field(default=None, max_length=32)
    spec: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    supplier_id: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class MaterialOut(BaseModel):
    id: int
    code: str
    name: str
    unit: str | None
    spec: str | None
    remark: str | None
    supplier_id: int | None
    sku_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
