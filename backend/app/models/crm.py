from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CustomerContact(Base):
    __tablename__ = "customer_contacts"
    __table_args__ = (UniqueConstraint("tenant_id", "customer_id", "name", "phone", name="uq_customer_contacts_tenant_customer_name_phone"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer")


class CrmOpportunity(Base):
    __tablename__ = "crm_opportunities"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_crm_opportunities_tenant_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, server_default="prospecting")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    probability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    converted_order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    win_loss_reason_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    win_loss_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer")
    owner = relationship("User", foreign_keys=[owner_user_id])
    converted_order = relationship("Order", foreign_keys=[converted_order_id])
    activities = relationship("CrmOpportunityActivity", back_populates="opportunity", cascade="all, delete-orphan")


class CrmOpportunityActivity(Base):
    __tablename__ = "crm_opportunity_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id: Mapped[int] = mapped_column(Integer, ForeignKey("crm_opportunities.id", ondelete="CASCADE"), nullable=False, index=True)

    action_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="note")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    opportunity = relationship("CrmOpportunity", back_populates="activities")
    creator = relationship("User", foreign_keys=[created_by])


class CustomerTag(Base):
    __tablename__ = "customer_tags"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_customer_tags_tenant_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class CustomerTagLink(Base):
    __tablename__ = "customer_tag_links"
    __table_args__ = (UniqueConstraint("tenant_id", "customer_id", "tag_id", name="uq_customer_tag_links_tenant_customer_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer_tags.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    customer = relationship("Customer")
    tag = relationship("CustomerTag")


class CrmLead(Base):
    __tablename__ = "crm_leads"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_crm_leads_tenant_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(64), nullable=False)
    company: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    wechat: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(256), nullable=True)
    website: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    interest_products: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="new")
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    last_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_public_pool: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    campaign_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    converted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmLeadActivity(Base):
    __tablename__ = "crm_lead_activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="note")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmQuotation(Base):
    __tablename__ = "crm_quotations"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_crm_quotations_tenant_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    opportunity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    contact_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, server_default="1")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    payment_terms: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_terms: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    converted_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmQuotationItem(Base):
    __tablename__ = "crm_quotation_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    quotation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sku_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    spec: Mapped[str | None] = mapped_column(String(256), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(512), nullable=True)


class CrmContract(Base):
    __tablename__ = "crm_contracts"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_crm_contracts_tenant_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quotation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="sales")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    sign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    auto_renewal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    renewal_notice_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    payment_terms: Mapped[str | None] = mapped_column(String(256), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    parent_contract_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    renewal_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    win_loss_reason_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmPaymentPlan(Base):
    __tablename__ = "crm_payment_plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    contract_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phase_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    invoice_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(512), nullable=True)


class CrmWinLossReason(Base):
    __tablename__ = "crm_win_loss_reasons"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_crm_win_loss_reasons_tenant_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmCampaign(Base):
    __tablename__ = "crm_campaigns"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_crm_campaigns_tenant_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(256), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="planned")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    expected_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    actual_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    target_leads_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    landing_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    utm_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmCampaignMember(Base):
    __tablename__ = "crm_campaign_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    member_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    member_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="invited")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    converted_to_opportunity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    score_delta: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmSalesTarget(Base):
    __tablename__ = "crm_sales_targets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    period_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    dimension: Mapped[str | None] = mapped_column(String(16), nullable=True)
    dimension_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    metric: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmDataImportJob(Base):
    __tablename__ = "crm_data_import_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    field_mapping: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    import_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default="insert_only")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_report_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CrmDataImportError(Base):
    __tablename__ = "crm_data_import_errors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
