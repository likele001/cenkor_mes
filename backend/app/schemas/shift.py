from datetime import datetime, time

from pydantic import BaseModel, Field


# ---------- 班次 ----------
class ShiftCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    start_time: str = Field(min_length=1, max_length=5)  # HH:MM
    end_time: str = Field(min_length=1, max_length=5)    # HH:MM
    rest_minutes: int = Field(default=0, ge=0)
    shift_type: str = Field(default="day", max_length=16)
    remark: str | None = None


class ShiftUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    start_time: str | None = Field(default=None, min_length=1, max_length=5)
    end_time: str | None = Field(default=None, min_length=1, max_length=5)
    rest_minutes: int | None = Field(default=None, ge=0)
    shift_type: str | None = Field(default=None, max_length=16)
    status: str | None = Field(default=None, max_length=16)
    remark: str | None = None


class ShiftOut(BaseModel):
    id: int
    code: str
    name: str
    start_time: str
    end_time: str
    rest_minutes: int
    shift_type: str
    status: str
    remark: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ---------- 排班 ----------
class ShiftScheduleCreateIn(BaseModel):
    user_id: int
    shift_id: int
    work_date: str = Field(min_length=1, max_length=10)  # YYYY-MM-DD
    remark: str | None = None


class ShiftScheduleBatchCreateIn(BaseModel):
    user_ids: list[int] = Field(min_length=1)
    shift_id: int
    start_date: str = Field(min_length=1, max_length=10)
    end_date: str = Field(min_length=1, max_length=10)


class ShiftScheduleOut(BaseModel):
    id: int
    user_id: int
    shift_id: int
    work_date: str
    remark: str | None
    created_at: datetime
    updated_at: datetime
    shift_name: str | None = None
    shift_code: str | None = None
    user_name: str | None = None
    model_config = {"from_attributes": True}
