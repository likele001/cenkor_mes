from datetime import datetime

from pydantic import BaseModel, Field


class ProductCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    description: str | None = None
    is_active: bool = True


class ProductUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    description: str | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: int
    code: str
    name: str
    category: str | None
    unit: str | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
