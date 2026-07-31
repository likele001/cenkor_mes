from datetime import datetime

from pydantic import BaseModel, Field


class ProcessCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    workshop: str | None = Field(default=None, max_length=64)
    std_minutes: int | None = None
    is_active: bool = True


class ProcessUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    workshop: str | None = Field(default=None, max_length=64)
    std_minutes: int | None = None
    is_active: bool | None = None


class ProcessOut(BaseModel):
    id: int
    code: str
    name: str
    display_name: str | None = None
    workshop: str | None
    std_minutes: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
