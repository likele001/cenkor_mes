"""质量检测相关 Pydantic 模型：质检模板、缺陷代码、检测记录"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── 质检模板明细项 ──

class TemplateItemIn(BaseModel):
    """质检模板明细项 — 创建/更新"""
    item_name: str = Field(min_length=1, max_length=128, description="检查项名称")
    item_type: str = Field(
        default="pass_fail",
        pattern="^(pass_fail|measure|text)$",
        description="检查类型: pass_fail|measure|text",
    )
    standard_value: str | None = Field(default=None, max_length=64, description="标准值")
    upper_limit: str | None = Field(default=None, max_length=64, description="上限")
    lower_limit: str | None = Field(default=None, max_length=64, description="下限")
    unit: str | None = Field(default=None, max_length=32, description="单位")
    is_required: bool = Field(default=True, description="是否必检")
    remark: str | None = Field(default=None, max_length=255, description="备注")


class TemplateItemOut(BaseModel):
    """质检模板明细项 — 输出"""
    id: int
    seq: int
    item_name: str
    item_type: str
    standard_value: str | None
    upper_limit: str | None
    lower_limit: str | None
    unit: str | None
    is_required: bool
    remark: str | None


# ── 质检模板 ──

class TemplateIn(BaseModel):
    """质检模板 — 创建"""
    code: str = Field(min_length=1, max_length=64, description="模板编码")
    name: str = Field(min_length=1, max_length=128, description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    process_id: int | None = Field(default=None, description="关联工序 ID")
    product_id: int | None = Field(default=None, description="关联产品 ID")
    items: list[TemplateItemIn] = Field(default_factory=list, description="模板明细项")


class TemplateUpdateIn(BaseModel):
    """质检模板 — 更新"""
    code: str = Field(min_length=1, max_length=64, description="模板编码")
    name: str = Field(min_length=1, max_length=128, description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    process_id: int | None = Field(default=None, description="关联工序 ID")
    product_id: int | None = Field(default=None, description="关联产品 ID")
    items: list[TemplateItemIn] = Field(default_factory=list, description="模板明细项")


class TemplateOut(BaseModel):
    """质检模板 — 输出"""
    id: int
    code: str
    name: str
    description: str | None
    process_id: int | None
    product_id: int | None
    is_active: bool
    items: list[TemplateItemOut]
    created_at: str | None


# ── 缺陷代码 ──

class DefectCodeCreateIn(BaseModel):
    """缺陷代码 — 创建"""
    code: str = Field(min_length=1, max_length=32, description="缺陷代码")
    name: str = Field(min_length=1, max_length=128, description="缺陷名称")
    severity: str = Field(
        default="minor",
        pattern="^(critical|major|minor)$",
        description="严重程度: critical|major|minor",
    )
    description: str | None = Field(default=None, description="描述")


class DefectCodeUpdateIn(BaseModel):
    """缺陷代码 — 更新"""
    code: str = Field(min_length=1, max_length=32, description="缺陷代码")
    name: str = Field(min_length=1, max_length=128, description="缺陷名称")
    severity: str = Field(
        default="minor",
        pattern="^(critical|major|minor)$",
        description="严重程度: critical|major|minor",
    )
    description: str | None = Field(default=None, description="描述")


class DefectCodeOut(BaseModel):
    """缺陷代码 — 输出"""
    id: int
    code: str
    name: str
    severity: str
    description: str | None
    is_active: bool


# ── 检测记录 ──

class InspectionRecordOut(BaseModel):
    """检测记录 — 输出"""
    id: int
    report_unit_audit_id: int
    template_item_id: int
    result: str
    measured_value: str | None
    defect_code_id: int | None
    remark: str | None
    created_at: datetime
