from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --- 报工 ---

class ReportSubmitIn(BaseModel):
    task_id: int = Field(ge=1)
    good_qty: int = Field(ge=0)
    bad_qty: int = Field(ge=0, default=0)
    remark: str | None = Field(default=None, max_length=500)
    attachment_ids: str | None = Field(default=None, max_length=512)


class ReportOut(BaseModel):
    id: int
    task_id: int
    report_user_id: int
    good_qty: int
    bad_qty: int
    remark: str | None
    attachment_ids: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ReportAuditOut(BaseModel):
    id: int
    report_id: int
    auditor_id: int
    audit_level: str
    action: str
    reason: str | None
    created_at: datetime


# --- 审核 ---

class AuditActionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


# --- 工资 ---

class SalaryItemOut(BaseModel):
    id: int
    report_id: int
    user_id: int
    sku_id: int
    process_id: int
    unit_price: Decimal
    good_qty: int
    amount: Decimal
    month: str
    created_at: datetime


class SalarySummaryOut(BaseModel):
    user_id: int
    total_amount: Decimal
    total_qty: int
    month: str


# SalaryAllowanceCreateIn moved to app.schemas.salary
