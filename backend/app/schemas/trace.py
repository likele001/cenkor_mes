from datetime import datetime

from pydantic import BaseModel, Field


class TraceCodeOut(BaseModel):
    id: int
    code: str
    order_id: int
    sku_id: int
    process_id: int
    report_id: int
    user_id: int
    qty: int
    remark: str | None
    created_at: datetime


class TraceChainOut(BaseModel):
    """全链路溯源结果"""
    trace_code: str
    order: dict | None = None
    sku: dict | None = None
    process: dict | None = None
    report: dict | None = None
    report_user: dict | None = None
    audits: list[dict] = []
    salary_item: dict | None = None
