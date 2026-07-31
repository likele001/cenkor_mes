from datetime import date, datetime

from pydantic import BaseModel, Field


class AttendanceCheckInIn(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class AttendanceCheckOutIn(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class AttendanceGeofenceIn(BaseModel):
    enabled: bool = False
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    radius_m: float | None = Field(default=None, ge=10, le=50000)


class AttendanceRecordUpdateIn(BaseModel):
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    remark: str | None = Field(default=None, max_length=255)


class AttendanceRecordCreateIn(BaseModel):
    user_id: int = Field(ge=1)
    work_date: date
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    remark: str | None = Field(default=None, max_length=255)
