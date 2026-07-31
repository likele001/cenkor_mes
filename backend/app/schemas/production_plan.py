from datetime import date

from pydantic import BaseModel, Field


class ProductionPlanCreateIn(BaseModel):
    order_id: int = Field(ge=1)
    code: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    work_days: int | None = Field(default=None, ge=0)
    remark: str | None = None


class ProductionPlanReleaseIn(BaseModel):
    allow_shortage: bool = Field(default=False, description="允许缺料仍下发投产")


class ProductionPlanUpdateIn(BaseModel):
    order_id: int | None = Field(default=None, ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    status: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    work_days: int | None = Field(default=None, ge=0)
    remark: str | None = None


class CalendarDayUpsertIn(BaseModel):
    day: date
    is_workday: bool = True
    capacity_minutes: int | None = Field(default=None, ge=0, le=10000)
    remark: str | None = Field(default=None, max_length=255)


class WorkshopCapacityItemIn(BaseModel):
    workshop: str = Field(min_length=1, max_length=64)
    capacity_minutes: int = Field(ge=1, le=10000)


class WorkshopCapacitiesIn(BaseModel):
    items: list[WorkshopCapacityItemIn] = []


class UserCapacityItemIn(BaseModel):
    user_id: int = Field(ge=1)
    capacity_minutes: int = Field(ge=1, le=10000)


class UserCapacitiesIn(BaseModel):
    items: list[UserCapacityItemIn] = []


class EquipmentCapacityItemIn(BaseModel):
    equipment_id: int = Field(ge=1)
    capacity_minutes: int = Field(ge=1, le=10000)


class EquipmentCapacitiesIn(BaseModel):
    items: list[EquipmentCapacityItemIn] = []


class AutoDispatchIn(BaseModel):
    user_ids: list[int] | None = Field(default=None, description="限定可分配的人员ID列表（须为员工角色）")
    unassigned_only: bool = Field(default=True, description="仅对未派工任务生效")
    include_leader: bool = Field(default=False, description="是否包含班组长（默认仅员工）")
    auto_release: bool = Field(
        default=False,
        description="计划为「计划中」时先自动确认下发（生成工单/任务）",
    )
    allow_shortage: bool = Field(default=False, description="自动下发时是否允许缺料")

