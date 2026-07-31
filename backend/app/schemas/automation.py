from pydantic import BaseModel, Field


class AutomationSettingsIn(BaseModel):
    enabled: bool | None = None
    on_order_confirm: dict | None = None
    on_plan_saved: dict | None = None
    audit: dict | None = None
    briefing: dict | None = None
    alerts: dict | None = None


class AutomationDryRunIn(BaseModel):
    order_id: int | None = None
    plan_id: int | None = None
    allow_shortage: bool = False
