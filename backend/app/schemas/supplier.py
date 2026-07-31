from datetime import datetime

from pydantic import BaseModel, Field


class SupplierCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool = True


class SupplierUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool | None = None


class SupplierOut(BaseModel):
    id: int
    code: str
    name: str
    contact_name: str | None
    phone: str | None
    address: str | None
    remark: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
