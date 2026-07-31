"""工资相关 Pydantic 模型：工资补贴/扣款、工资条、工资台账"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── 工资补贴/扣款 ──

class SalaryAllowanceCreateIn(BaseModel):
    """工资补贴/扣款 — 创建"""
    user_id: int = Field(ge=1, description="员工 ID")
    allowance_type: str = Field(min_length=1, max_length=16, description="类型: bonus/deduction")
    amount: float = Field(description="金额")
    month: str = Field(min_length=7, max_length=7, description="月份 YYYY-MM")
    reason: str | None = Field(default=None, max_length=255, description="原因")


class SalaryAllowanceUpdateIn(BaseModel):
    """工资补贴/扣款 — 更新"""
    user_id: int | None = Field(default=None, ge=1, description="员工 ID")
    allowance_type: str | None = Field(default=None, max_length=16, description="类型: bonus/deduction")
    amount: float | None = Field(default=None, description="金额")
    month: str | None = Field(default=None, min_length=7, max_length=7, description="月份 YYYY-MM")
    reason: str | None = Field(default=None, max_length=255, description="原因")


class SalaryAllowanceOut(BaseModel):
    """工资补贴/扣款 — 输出"""
    id: int
    user_id: int
    allowance_type: str
    amount: float
    month: str
    reason: str | None
    created_at: datetime


# ── 工资条 ──

class SalarySlipOut(BaseModel):
    """工资条 — 输出（含计算字段）"""
    id: int
    user_id: int
    user_name: str | None = None
    month: str
    total_qty: int
    item_amount: float
    hourly_amount: float = 0
    hourly_hours: float = 0
    bonus_amount: float
    deduction_amount: float
    net_amount: float
    signature_attachment_id: int | None
    signed_at: datetime | None
    is_signed: bool
    confirm_status: str
    reject_reason: str | None
    rejected_at: datetime | None


class SalarySlipSignOut(BaseModel):
    """工资条签名后输出"""
    id: int
    month: str
    signature_attachment_id: int | None
    signed_at: datetime | None
    confirm_status: str


class SalarySlipRejectOut(BaseModel):
    """工资条拒签后输出"""
    id: int
    month: str
    confirm_status: str
    reject_reason: str | None
    rejected_at: datetime | None


class SalarySlipResetOut(BaseModel):
    """工资条重置确认后输出"""
    id: int
    confirm_status: str


# ── 工资台账 ──

class SalaryLedgerItemOut(BaseModel):
    """工资台账明细 — 输出"""
    id: int
    source: str
    salary_id: int | None
    report_unit_id: int | None
    report_id: int | None
    user_id: int
    username: str | None
    user_full_name: str | None
    order_id: int | None
    order_code: str | None
    product_id: int | None
    product_name: str | None
    sku_id: int | None
    sku_code: str | None
    sku_name: str | None
    process_id: int | None
    process_code: str | None
    process_name: str | None
    unit_seq: int | None
    reported_qty: int
    unit_price: float
    amount: float
    status: str
    status_label: str
    reported_at: datetime | None
    month: str
    task_code: str | None
    result_type: str | None
