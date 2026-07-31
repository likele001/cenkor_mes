from pydantic import BaseModel, Field


class DictTypeCreateIn(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


class DictTypeUpdateIn(BaseModel):
    code: str | None = None
    name: str | None = None


class DictTypeOut(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    model_config = {"from_attributes": True}


class DictItemCreateIn(BaseModel):
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    sort_order: int = 0


class DictItemUpdateIn(BaseModel):
    label: str | None = None
    value: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class DictItemOut(BaseModel):
    id: int
    label: str
    value: str
    sort_order: int
    is_active: bool
    model_config = {"from_attributes": True}
