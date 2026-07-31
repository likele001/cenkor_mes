from pydantic import BaseModel, Field


class DepartmentCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    parent_id: int | None = None
    is_active: bool = True


class DepartmentUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    parent_id: int | None = None
    is_active: bool | None = None
