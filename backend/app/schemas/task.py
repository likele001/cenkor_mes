from datetime import datetime

from pydantic import BaseModel, Field


class TaskAssignIn(BaseModel):
    assigned_user_id: int | None = Field(default=None, ge=1)
    equipment_id: int | None = Field(default=None, ge=1)


class TaskAssignmentItemIn(BaseModel):
    user_id: int = Field(ge=1)
    assigned_qty: int = Field(ge=1)


class TaskAssignmentsIn(BaseModel):
    items: list[TaskAssignmentItemIn] = Field(default_factory=list, max_length=50)
    equipment_id: int | None = Field(default=None, ge=1)


class TaskLabelBatchIn(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=200)
    template_id: int | None = Field(default=None, ge=1)
    template_code: str = Field(default="task_label", min_length=1, max_length=64)


class TaskOut(BaseModel):
    id: int
    work_order_id: int
    process_id: int
    seq: int
    planned_qty: int
    status: str
    assigned_user_id: int | None
    assigned_at: datetime | None
    assigned_by: int | None
    equipment_id: int | None
    created_at: datetime
    updated_at: datetime
