from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.order import OrderItemCreateIn


class CustomerContactCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    title: str | None = Field(default=None, max_length=64)
    is_primary: bool = False
    remark: str | None = None
    is_active: bool = True


class CustomerContactUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    title: str | None = Field(default=None, max_length=64)
    is_primary: bool | None = None
    remark: str | None = None
    is_active: bool | None = None


class CrmOpportunityCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=128)
    stage: str = Field(default="prospecting", max_length=32)
    status: str = Field(default="open", max_length=16)
    amount: Decimal | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    remark: str | None = None
    is_active: bool = True


class CrmOpportunityUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    stage: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=16)
    amount: Decimal | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    remark: str | None = None
    is_active: bool | None = None


class CrmOpportunityActivityCreateIn(BaseModel):
    action_type: str = Field(default="note", max_length=16)
    content: str = Field(min_length=1)
    next_follow_up_at: datetime | None = None


class OpportunityConvertToOrderIn(BaseModel):
    due_date: date | None = None
    remark: str | None = None
    items: list[OrderItemCreateIn] = Field(min_length=1)


class CustomerContactOut(BaseModel):
    id: int
    tenant_id: int
    customer_id: int
    name: str
    phone: str | None
    email: str | None
    title: str | None
    is_primary: bool
    remark: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CrmOpportunityOut(BaseModel):
    id: int
    tenant_id: int
    customer_id: int
    code: str
    title: str
    stage: str
    status: str
    amount: Decimal | None
    probability: int | None
    expected_close_date: date | None
    owner_user_id: int | None
    owner_name: str | None
    remark: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CrmOpportunityActivityOut(BaseModel):
    id: int
    tenant_id: int
    opportunity_id: int
    action_type: str
    content: str
    created_by: int | None
    created_by_name: str | None
    next_follow_up_at: datetime | None = None
    created_at: datetime


class CustomerTagCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    is_active: bool = True


class CustomerTagUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    is_active: bool | None = None


class CustomerTagOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    color: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerTagsSetIn(BaseModel):
    tag_ids: list[int] = Field(default_factory=list)


# ============================
# Lead (线索)
# ============================
class CrmLeadBase(BaseModel):
    contact_name: str = Field(min_length=1, max_length=64)
    company: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    mobile: str | None = Field(default=None, max_length=32)
    wechat: str | None = Field(default=None, max_length=64)
    position: str | None = Field(default=None, max_length=64)
    industry: str | None = Field(default=None, max_length=64)
    country: str | None = Field(default=None, max_length=64)
    province: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=256)
    website: str | None = Field(default=None, max_length=256)
    source: str | None = Field(default=None, max_length=32)
    interest_products: list[int] | None = Field(default=None)
    remark: str | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    status: str = Field(default="new", max_length=16)


class CrmLeadCreateIn(CrmLeadBase):
    pass


class CrmLeadUpdateIn(BaseModel):
    contact_name: str | None = Field(default=None, min_length=1, max_length=64)
    company: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    mobile: str | None = Field(default=None, max_length=32)
    wechat: str | None = Field(default=None, max_length=64)
    position: str | None = Field(default=None, max_length=64)
    industry: str | None = Field(default=None, max_length=64)
    country: str | None = Field(default=None, max_length=64)
    province: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=256)
    website: str | None = Field(default=None, max_length=256)
    source: str | None = Field(default=None, max_length=32)
    interest_products: list[int] | None = None
    remark: str | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, max_length=16)


class CrmLeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    score: int | None = None
    grade: str | None = None
    last_follow_up_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    is_public_pool: bool = False
    customer_id: int | None = None
    opportunity_id: int | None = None
    converted_at: datetime | None = None
    campaign_id: int | None = None
    created_at: datetime


class LeadConvertIn(BaseModel):
    convert_to_customer: bool = True
    convert_to_opportunity: bool = True
    opportunity_title: str | None = None
    opportunity_stage: str = Field(default="prospecting", max_length=32)
    opportunity_amount: Decimal | None = None


class LeadActivityCreateIn(BaseModel):
    action_type: str = Field(default="note", max_length=16)
    content: str = Field(min_length=1)
    next_follow_up_at: datetime | None = None


class LeadActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    action_type: str
    content: str
    created_by: int | None = None
    next_follow_up_at: datetime | None = None
    created_at: datetime


# ============================
# Quotation (报价单)
# ============================
class CrmQuotationItemIn(BaseModel):
    product_id: int | None = Field(default=None, ge=1)
    sku_id: int | None = Field(default=None, ge=1)
    product_name: str = Field(min_length=1, max_length=256)
    spec: str | None = Field(default=None, max_length=256)
    quantity: Decimal
    unit_price: Decimal
    discount_rate: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    delivery_date: date | None = None
    remark: str | None = None


class CrmQuotationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None = None
    sku_id: int | None = None
    product_name: str
    spec: str | None = None
    quantity: Decimal
    unit_price: Decimal
    discount_rate: Decimal
    tax_rate: Decimal
    amount: Decimal
    delivery_date: date | None = None
    remark: str | None = None


class CrmQuotationCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    customer_id: int = Field(ge=1)
    opportunity_id: int | None = Field(default=None, ge=1)
    contact_id: int | None = Field(default=None, ge=1)
    valid_from: date | None = None
    valid_until: date | None = None
    currency: str = Field(default="CNY", max_length=8)
    tax_rate: Decimal = Decimal("0")
    discount_rate: Decimal = Decimal("0")
    payment_terms: str | None = None
    delivery_terms: str | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    remark: str | None = None
    items: list[CrmQuotationItemIn] = Field(min_length=1)


class CrmQuotationUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    valid_from: date | None = None
    valid_until: date | None = None
    currency: str | None = Field(default=None, max_length=8)
    tax_rate: Decimal | None = None
    discount_rate: Decimal | None = None
    payment_terms: str | None = None
    delivery_terms: str | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    remark: str | None = None
    items: list[CrmQuotationItemIn] | None = None


class CrmQuotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    title: str
    customer_id: int
    opportunity_id: int | None = None
    version: int
    parent_id: int | None = None
    status: str
    valid_from: date
    valid_until: date
    currency: str
    tax_rate: Decimal
    discount_rate: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    payment_terms: str | None = None
    delivery_terms: str | None = None
    owner_user_id: int | None = None
    sent_at: datetime | None = None
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    reject_reason: str | None = None
    converted_order_id: int | None = None
    remark: str | None = None
    created_at: datetime


class CrmQuotationRejectIn(BaseModel):
    reason: str | None = None


# ============================
# Contract (合同) & Payment Plan
# ============================
class CrmPaymentPlanItemIn(BaseModel):
    phase: str = Field(max_length=32)
    phase_name: str = Field(max_length=64)
    due_date: date
    amount: Decimal
    actual_amount: Decimal = Decimal("0")
    actual_date: date | None = None
    status: str | None = Field(default=None, max_length=16)
    invoice_no: str | None = Field(default=None, max_length=128)
    remark: str | None = None


class CrmContractCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    customer_id: int = Field(ge=1)
    opportunity_id: int | None = Field(default=None, ge=1)
    quotation_id: int | None = Field(default=None, ge=1)
    order_id: int | None = Field(default=None, ge=1)
    type: str = Field(default="sales", max_length=16)
    status: str = Field(default="draft", max_length=16)
    sign_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    auto_renewal: bool = False
    renewal_notice_days: int = 30
    currency: str = Field(default="CNY", max_length=8)
    payment_terms: str | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    remark: str | None = None
    plan_items: list[CrmPaymentPlanItemIn] = Field(default_factory=list)


class CrmContractUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    type: str | None = Field(default=None, max_length=16)
    status: str | None = Field(default=None, max_length=16)
    sign_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    auto_renewal: bool | None = None
    renewal_notice_days: int | None = None
    currency: str | None = Field(default=None, max_length=8)
    payment_terms: str | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    remark: str | None = None
    plan_items: list[CrmPaymentPlanItemIn] | None = None


class CrmContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    name: str
    customer_id: int
    opportunity_id: int | None = None
    quotation_id: int | None = None
    order_id: int | None = None
    type: str
    status: str
    sign_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    auto_renewal: bool
    renewal_notice_days: int
    total_amount: Decimal
    currency: str
    payment_terms: str | None = None
    owner_user_id: int | None = None
    parent_contract_id: int | None = None
    renewal_count: int
    remark: str | None = None
    created_at: datetime


class CrmPaymentPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    phase: str
    phase_name: str
    due_date: date
    amount: Decimal
    actual_amount: Decimal
    actual_date: date | None = None
    status: str
    invoice_no: str | None = None
    remark: str | None = None


class PaymentRecordIn(BaseModel):
    actual_amount: Decimal
    actual_date: date | None = None
    invoice_no: str | None = None


# ============================
# Win/Loss Reason (赢单/丢单原因)
# ============================
class CrmWinLossReasonCreateIn(BaseModel):
    type: str = Field(max_length=8)
    category: str = Field(max_length=32)
    code: str = Field(max_length=32)
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=512)
    sort_order: int = 0


class CrmWinLossReasonUpdateIn(BaseModel):
    type: str | None = Field(default=None, max_length=8)
    category: str | None = Field(default=None, max_length=32)
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    sort_order: int | None = None


class CrmWinLossReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    type: str
    category: str
    code: str
    name: str
    description: str | None = None
    sort_order: int
    created_at: datetime


# ============================
# Campaign (营销活动)
# ============================
class CrmCampaignCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    type: str = Field(default="email", max_length=32)
    objective: str | None = Field(default=None, max_length=64)
    target_audience: str | None = None
    channel: str | None = Field(default=None, max_length=32)
    status: str = Field(default="draft", max_length=16)
    start_date: date | None = None
    end_date: date | None = None
    budget: Decimal | None = None
    actual_cost: Decimal | None = None
    expected_revenue: Decimal | None = None
    actual_revenue: Decimal | None = None
    currency: str = Field(default="CNY", max_length=8)
    target_leads_count: int | None = None
    landing_url: str | None = None
    utm_source: str | None = None
    utm_campaign: str | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    remark: str | None = None


class CrmCampaignUpdateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    type: str | None = Field(default=None, max_length=32)
    objective: str | None = Field(default=None, max_length=64)
    target_audience: str | None = None
    channel: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=16)
    start_date: date | None = None
    end_date: date | None = None
    budget: Decimal | None = None
    actual_cost: Decimal | None = None
    expected_revenue: Decimal | None = None
    actual_revenue: Decimal | None = None
    currency: str | None = Field(default=None, max_length=8)
    target_leads_count: int | None = None
    landing_url: str | None = None
    utm_source: str | None = None
    utm_campaign: str | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    remark: str | None = None


class CrmCampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    name: str
    type: str
    objective: str | None = None
    target_audience: str | None = None
    channel: str | None = None
    status: str
    start_date: date | None = None
    end_date: date | None = None
    budget: Decimal | None = None
    actual_cost: Decimal | None = None
    expected_revenue: Decimal | None = None
    actual_revenue: Decimal | None = None
    currency: str
    target_leads_count: int | None = None
    landing_url: str | None = None
    utm_source: str | None = None
    utm_campaign: str | None = None
    owner_user_id: int | None = None
    remark: str | None = None
    created_at: datetime


class CampaignMemberAddIn(BaseModel):
    members: list[dict[str, Any]] = Field(default_factory=list)


# ============================
# Sales Target (销售目标)
# ============================
class CrmSalesTargetCreateIn(BaseModel):
    period_type: str = Field(max_length=16)
    period_start: date
    period_end: date
    dimension: str = Field(max_length=32)
    dimension_id: int | None = None
    metric: str = Field(max_length=32)
    target_value: Decimal
    currency: str = Field(default="CNY", max_length=8)
    owner_user_id: int | None = Field(default=None, ge=1)


class CrmSalesTargetUpdateIn(BaseModel):
    period_type: str | None = Field(default=None, max_length=16)
    period_start: date | None = None
    period_end: date | None = None
    dimension: str | None = Field(default=None, max_length=32)
    dimension_id: int | None = None
    metric: str | None = Field(default=None, max_length=32)
    target_value: Decimal | None = None
    currency: str | None = Field(default=None, max_length=8)
    owner_user_id: int | None = Field(default=None, ge=1)


class CrmSalesTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    period_type: str
    period_start: date
    period_end: date
    dimension: str
    dimension_id: int | None = None
    metric: str
    target_value: Decimal
    currency: str
    owner_user_id: int | None = None
    created_at: datetime


# ============================
# Lead Summary
# ============================
class LeadSummaryOut(BaseModel):
    total: int
    by_status: dict[str, int]
    by_grade: dict[str, int]
    by_source: dict[str, int]
    public_pool: int
    converted: int
