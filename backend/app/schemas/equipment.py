from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------- 设备 ----------
class EquipmentCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    model: str | None = Field(default=None, max_length=64)
    workshop: str | None = Field(default=None, max_length=64)
    remark: str | None = None


class EquipmentUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    model: str | None = Field(default=None, max_length=64)
    workshop: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)
    purchase_date: date | None = None
    last_maintenance_date: date | None = None
    next_maintenance_date: date | None = None
    maintenance_interval_days: int | None = None
    remark: str | None = None


class EquipmentOut(BaseModel):
    id: int
    code: str

    name: str
    model: str | None
    workshop: str | None
    status: str
    purchase_date: date | None
    last_maintenance_date: date | None
    next_maintenance_date: date | None
    maintenance_interval_days: int | None
    remark: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ---------- 设备保养计划 ----------
class EquipmentMaintenancePlanCreateIn(BaseModel):
    equipment_id: int
    plan_type: str = Field(min_length=1, max_length=16)  # daily/weekly/monthly
    check_items: str | None = None  # 检查项 JSON
    interval_days: int | None = None
    responsible_user_id: int | None = None
    next_date: date | None = None
    remark: str | None = None


class EquipmentMaintenancePlanUpdateIn(BaseModel):
    equipment_id: int | None = None
    plan_type: str | None = Field(default=None, min_length=1, max_length=16)
    check_items: str | None = None
    interval_days: int | None = None
    responsible_user_id: int | None = None
    next_date: date | None = None
    remark: str | None = None


class EquipmentMaintenancePlanOut(BaseModel):
    id: int
    equipment_id: int
    plan_type: str
    check_items: str | None
    interval_days: int | None
    responsible_user_id: int | None
    next_date: date | None
    remark: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ---------- 设备保养日志 ----------
class EquipmentMaintenanceLogCreateIn(BaseModel):
    plan_id: int | None = None
    equipment_id: int
    check_result: str = Field(min_length=1, max_length=32)
    description: str | None = None
    attachments: str | None = None  # JSON array


class EquipmentMaintenanceLogOut(BaseModel):
    id: int
    plan_id: int | None
    equipment_id: int
    check_result: str
    description: str | None
    attachments: str | None
    checked_by: int | None
    created_at: datetime
    model_config = {"from_attributes": True}
