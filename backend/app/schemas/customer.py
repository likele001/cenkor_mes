from datetime import datetime

from pydantic import BaseModel, Field


class CustomerCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    user_id: int | None = Field(default=None, ge=1)
    login_username: str | None = Field(default=None, max_length=64)
    login_password: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool = True
    owner_user_id: int | None = Field(default=None, ge=1)


class CustomerUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    user_id: int | None = Field(default=None, ge=1)
    login_username: str | None = Field(default=None, max_length=64)
    login_password: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    remark: str | None = None
    is_active: bool | None = None
    owner_user_id: int | None = Field(default=None, ge=1)


class CustomerProductsSetIn(BaseModel):
    product_ids: list[int] = Field(default_factory=list)


class CustomerOut(BaseModel):
    id: int
    user_id: int | None
    owner_user_id: int | None = None
    owner_name: str | None = None
    code: str
    name: str
    contact_name: str | None
    contact_phone: str | None
    address: str | None
    remark: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
