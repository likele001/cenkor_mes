from datetime import datetime

from pydantic import BaseModel, Field


class ProcessRouteStepIn(BaseModel):
    seq: int = Field(ge=1)
    process_id: int


class ProcessRouteCreateIn(BaseModel):
    product_id: int
    name: str = Field(min_length=1, max_length=128)
    is_default: bool = False
    is_active: bool = True
    steps: list[ProcessRouteStepIn] = Field(default_factory=list)


class ProcessRouteUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_default: bool | None = None
    is_active: bool | None = None
    steps: list[ProcessRouteStepIn] | None = None


class ProcessRouteStepOut(BaseModel):
    id: int
    route_id: int
    seq: int
    process_id: int


class ProcessRouteOut(BaseModel):
    id: int
    product_id: int
    name: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    steps: list[ProcessRouteStepOut] = Field(default_factory=list)
