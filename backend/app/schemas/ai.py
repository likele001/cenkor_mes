from pydantic import BaseModel, Field


class PlatformAiGlobalIn(BaseModel):
    enabled: bool


class PlatformAiGatewayIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str | None = None
    enabled: bool = True
    timeout_seconds: int = Field(default=120, ge=10, le=600)
    sort_order: int = 0
    is_default: bool = False


class PlatformAiGatewayUpdateIn(BaseModel):
    code: str | None = None
    display_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=10, le=600)
    sort_order: int | None = None
    is_default: bool | None = None


class PlatformAiModelIn(BaseModel):
    gateway_id: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    is_vision: bool = False
    is_active: bool = True
    sort_order: int = 0
    is_default: bool = False


class PlatformAiModelUpdateIn(BaseModel):
    gateway_id: int | None = Field(default=None, ge=1)
    code: str | None = None
    display_name: str | None = None
    model_id: str | None = None
    is_vision: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    is_default: bool | None = None


class AiChatIn(BaseModel):
    scene: str = Field(default="boss_qa", max_length=32)
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    context_id: int | None = None
    model_code: str | None = Field(default=None, max_length=64)


class AiPromptSettingsIn(BaseModel):
    prompt: str | None = Field(default=None, max_length=2000)


class AiTestIn(BaseModel):
    gateway_id: int | None = Field(default=None, ge=1)
    model_code: str | None = None


class ReportAssistIn(BaseModel):
    task_id: int = Field(ge=1)
    result_type: str = Field(default="good", max_length=16)
    remark: str = ""
    good_qty: int | None = Field(default=None, ge=0)
    bad_qty: int | None = Field(default=None, ge=0)


class PhotoCountIn(BaseModel):
    image_urls: list[str] = Field(min_length=1, max_length=6)
    task_id: int | None = Field(default=None, ge=1)
    hint: str | None = Field(default=None, max_length=200, description="可选：用户描述的零件特征")


class VoiceParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    task_id: int | None = Field(default=None, ge=1)


class DefectClassifyIn(BaseModel):
    image_urls: list[str] = Field(min_length=1, max_length=6)
    task_id: int | None = Field(default=None, ge=1)
    remark: str | None = Field(default=None, max_length=500)


class ShiftSummaryIn(BaseModel):
    shift_start: str | None = Field(default=None, description="班次开始时间 ISO")
    shift_hours: int = Field(default=8, ge=1, le=24, description="班次小时数")
    push_to_webhook: bool = False


class AiHelpIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AiGatewaySettingsIn(BaseModel):
    enabled: bool | None = None
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = None
    model_id: str | None = Field(default=None, max_length=128)
    timeout_seconds: int | None = Field(default=None, ge=10, le=600)


class ScheduleApplyIn(BaseModel):
    mode: str = Field(default="backward", description="backward|forward")
    user_ids: list[int] | None = None
    unassigned_only: bool = True
    auto_release: bool = Field(
        default=True,
        description="计划为「计划中」时先自动确认下发（生成工单/任务），再派工",
    )
    allow_shortage: bool = Field(default=False, description="自动下发时是否允许缺料")
    start_date: str | None = Field(default=None, description="直接采纳的开始日 YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="直接采纳的结束日 YYYY-MM-DD")
    work_days: int | None = Field(default=None, ge=1, description="工期（工作日）")
