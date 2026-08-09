from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.crm import CrmOpportunity, CrmOpportunityActivity, CustomerContact, CustomerTag, CustomerTagLink
from app.models.customer import Customer
from app.models.user import User

# 以下为扩展模型，若模型尚未定义会使用回退占位符，保持模块可导入。
try:
    from app.models.crm import (
        CrmCampaign,
        CrmCampaignMember,
        CrmContract,
        CrmLead,
        CrmLeadActivity,
        CrmPaymentPlan,
        CrmQuotation,
        CrmQuotationItem,
        CrmSalesTarget,
        CrmWinLossReason,
    )
except ImportError:  # pragma: no cover - 模型尚未定义时的回退
    CrmLead = None
    CrmLeadActivity = None
    CrmQuotation = None
    CrmQuotationItem = None
    CrmContract = None
    CrmPaymentPlan = None
    CrmWinLossReason = None
    CrmCampaign = None
    CrmCampaignMember = None
    CrmSalesTarget = None


def list_customer_contacts(
    db: Session,
    tenant_id: int,
    customer_id: int,
    include_inactive: bool = False,
) -> list[CustomerContact]:
    stmt = select(CustomerContact).where(CustomerContact.tenant_id == tenant_id, CustomerContact.customer_id == customer_id)
    if not include_inactive:
        stmt = stmt.where(CustomerContact.is_active.is_(True))
    stmt = stmt.order_by(CustomerContact.is_primary.desc(), CustomerContact.id.desc())
    return db.scalars(stmt).all()


def get_contact_by_id(db: Session, tenant_id: int, contact_id: int) -> CustomerContact | None:
    return db.scalar(select(CustomerContact).where(CustomerContact.tenant_id == tenant_id, CustomerContact.id == contact_id))


def create_customer_contact(
    db: Session,
    tenant_id: int,
    customer_id: int,
    name: str,
    phone: str | None,
    email: str | None,
    title: str | None,
    is_primary: bool,
    remark: str | None,
    is_active: bool,
) -> CustomerContact:
    item = CustomerContact(
        tenant_id=tenant_id,
        customer_id=customer_id,
        name=name,
        phone=phone,
        email=email,
        title=title,
        is_primary=is_primary,
        remark=remark,
        is_active=is_active,
    )
    db.add(item)
    db.flush()
    if is_primary:
        db.execute(
            update(CustomerContact)
            .where(
                CustomerContact.tenant_id == tenant_id,
                CustomerContact.customer_id == customer_id,
                CustomerContact.id != item.id,
            )
            .values(is_primary=False)
        )
        db.flush()
    return item


def update_customer_contact(db: Session, item: CustomerContact, **kwargs) -> CustomerContact:
    for k, v in kwargs.items():
        if v is not None:
            setattr(item, k, v)
    db.flush()
    if kwargs.get("is_primary") is True:
        db.execute(
            update(CustomerContact)
            .where(
                CustomerContact.tenant_id == item.tenant_id,
                CustomerContact.customer_id == item.customer_id,
                CustomerContact.id != item.id,
            )
            .values(is_primary=False)
        )
        db.flush()
    return item


def deactivate_customer_contact(db: Session, item: CustomerContact) -> CustomerContact:
    item.is_active = False
    item.is_primary = False
    db.flush()
    return item


def list_opportunities(
    db: Session,
    tenant_id: int,
    customer_id: int,
    status: str | None = None,
    include_inactive: bool = False,
    scope_stmt=None,
) -> list[CrmOpportunity]:
    stmt = (
        select(CrmOpportunity)
        .where(CrmOpportunity.tenant_id == tenant_id, CrmOpportunity.customer_id == customer_id)
        .options(selectinload(CrmOpportunity.owner), selectinload(CrmOpportunity.converted_order))
    )
    if scope_stmt is not None:
        stmt = scope_stmt(stmt)
    if status:
        stmt = stmt.where(CrmOpportunity.status == status)
    if not include_inactive:
        stmt = stmt.where(CrmOpportunity.is_active.is_(True))
    stmt = stmt.order_by(CrmOpportunity.id.desc())
    return db.scalars(stmt).all()


def get_opportunity_by_id(db: Session, tenant_id: int, opportunity_id: int, with_activities: bool = False) -> CrmOpportunity | None:
    stmt = select(CrmOpportunity).where(CrmOpportunity.tenant_id == tenant_id, CrmOpportunity.id == opportunity_id).options(selectinload(CrmOpportunity.owner))
    if with_activities:
        stmt = stmt.options(selectinload(CrmOpportunity.activities).selectinload(CrmOpportunityActivity.creator))
    return db.scalar(stmt)


def create_opportunity(
    db: Session,
    tenant_id: int,
    customer_id: int,
    code: str,
    title: str,
    stage: str,
    status: str,
    amount,
    probability: int | None,
    expected_close_date,
    owner_user_id: int | None,
    remark: str | None,
    is_active: bool,
) -> CrmOpportunity:
    item = CrmOpportunity(
        tenant_id=tenant_id,
        customer_id=customer_id,
        code=code,
        title=title,
        stage=stage,
        status=status,
        amount=amount,
        probability=probability,
        expected_close_date=expected_close_date,
        owner_user_id=owner_user_id,
        remark=remark,
        is_active=is_active,
    )
    db.add(item)
    db.flush()
    return item


def update_opportunity(db: Session, item: CrmOpportunity, **kwargs) -> CrmOpportunity:
    for k, v in kwargs.items():
        if v is not None:
            setattr(item, k, v)
    db.flush()
    return item


def deactivate_opportunity(db: Session, item: CrmOpportunity) -> CrmOpportunity:
    item.is_active = False
    db.flush()
    return item


def list_opportunity_activities(db: Session, tenant_id: int, opportunity_id: int) -> list[CrmOpportunityActivity]:
    stmt = (
        select(CrmOpportunityActivity)
        .where(
            CrmOpportunityActivity.tenant_id == tenant_id,
            CrmOpportunityActivity.opportunity_id == opportunity_id,
        )
        .options(selectinload(CrmOpportunityActivity.creator))
        .order_by(CrmOpportunityActivity.id.desc())
    )
    return db.scalars(stmt).all()


def create_opportunity_activity(
    db: Session,
    tenant_id: int,
    opportunity_id: int,
    action_type: str,
    content: str,
    created_by: int | None,
    next_follow_up_at=None,
) -> CrmOpportunityActivity:
    item = CrmOpportunityActivity(
        tenant_id=tenant_id,
        opportunity_id=opportunity_id,
        action_type=action_type,
        content=content,
        created_by=created_by,
        next_follow_up_at=next_follow_up_at,
    )
    db.add(item)
    db.flush()
    return item


def list_customer_tags(db: Session, tenant_id: int, include_inactive: bool = False) -> list[CustomerTag]:
    stmt = select(CustomerTag).where(CustomerTag.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(CustomerTag.is_active.is_(True))
    stmt = stmt.order_by(CustomerTag.id.desc())
    return db.scalars(stmt).all()


def get_customer_tag_by_id(db: Session, tenant_id: int, tag_id: int) -> CustomerTag | None:
    return db.scalar(select(CustomerTag).where(CustomerTag.tenant_id == tenant_id, CustomerTag.id == tag_id))


def get_customer_tag_by_name(db: Session, tenant_id: int, name: str) -> CustomerTag | None:
    return db.scalar(select(CustomerTag).where(CustomerTag.tenant_id == tenant_id, CustomerTag.name == name))


def create_customer_tag(db: Session, tenant_id: int, name: str, color: str | None, is_active: bool) -> CustomerTag:
    item = CustomerTag(tenant_id=tenant_id, name=name, color=color, is_active=is_active)
    db.add(item)
    db.flush()
    return item


def update_customer_tag(db: Session, item: CustomerTag, name: str | None = None, color: str | None = None, is_active: bool | None = None) -> CustomerTag:
    if name is not None:
        item.name = name
    if color is not None:
        item.color = color
    if is_active is not None:
        item.is_active = is_active
    db.flush()
    return item


def list_customer_tag_links(db: Session, tenant_id: int, customer_id: int) -> list[CustomerTagLink]:
    stmt = (
        select(CustomerTagLink)
        .where(CustomerTagLink.tenant_id == tenant_id, CustomerTagLink.customer_id == customer_id)
        .options(selectinload(CustomerTagLink.tag))
        .order_by(CustomerTagLink.id.desc())
    )
    return db.scalars(stmt).all()


def set_customer_tags(db: Session, tenant_id: int, customer_id: int, tag_ids: list[int]) -> None:
    tag_ids = [int(x) for x in tag_ids if int(x) > 0]
    tag_ids = list(dict.fromkeys(tag_ids))

    if tag_ids:
        exists = db.scalars(select(CustomerTag.id).where(CustomerTag.tenant_id == tenant_id, CustomerTag.id.in_(tag_ids))).all()
        if len(exists) != len(tag_ids):
            raise ValueError("标签不存在")

    db.execute(delete(CustomerTagLink).where(CustomerTagLink.tenant_id == tenant_id, CustomerTagLink.customer_id == customer_id))
    for tid in tag_ids:
        db.add(CustomerTagLink(tenant_id=tenant_id, customer_id=customer_id, tag_id=tid))
    db.flush()


def list_all_opportunities(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    stage: str | None = None,
    status: str | None = None,
    owner_user_id: int | None = None,
    customer_id: int | None = None,
    has_order: bool | None = None,
    offset: int = 0,
    limit: int = 50,
    scope_stmt=None,
) -> list[CrmOpportunity]:
    stmt = (
        select(CrmOpportunity)
        .where(CrmOpportunity.tenant_id == tenant_id, CrmOpportunity.is_active.is_(True))
        .options(
            selectinload(CrmOpportunity.owner),
            selectinload(CrmOpportunity.customer),
            selectinload(CrmOpportunity.converted_order),
        )
    )
    if scope_stmt is not None:
        stmt = scope_stmt(stmt)
    if stage:
        stmt = stmt.where(CrmOpportunity.stage == stage)
    if status:
        stmt = stmt.where(CrmOpportunity.status == status)
    if owner_user_id is not None:
        stmt = stmt.where(CrmOpportunity.owner_user_id == owner_user_id)
    if customer_id is not None:
        stmt = stmt.where(CrmOpportunity.customer_id == customer_id)
    if has_order is True:
        stmt = stmt.where(CrmOpportunity.converted_order_id.is_not(None))
    elif has_order is False:
        stmt = stmt.where(CrmOpportunity.converted_order_id.is_(None))
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            (CrmOpportunity.code.like(kw)) | (CrmOpportunity.title.like(kw)) | (CrmOpportunity.remark.like(kw))
        )
    stmt = stmt.order_by(CrmOpportunity.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def list_public_pool_opportunities(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    stage: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[CrmOpportunity]:
    stmt = (
        select(CrmOpportunity)
        .where(CrmOpportunity.tenant_id == tenant_id, CrmOpportunity.owner_user_id.is_(None))
        .options(selectinload(CrmOpportunity.customer))
        .order_by(CrmOpportunity.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if stage:
        stmt = stmt.where(CrmOpportunity.stage == stage)
    if status:
        stmt = stmt.where(CrmOpportunity.status == status)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            (CrmOpportunity.code.like(kw)) | (CrmOpportunity.title.like(kw)) | (CrmOpportunity.remark.like(kw))
        )
    return db.scalars(stmt).all()


def opportunity_stage_stats(
    db: Session,
    tenant_id: int,
    date_from,
    date_to,
) -> list[dict]:
    stmt = (
        select(
            CrmOpportunity.stage,
            CrmOpportunity.status,
            func.count(CrmOpportunity.id).label("cnt"),
            func.sum(CrmOpportunity.amount).label("amt"),
        )
        .where(CrmOpportunity.tenant_id == tenant_id)
        .where(CrmOpportunity.is_active.is_(True))
    )
    if date_from:
        stmt = stmt.where(CrmOpportunity.created_at >= date_from)
    if date_to:
        stmt = stmt.where(CrmOpportunity.created_at <= date_to)
    stmt = stmt.group_by(CrmOpportunity.stage, CrmOpportunity.status).order_by(CrmOpportunity.stage, CrmOpportunity.status)
    rows = db.execute(stmt).all()
    return [{"stage": r.stage, "status": r.status, "count": int(r.cnt or 0), "amount": float(r.amt or 0)} for r in rows]


def list_due_followups(
    db: Session,
    tenant_id: int,
    now: datetime | None = None,
    limit: int = 500,
) -> list[CrmOpportunityActivity]:
    now = now or datetime.now(timezone.utc)
    stmt = (
        select(CrmOpportunityActivity)
        .join(CrmOpportunity, CrmOpportunity.id == CrmOpportunityActivity.opportunity_id)
        .where(
            CrmOpportunityActivity.tenant_id == tenant_id,
            CrmOpportunityActivity.next_follow_up_at.is_not(None),
            CrmOpportunityActivity.next_follow_up_at <= now,
            CrmOpportunity.is_active.is_(True),
            CrmOpportunity.status == "open",
        )
        .options(selectinload(CrmOpportunityActivity.opportunity).selectinload(CrmOpportunity.owner))
        .order_by(CrmOpportunityActivity.next_follow_up_at.asc())
        .limit(limit)
    )
    return db.scalars(stmt).all()


def recycle_stale_opportunities(db: Session, tenant_id: int, days: int, now: datetime | None = None) -> list[tuple[int, int | None]]:
    if days <= 0:
        return []
    now = now or datetime.now(timezone.utc)
    threshold = now - timedelta(days=days)

    last_act = (
        select(
            CrmOpportunityActivity.opportunity_id.label("opportunity_id"),
            func.max(CrmOpportunityActivity.created_at).label("last_at"),
        )
        .where(CrmOpportunityActivity.tenant_id == tenant_id)
        .group_by(CrmOpportunityActivity.opportunity_id)
        .subquery()
    )

    last_time = func.coalesce(last_act.c.last_at, CrmOpportunity.created_at)
    stmt = (
        select(CrmOpportunity.id, CrmOpportunity.owner_user_id)
        .outerjoin(last_act, last_act.c.opportunity_id == CrmOpportunity.id)
        .where(
            CrmOpportunity.tenant_id == tenant_id,
            CrmOpportunity.owner_user_id.is_not(None),
            CrmOpportunity.is_active.is_(True),
            CrmOpportunity.status == "open",
            last_time < threshold,
        )
        .order_by(CrmOpportunity.id.desc())
        .limit(500)
    )
    rows = db.execute(stmt).all()
    if not rows:
        return []
    recycled: list[tuple[int, int | None]] = [(int(r[0]), int(r[1]) if r[1] is not None else None) for r in rows]
    ids = [x[0] for x in recycled]
    db.execute(update(CrmOpportunity).where(CrmOpportunity.tenant_id == tenant_id, CrmOpportunity.id.in_(ids)).values(owner_user_id=None))
    db.flush()
    return recycled


def opportunity_stats(
    db: Session,
    tenant_id: int,
    group_by: str,
    date_from: datetime | None,
    date_to: datetime | None,
    owner_user_id: int | None = None,
    customer_id: int | None = None,
) -> list[dict]:
    base_filters = [CrmOpportunity.tenant_id == tenant_id, CrmOpportunity.is_active.is_(True)]
    if date_from:
        base_filters.append(CrmOpportunity.created_at >= date_from)
    if date_to:
        base_filters.append(CrmOpportunity.created_at <= date_to)
    if owner_user_id is not None:
        base_filters.append(CrmOpportunity.owner_user_id == owner_user_id)
    if customer_id is not None:
        base_filters.append(CrmOpportunity.customer_id == customer_id)

    amount_sum = func.sum(CrmOpportunity.amount).label("amt")
    cnt = func.count(CrmOpportunity.id).label("cnt")

    if group_by == "stage":
        stmt = select(CrmOpportunity.stage, CrmOpportunity.status, cnt, amount_sum).where(*base_filters).group_by(CrmOpportunity.stage, CrmOpportunity.status)
        rows = db.execute(stmt.order_by(CrmOpportunity.stage, CrmOpportunity.status)).all()
        return [{"stage": r.stage, "status": r.status, "count": int(r.cnt or 0), "amount": float(r.amt or 0)} for r in rows]

    if group_by == "owner":
        stmt = (
            select(CrmOpportunity.owner_user_id, User.full_name.label("owner_name"), cnt, amount_sum)
            .select_from(CrmOpportunity)
            .outerjoin(User, User.id == CrmOpportunity.owner_user_id)
            .where(*base_filters)
            .group_by(CrmOpportunity.owner_user_id, User.full_name)
            .order_by(cnt.desc())
        )
        rows = db.execute(stmt).all()
        return [{"owner_user_id": r.owner_user_id, "owner_name": r.owner_name, "count": int(r.cnt or 0), "amount": float(r.amt or 0)} for r in rows]

    if group_by == "customer":
        stmt = (
            select(CrmOpportunity.customer_id, Customer.name.label("customer_name"), cnt, amount_sum)
            .select_from(CrmOpportunity)
            .join(Customer, Customer.id == CrmOpportunity.customer_id)
            .where(*base_filters)
            .group_by(CrmOpportunity.customer_id, Customer.name)
            .order_by(cnt.desc())
        )
        rows = db.execute(stmt).all()
        return [{"customer_id": r.customer_id, "customer_name": r.customer_name, "count": int(r.cnt or 0), "amount": float(r.amt or 0)} for r in rows]

    if group_by == "owner_stage":
        stmt = (
            select(
                CrmOpportunity.owner_user_id,
                User.full_name.label("owner_name"),
                CrmOpportunity.stage,
                CrmOpportunity.status,
                cnt,
                amount_sum,
            )
            .select_from(CrmOpportunity)
            .outerjoin(User, User.id == CrmOpportunity.owner_user_id)
            .where(*base_filters)
            .group_by(CrmOpportunity.owner_user_id, User.full_name, CrmOpportunity.stage, CrmOpportunity.status)
            .order_by(CrmOpportunity.owner_user_id, CrmOpportunity.stage, CrmOpportunity.status)
        )
        rows = db.execute(stmt).all()
        return [
            {
                "owner_user_id": r.owner_user_id,
                "owner_name": r.owner_name,
                "stage": r.stage,
                "status": r.status,
                "count": int(r.cnt or 0),
                "amount": float(r.amt or 0),
            }
            for r in rows
        ]

    if group_by == "customer_stage":
        stmt = (
            select(
                CrmOpportunity.customer_id,
                Customer.name.label("customer_name"),
                CrmOpportunity.stage,
                CrmOpportunity.status,
                cnt,
                amount_sum,
            )
            .select_from(CrmOpportunity)
            .join(Customer, Customer.id == CrmOpportunity.customer_id)
            .where(*base_filters)
            .group_by(CrmOpportunity.customer_id, Customer.name, CrmOpportunity.stage, CrmOpportunity.status)
            .order_by(CrmOpportunity.customer_id, CrmOpportunity.stage, CrmOpportunity.status)
        )
        rows = db.execute(stmt).all()
        return [
            {
                "customer_id": r.customer_id,
                "customer_name": r.customer_name,
                "stage": r.stage,
                "status": r.status,
                "count": int(r.cnt or 0),
                "amount": float(r.amt or 0),
            }
            for r in rows
        ]

    raise ValueError("group_by 不支持")


# ============================
# Lead (线索)
# ============================
def create_lead(
    db: Session,
    tenant_id: int,
    contact_name: str,
    company: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    mobile: str | None = None,
    wechat: str | None = None,
    position: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    province: str | None = None,
    city: str | None = None,
    address: str | None = None,
    website: str | None = None,
    source: str | None = None,
    interest_products: list[int] | None = None,
    remark: str | None = None,
    owner_user_id: int | None = None,
    campaign_id: int | None = None,
):
    if CrmLead is None:
        return None
    item = CrmLead(
        tenant_id=tenant_id,
        code=f"LD{tenant_id}{int(datetime.utcnow().timestamp() * 1000)}",
        contact_name=contact_name,
        company=company,
        email=email,
        phone=phone,
        mobile=mobile,
        wechat=wechat,
        position=position,
        industry=industry,
        country=country,
        province=province,
        city=city,
        address=address,
        website=website,
        source=source,
        interest_products=interest_products or [],
        remark=remark,
        owner_user_id=owner_user_id,
        campaign_id=campaign_id,
        status="new",
        is_public_pool=owner_user_id is None,
    )
    item.score = _calc_lead_score(item)
    item.grade = _score_to_grade(item.score)
    db.add(item)
    db.flush()
    return item


def get_lead_by_id(db: Session, tenant_id: int, lead_id: int):
    if CrmLead is None:
        return None
    return db.scalar(select(CrmLead).where(CrmLead.tenant_id == tenant_id, CrmLead.id == lead_id))


def list_leads(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    status: str | None = None,
    source: str | None = None,
    grade: str | None = None,
    owner_user_id: int | None = None,
    is_public_pool: bool | None = None,
    offset: int = 0,
    limit: int = 50,
    scope_stmt=None,
):
    if CrmLead is None:
        return []
    stmt = select(CrmLead).where(CrmLead.tenant_id == tenant_id)
    if scope_stmt is not None:
        stmt = scope_stmt(stmt)
    if status:
        stmt = stmt.where(CrmLead.status == status)
    if source:
        stmt = stmt.where(CrmLead.source == source)
    if grade:
        stmt = stmt.where(CrmLead.grade == grade)
    if owner_user_id is not None:
        stmt = stmt.where(CrmLead.owner_user_id == owner_user_id)
    if is_public_pool is not None:
        stmt = stmt.where(CrmLead.is_public_pool == is_public_pool)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                CrmLead.code.like(kw),
                CrmLead.contact_name.like(kw),
                CrmLead.company.like(kw),
                CrmLead.email.like(kw),
                CrmLead.phone.like(kw),
            )
        )
    stmt = stmt.order_by(CrmLead.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def update_lead(db: Session, lead, **kwargs):
    if lead is None:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(lead, k, v)
    score = _calc_lead_score(lead)
    lead.score = score
    lead.grade = _score_to_grade(score)
    if hasattr(lead, "owner_user_id"):
        lead.is_public_pool = lead.owner_user_id is None
    db.flush()
    return lead


def deactivate_lead(db: Session, lead):
    if lead is None:
        return None
    if hasattr(lead, "is_active"):
        lead.is_active = False
    else:
        lead.status = "archived"
    db.flush()
    return lead


def claim_lead_from_pool(db: Session, tenant_id: int, lead_id: int, user_id: int):
    lead = get_lead_by_id(db, tenant_id, lead_id)
    if lead is None:
        return None
    lead.owner_user_id = user_id
    lead.is_public_pool = False
    db.flush()
    return lead


def release_lead_to_pool(db: Session, tenant_id: int, lead_id: int):
    lead = get_lead_by_id(db, tenant_id, lead_id)
    if lead is None:
        return None
    lead.owner_user_id = None
    lead.is_public_pool = True
    db.flush()
    return lead


def recycle_stale_leads(db: Session, tenant_id: int, days: int = 30):
    if CrmLead is None or CrmLeadActivity is None:
        return []
    if days <= 0:
        return []
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=days)

    last_act = (
        select(
            CrmLeadActivity.lead_id.label("lead_id"),
            func.max(CrmLeadActivity.created_at).label("last_at"),
        )
        .where(CrmLeadActivity.tenant_id == tenant_id)
        .group_by(CrmLeadActivity.lead_id)
        .subquery()
    )
    last_time = func.coalesce(last_act.c.last_at, CrmLead.created_at)
    stmt = (
        select(CrmLead.id, CrmLead.owner_user_id)
        .outerjoin(last_act, last_act.c.lead_id == CrmLead.id)
        .where(
            CrmLead.tenant_id == tenant_id,
            CrmLead.owner_user_id.is_not(None),
            CrmLead.status != "converted",
            last_time < threshold,
        )
        .limit(500)
    )
    rows = db.execute(stmt).all()
    if not rows:
        return []
    recycled = [(int(r[0]), int(r[1]) if r[1] is not None else None) for r in rows]
    ids = [x[0] for x in recycled]
    db.execute(
        update(CrmLead)
        .where(CrmLead.tenant_id == tenant_id, CrmLead.id.in_(ids))
        .values(owner_user_id=None, is_public_pool=True)
    )
    db.flush()
    return recycled


def convert_lead(
    db: Session,
    tenant_id: int,
    lead_id: int,
    user_id: int,
    convert_to_customer: bool = True,
    convert_to_opportunity: bool = True,
    opportunity_title: str | None = None,
    opportunity_stage: str = "prospecting",
    opportunity_amount: Decimal | None = None,
):
    lead = get_lead_by_id(db, tenant_id, lead_id)
    if lead is None:
        return None

    customer = None
    opportunity = None

    if convert_to_customer:
        customer = Customer(
            tenant_id=tenant_id,
            code=f"CU{tenant_id}{int(datetime.utcnow().timestamp() * 1000)}",
            name=lead.company or lead.contact_name,
            email=lead.email,
            phone=lead.phone,
            country=lead.country,
            province=lead.province,
            city=lead.city,
            address=lead.address,
            website=lead.website,
            industry=lead.industry,
            source=lead.source,
            owner_user_id=lead.owner_user_id or user_id,
            remark=lead.remark,
            is_active=True,
        )
        db.add(customer)
        db.flush()
        lead.customer_id = customer.id

    if convert_to_opportunity:
        if customer is None:
            raise ValueError("转化为商机前必须先创建客户")
        opportunity = CrmOpportunity(
            tenant_id=tenant_id,
            customer_id=customer.id,
            code=f"OP{tenant_id}{int(datetime.utcnow().timestamp() * 1000)}",
            title=opportunity_title or customer.name,
            stage=opportunity_stage,
            status="open",
            amount=opportunity_amount,
            probability=None,
            expected_close_date=None,
            owner_user_id=lead.owner_user_id or user_id,
            remark=lead.remark,
            is_active=True,
        )
        db.add(opportunity)
        db.flush()
        lead.opportunity_id = opportunity.id

    lead.status = "converted"
    lead.converted_at = datetime.now(timezone.utc)
    db.flush()
    return {"lead": lead, "customer": customer, "opportunity": opportunity}


def create_lead_activity(
    db: Session,
    tenant_id: int,
    lead_id: int,
    action_type: str,
    content: str,
    created_by: int | None = None,
    next_follow_up_at: datetime | None = None,
):
    if CrmLeadActivity is None:
        return None
    item = CrmLeadActivity(
        tenant_id=tenant_id,
        lead_id=lead_id,
        action_type=action_type,
        content=content,
        created_by=created_by,
        next_follow_up_at=next_follow_up_at,
    )
    db.add(item)
    # 更新线索的最后跟进时间
    lead = get_lead_by_id(db, tenant_id, lead_id)
    if lead is not None:
        lead.last_follow_up_at = datetime.now(timezone.utc)
        if next_follow_up_at is not None:
            lead.next_follow_up_at = next_follow_up_at
    db.flush()
    return item


def list_lead_activities(db: Session, tenant_id: int, lead_id: int):
    if CrmLeadActivity is None:
        return []
    stmt = (
        select(CrmLeadActivity)
        .where(CrmLeadActivity.tenant_id == tenant_id, CrmLeadActivity.lead_id == lead_id)
        .order_by(CrmLeadActivity.id.desc())
    )
    return db.scalars(stmt).all()


def lead_summary(db: Session, tenant_id: int) -> dict:
    if CrmLead is None:
        return {
            "total": 0,
            "by_status": {},
            "by_grade": {},
            "by_source": {},
            "public_pool": 0,
            "converted": 0,
        }
    total = db.scalar(select(func.count(CrmLead.id)).where(CrmLead.tenant_id == tenant_id)) or 0
    public_pool = (
        db.scalar(
            select(func.count(CrmLead.id)).where(
                CrmLead.tenant_id == tenant_id, CrmLead.is_public_pool.is_(True)
            )
        )
        or 0
    )
    converted = (
        db.scalar(
            select(func.count(CrmLead.id)).where(
                CrmLead.tenant_id == tenant_id, CrmLead.status == "converted"
            )
        )
        or 0
    )

    def _group(col):
        rows = db.execute(select(col, func.count(CrmLead.id)).where(CrmLead.tenant_id == tenant_id).group_by(col)).all()
        return {str(r[0] or "unknown"): int(r[1] or 0) for r in rows}

    return {
        "total": int(total),
        "by_status": _group(CrmLead.status),
        "by_grade": _group(CrmLead.grade),
        "by_source": _group(CrmLead.source),
        "public_pool": int(public_pool),
        "converted": int(converted),
    }


def _calc_lead_score(lead) -> int:
    if lead is None:
        return 0
    score = 10
    # 邮箱+10、手机+10、公司+15、职位+10、行业+5、地址+5、官网+5
    if getattr(lead, "email", None):
        score += 10
    if getattr(lead, "mobile", None) or getattr(lead, "phone", None):
        score += 10
    if getattr(lead, "company", None):
        score += 15
    if getattr(lead, "position", None):
        score += 10
    if getattr(lead, "industry", None):
        score += 5
    if getattr(lead, "address", None):
        score += 5
    if getattr(lead, "website", None):
        score += 5
    # 高价值来源+10
    if getattr(lead, "source", None) in {"referral", "paid_search", "exhibition"}:
        score += 10
    return score


def _score_to_grade(score) -> str:
    if score is None:
        return "C"
    if score >= 60:
        return "A"
    if score >= 40:
        return "B"
    return "C"


# ============================
# Quotation (报价单)
# ============================
def create_quotation_with_items(
    db: Session,
    tenant_id: int,
    customer_id: int,
    title: str,
    items_data: list[dict],
    opportunity_id: int | None = None,
    contact_id: int | None = None,
    valid_from: date | None = None,
    valid_until: date | None = None,
    currency: str = "CNY",
    tax_rate: Decimal = Decimal("0"),
    discount_rate: Decimal = Decimal("0"),
    payment_terms: str | None = None,
    delivery_terms: str | None = None,
    owner_user_id: int | None = None,
    remark: str | None = None,
):
    if CrmQuotation is None or CrmQuotationItem is None:
        return None
    if not items_data:
        raise ValueError("报价单至少需要一个商品行")

    subtotal = Decimal("0")
    for it in items_data:
        qty = Decimal(str(it.get("quantity", 0)))
        price = Decimal(str(it.get("unit_price", 0)))
        line_amount = qty * price
        subtotal += line_amount

    discount_amount = subtotal * (Decimal(str(discount_rate)) or Decimal("0"))
    net = subtotal - discount_amount
    tax_amount = net * (Decimal(str(tax_rate)) or Decimal("0"))
    total_amount = net + tax_amount

    quotation = CrmQuotation(
        tenant_id=tenant_id,
        code=f"Q{tenant_id}{int(datetime.utcnow().timestamp() * 1000)}",
        title=title,
        customer_id=customer_id,
        opportunity_id=opportunity_id,
        contact_id=contact_id,
        version=1,
        parent_id=None,
        status="draft",
        valid_from=valid_from or date.today(),
        valid_until=valid_until or (date.today() + timedelta(days=30)),
        currency=currency,
        tax_rate=Decimal(str(tax_rate)),
        discount_rate=Decimal(str(discount_rate)),
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        payment_terms=payment_terms,
        delivery_terms=delivery_terms,
        owner_user_id=owner_user_id,
        remark=remark,
    )
    db.add(quotation)
    db.flush()

    for it in items_data:
        qty = Decimal(str(it.get("quantity", 0)))
        price = Decimal(str(it.get("unit_price", 0)))
        disc = Decimal(str(it.get("discount_rate", 0)))
        tr = Decimal(str(it.get("tax_rate", 0)))
        amount = qty * price * (Decimal("1") - disc)
        item = CrmQuotationItem(
            tenant_id=tenant_id,
            quotation_id=quotation.id,
            product_id=it.get("product_id"),
            sku_id=it.get("sku_id"),
            product_name=it.get("product_name", ""),
            spec=it.get("spec"),
            quantity=qty,
            unit_price=price,
            discount_rate=disc,
            tax_rate=tr,
            amount=amount,
            delivery_date=it.get("delivery_date"),
            remark=it.get("remark"),
        )
        db.add(item)
    db.flush()
    return quotation


def get_quotation_by_id(db: Session, tenant_id: int, quotation_id: int):
    if CrmQuotation is None:
        return None
    return db.scalar(
        select(CrmQuotation).where(CrmQuotation.tenant_id == tenant_id, CrmQuotation.id == quotation_id)
    )


def get_quotation_items(db: Session, tenant_id: int, quotation_id: int):
    if CrmQuotationItem is None:
        return []
    stmt = select(CrmQuotationItem).where(
        CrmQuotationItem.tenant_id == tenant_id, CrmQuotationItem.quotation_id == quotation_id
    )
    return db.scalars(stmt).all()


def list_quotations(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    opportunity_id: int | None = None,
    owner_user_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    scope_stmt=None,
):
    if CrmQuotation is None:
        return []
    stmt = select(CrmQuotation).where(CrmQuotation.tenant_id == tenant_id)
    if scope_stmt is not None:
        stmt = scope_stmt(stmt)
    if status:
        stmt = stmt.where(CrmQuotation.status == status)
    if customer_id is not None:
        stmt = stmt.where(CrmQuotation.customer_id == customer_id)
    if opportunity_id is not None:
        stmt = stmt.where(CrmQuotation.opportunity_id == opportunity_id)
    if owner_user_id is not None:
        stmt = stmt.where(CrmQuotation.owner_user_id == owner_user_id)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(CrmQuotation.code.like(kw), CrmQuotation.title.like(kw), CrmQuotation.remark.like(kw)))
    stmt = stmt.order_by(CrmQuotation.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def update_quotation(db: Session, quotation, items_data: list[dict] | None = None, **kwargs):
    if quotation is None:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(quotation, k, v)

    if items_data is not None and CrmQuotationItem is not None:
        # 清空旧明细
        db.execute(
            delete(CrmQuotationItem).where(
                CrmQuotationItem.tenant_id == quotation.tenant_id,
                CrmQuotationItem.quotation_id == quotation.id,
            )
        )
        subtotal = Decimal("0")
        for it in items_data:
            qty = Decimal(str(it.get("quantity", 0)))
            price = Decimal(str(it.get("unit_price", 0)))
            disc = Decimal(str(it.get("discount_rate", 0) or 0))
            tr = Decimal(str(it.get("tax_rate", 0) or 0))
            amount = qty * price * (Decimal("1") - disc)
            subtotal += qty * price
            db.add(
                CrmQuotationItem(
                    tenant_id=quotation.tenant_id,
                    quotation_id=quotation.id,
                    product_id=it.get("product_id"),
                    sku_id=it.get("sku_id"),
                    product_name=it.get("product_name", ""),
                    spec=it.get("spec"),
                    quantity=qty,
                    unit_price=price,
                    discount_rate=disc,
                    tax_rate=tr,
                    amount=amount,
                    delivery_date=it.get("delivery_date"),
                    remark=it.get("remark"),
                )
            )
        discount_amount = subtotal * (Decimal(str(getattr(quotation, "discount_rate", 0))) or Decimal("0"))
        net = subtotal - discount_amount
        tax_amount = net * (Decimal(str(getattr(quotation, "tax_rate", 0))) or Decimal("0"))
        quotation.subtotal = subtotal
        quotation.tax_amount = tax_amount
        quotation.total_amount = net + tax_amount
    db.flush()
    return quotation


def create_quotation_new_version(db: Session, tenant_id: int, quotation_id: int, user_id: int):
    if CrmQuotation is None:
        return None
    old = get_quotation_by_id(db, tenant_id, quotation_id)
    if old is None:
        return None
    old_items = get_quotation_items(db, tenant_id, quotation_id)

    new_data_items = [
        {
            "product_id": it.product_id,
            "sku_id": it.sku_id,
            "product_name": it.product_name,
            "spec": it.spec,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "discount_rate": it.discount_rate,
            "tax_rate": it.tax_rate,
            "delivery_date": it.delivery_date,
            "remark": it.remark,
        }
        for it in old_items
    ]
    new_quotation = create_quotation_with_items(
        db,
        tenant_id=tenant_id,
        customer_id=old.customer_id,
        title=old.title,
        items_data=new_data_items,
        opportunity_id=old.opportunity_id,
        contact_id=getattr(old, "contact_id", None),
        valid_from=old.valid_from,
        valid_until=old.valid_until,
        currency=old.currency,
        tax_rate=old.tax_rate,
        discount_rate=old.discount_rate,
        payment_terms=old.payment_terms,
        delivery_terms=old.delivery_terms,
        owner_user_id=user_id,
        remark=old.remark,
    )
    if new_quotation is not None:
        new_quotation.version = (old.version or 1) + 1
        new_quotation.parent_id = old.id
        db.flush()
    return new_quotation


def send_quotation(db: Session, quotation):
    if quotation is None:
        return None
    quotation.status = "sent"
    quotation.sent_at = datetime.now(timezone.utc)
    db.flush()
    return quotation


def accept_quotation(db: Session, quotation):
    if quotation is None:
        return None
    quotation.status = "accepted"
    quotation.accepted_at = datetime.now(timezone.utc)
    db.flush()
    return quotation


def reject_quotation(db: Session, quotation, reason: str | None = None):
    if quotation is None:
        return None
    quotation.status = "rejected"
    quotation.rejected_at = datetime.now(timezone.utc)
    quotation.reject_reason = reason
    db.flush()
    return quotation


def deactivate_quotation(db: Session, quotation):
    if quotation is None:
        return None
    if hasattr(quotation, "is_active"):
        quotation.is_active = False
    else:
        quotation.status = "archived"
    db.flush()
    return quotation


def convert_quotation_to_order(db: Session, tenant_id: int, quotation_id: int, user_id: int):
    quotation = get_quotation_by_id(db, tenant_id, quotation_id)
    if quotation is None:
        return None
    # 该实现占位：真实订单模型不在本文件内，这里仅更新报价单状态并返回结构化结果
    quotation.status = "ordered"
    quotation.converted_order_id = None  # 调用方可按需替换为真实 order.id
    if hasattr(quotation, "owner_user_id") and quotation.owner_user_id is None:
        quotation.owner_user_id = user_id
    db.flush()
    return {"quotation": quotation, "items": get_quotation_items(db, tenant_id, quotation_id)}


# ============================
# Contract (合同) & Payment Plan
# ============================
def create_contract_with_plan(
    db: Session,
    tenant_id: int,
    customer_id: int,
    name: str,
    plan_rows: list[dict],
    **kwargs,
):
    if CrmContract is None or CrmPaymentPlan is None:
        return None
    total = Decimal("0")
    for row in plan_rows:
        total += Decimal(str(row.get("amount", 0)))

    contract = CrmContract(
        tenant_id=tenant_id,
        code=f"CT{tenant_id}{int(datetime.utcnow().timestamp() * 1000)}",
        name=name,
        customer_id=customer_id,
        opportunity_id=kwargs.get("opportunity_id"),
        quotation_id=kwargs.get("quotation_id"),
        order_id=kwargs.get("order_id"),
        type=kwargs.get("type", "sales"),
        status=kwargs.get("status", "draft"),
        sign_date=kwargs.get("sign_date"),
        start_date=kwargs.get("start_date"),
        end_date=kwargs.get("end_date"),
        auto_renewal=kwargs.get("auto_renewal", False),
        renewal_notice_days=kwargs.get("renewal_notice_days", 30),
        total_amount=total,
        currency=kwargs.get("currency", "CNY"),
        payment_terms=kwargs.get("payment_terms"),
        owner_user_id=kwargs.get("owner_user_id"),
        parent_contract_id=kwargs.get("parent_contract_id"),
        renewal_count=kwargs.get("renewal_count", 0),
        remark=kwargs.get("remark"),
    )
    db.add(contract)
    db.flush()

    for row in plan_rows:
        amount = Decimal(str(row.get("amount", 0)))
        actual = Decimal(str(row.get("actual_amount", 0) or 0))
        status = row.get("status") or _calc_payment_status(actual, amount, row.get("due_date"))
        db.add(
            CrmPaymentPlan(
                tenant_id=tenant_id,
                contract_id=contract.id,
                phase=str(row.get("phase", "")),
                phase_name=str(row.get("phase_name", "")),
                due_date=row.get("due_date"),
                amount=amount,
                actual_amount=actual,
                actual_date=row.get("actual_date"),
                status=status,
                invoice_no=row.get("invoice_no"),
                remark=row.get("remark"),
            )
        )
    db.flush()
    return contract


def get_contract_by_id(db: Session, tenant_id: int, contract_id: int):
    if CrmContract is None:
        return None
    return db.scalar(
        select(CrmContract).where(CrmContract.tenant_id == tenant_id, CrmContract.id == contract_id)
    )


def get_payment_plans_by_contract(db: Session, tenant_id: int, contract_id: int):
    if CrmPaymentPlan is None:
        return []
    stmt = select(CrmPaymentPlan).where(
        CrmPaymentPlan.tenant_id == tenant_id, CrmPaymentPlan.contract_id == contract_id
    )
    return db.scalars(stmt).all()


def list_contracts(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    status: str | None = None,
    type: str | None = None,
    customer_id: int | None = None,
    owner_user_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    scope_stmt=None,
):
    if CrmContract is None:
        return []
    stmt = select(CrmContract).where(CrmContract.tenant_id == tenant_id)
    if scope_stmt is not None:
        stmt = scope_stmt(stmt)
    if status:
        stmt = stmt.where(CrmContract.status == status)
    if type:
        stmt = stmt.where(CrmContract.type == type)
    if customer_id is not None:
        stmt = stmt.where(CrmContract.customer_id == customer_id)
    if owner_user_id is not None:
        stmt = stmt.where(CrmContract.owner_user_id == owner_user_id)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(CrmContract.code.like(kw), CrmContract.name.like(kw), CrmContract.remark.like(kw)))
    stmt = stmt.order_by(CrmContract.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def update_contract(db: Session, contract, plan_rows: list[dict] | None = None, **kwargs):
    if contract is None:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(contract, k, v)

    if plan_rows is not None and CrmPaymentPlan is not None:
        db.execute(
            delete(CrmPaymentPlan).where(
                CrmPaymentPlan.tenant_id == contract.tenant_id, CrmPaymentPlan.contract_id == contract.id
            )
        )
        total = Decimal("0")
        for row in plan_rows:
            amount = Decimal(str(row.get("amount", 0)))
            total += amount
            actual = Decimal(str(row.get("actual_amount", 0) or 0))
            status = row.get("status") or _calc_payment_status(actual, amount, row.get("due_date"))
            db.add(
                CrmPaymentPlan(
                    tenant_id=contract.tenant_id,
                    contract_id=contract.id,
                    phase=str(row.get("phase", "")),
                    phase_name=str(row.get("phase_name", "")),
                    due_date=row.get("due_date"),
                    amount=amount,
                    actual_amount=actual,
                    actual_date=row.get("actual_date"),
                    status=status,
                    invoice_no=row.get("invoice_no"),
                    remark=row.get("remark"),
                )
            )
        contract.total_amount = total
    db.flush()
    return contract


def update_payment_plan_paid(
    db: Session,
    tenant_id: int,
    plan_id: int,
    actual_amount: Decimal,
    actual_date: date | None = None,
    invoice_no: str | None = None,
):
    if CrmPaymentPlan is None:
        return None
    plan = db.scalar(
        select(CrmPaymentPlan).where(CrmPaymentPlan.tenant_id == tenant_id, CrmPaymentPlan.id == plan_id)
    )
    if plan is None:
        return None
    plan.actual_amount = Decimal(str(actual_amount))
    plan.actual_date = actual_date or date.today()
    if invoice_no is not None:
        plan.invoice_no = invoice_no
    plan.status = _calc_payment_status(plan.actual_amount, plan.amount, plan.due_date)
    db.flush()
    return plan


def renew_contract(
    db: Session,
    tenant_id: int,
    contract_id: int,
    user_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
):
    if CrmContract is None:
        return None
    base = get_contract_by_id(db, tenant_id, contract_id)
    if base is None:
        return None
    existing_plans = get_payment_plans_by_contract(db, tenant_id, contract_id)
    new_rows = [
        {
            "phase": p.phase,
            "phase_name": p.phase_name,
            "due_date": p.due_date,
            "amount": p.amount,
            "actual_amount": Decimal("0"),
            "actual_date": None,
            "status": "pending",
            "invoice_no": None,
            "remark": None,
        }
        for p in existing_plans
    ]
    new_contract = create_contract_with_plan(
        db,
        tenant_id=tenant_id,
        customer_id=base.customer_id,
        name=f"{base.name} - 续签",
        plan_rows=new_rows,
        opportunity_id=base.opportunity_id,
        quotation_id=base.quotation_id,
        order_id=getattr(base, "order_id", None),
        type=base.type,
        status="draft",
        sign_date=date.today(),
        start_date=start_date or date.today(),
        end_date=end_date or getattr(base, "end_date", None),
        auto_renewal=getattr(base, "auto_renewal", False),
        renewal_notice_days=getattr(base, "renewal_notice_days", 30),
        currency=base.currency,
        payment_terms=base.payment_terms,
        owner_user_id=user_id,
        parent_contract_id=base.id,
        renewal_count=(base.renewal_count or 0) + 1,
        remark=base.remark,
    )
    return new_contract


def _calc_payment_status(actual, total, due_date) -> str:
    actual = Decimal(str(actual or 0))
    total = Decimal(str(total or 0))
    if total <= 0:
        return "pending"
    if actual >= total:
        return "paid"
    if actual > 0:
        return "partial"
    if due_date is not None and due_date < date.today():
        return "overdue"
    return "pending"


# ============================
# Win/Loss Reason
# ============================
def create_win_loss_reason(
    db: Session,
    tenant_id: int,
    type: str,
    category: str,
    code: str,
    name: str,
    description: str | None = None,
    sort_order: int = 0,
):
    if CrmWinLossReason is None:
        return None
    item = CrmWinLossReason(
        tenant_id=tenant_id,
        type=type,
        category=category,
        code=code,
        name=name,
        description=description,
        sort_order=sort_order,
        is_active=True,
    )
    db.add(item)
    db.flush()
    return item


def list_win_loss_reasons(db: Session, tenant_id: int, type: str | None = None):
    if CrmWinLossReason is None:
        return []
    stmt = select(CrmWinLossReason).where(CrmWinLossReason.tenant_id == tenant_id)
    if type:
        stmt = stmt.where(CrmWinLossReason.type == type)
    stmt = stmt.order_by(CrmWinLossReason.sort_order.asc(), CrmWinLossReason.id.desc())
    return db.scalars(stmt).all()


def get_win_loss_reason_by_id(db: Session, tenant_id: int, reason_id: int):
    if CrmWinLossReason is None:
        return None
    return db.scalar(
        select(CrmWinLossReason).where(CrmWinLossReason.tenant_id == tenant_id, CrmWinLossReason.id == reason_id)
    )


def update_win_loss_reason(db: Session, reason, **kwargs):
    if reason is None:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(reason, k, v)
    db.flush()
    return reason


def deactivate_win_loss_reason(db: Session, reason):
    if reason is None:
        return None
    if hasattr(reason, "is_active"):
        reason.is_active = False
    db.flush()
    return reason


# ============================
# Campaign (营销活动)
# ============================
def create_campaign(
    db: Session,
    tenant_id: int,
    name: str,
    type: str,
    start_date: date | None,
    end_date: date | None,
    budget: Decimal | None,
    currency: str = "CNY",
    **kwargs,
):
    if CrmCampaign is None:
        return None
    item = CrmCampaign(
        tenant_id=tenant_id,
        code=kwargs.get("code") or f"CAM{tenant_id}{int(datetime.utcnow().timestamp() * 1000)}",
        name=name,
        type=type,
        objective=kwargs.get("objective"),
        target_audience=kwargs.get("target_audience"),
        channel=kwargs.get("channel"),
        status=kwargs.get("status", "draft"),
        start_date=start_date,
        end_date=end_date,
        budget=Decimal(str(budget)) if budget is not None else None,
        actual_cost=Decimal(str(kwargs.get("actual_cost"))) if kwargs.get("actual_cost") is not None else None,
        expected_revenue=Decimal(str(kwargs.get("expected_revenue"))) if kwargs.get("expected_revenue") is not None else None,
        actual_revenue=Decimal(str(kwargs.get("actual_revenue"))) if kwargs.get("actual_revenue") is not None else None,
        currency=currency,
        target_leads_count=kwargs.get("target_leads_count"),
        landing_url=kwargs.get("landing_url"),
        utm_source=kwargs.get("utm_source"),
        utm_campaign=kwargs.get("utm_campaign"),
        owner_user_id=kwargs.get("owner_user_id"),
        remark=kwargs.get("remark"),
        is_active=True,
    )
    db.add(item)
    db.flush()
    return item


def get_campaign_by_id(db: Session, tenant_id: int, campaign_id: int):
    if CrmCampaign is None:
        return None
    return db.scalar(
        select(CrmCampaign).where(CrmCampaign.tenant_id == tenant_id, CrmCampaign.id == campaign_id)
    )


def list_campaigns(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    status: str | None = None,
    type: str | None = None,
    owner_user_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
):
    if CrmCampaign is None:
        return []
    stmt = select(CrmCampaign).where(CrmCampaign.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(CrmCampaign.status == status)
    if type:
        stmt = stmt.where(CrmCampaign.type == type)
    if owner_user_id is not None:
        stmt = stmt.where(CrmCampaign.owner_user_id == owner_user_id)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            or_(CrmCampaign.code.like(kw), CrmCampaign.name.like(kw), CrmCampaign.remark.like(kw))
        )
    stmt = stmt.order_by(CrmCampaign.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def update_campaign(db: Session, campaign, **kwargs):
    if campaign is None:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(campaign, k, v)
    db.flush()
    return campaign


def deactivate_campaign(db: Session, campaign):
    if campaign is None:
        return None
    if hasattr(campaign, "is_active"):
        campaign.is_active = False
    else:
        campaign.status = "archived"
    db.flush()
    return campaign


def campaign_add_members(db: Session, tenant_id: int, campaign_id: int, member_rows: list[dict]):
    if CrmCampaignMember is None:
        return []
    created = []
    for row in member_rows:
        member = CrmCampaignMember(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            member_type=str(row.get("member_type", "lead")),
            member_id=int(row.get("member_id", 0)),
            score_delta=int(row.get("score_delta", 0) or 0),
            joined_at=datetime.now(timezone.utc),
            remark=row.get("remark"),
        )
        db.add(member)
        created.append(member)
    db.flush()
    return created


def campaign_remove_member(db: Session, tenant_id: int, campaign_id: int, member_type: str, member_id: int):
    if CrmCampaignMember is None:
        return None
    item = db.scalar(
        select(CrmCampaignMember).where(
            CrmCampaignMember.tenant_id == tenant_id,
            CrmCampaignMember.campaign_id == campaign_id,
            CrmCampaignMember.member_type == member_type,
            CrmCampaignMember.member_id == member_id,
        )
    )
    if item is None:
        return None
    db.execute(delete(CrmCampaignMember).where(CrmCampaignMember.id == item.id))
    db.flush()
    return item


def campaign_get_members(db: Session, tenant_id: int, campaign_id: int):
    if CrmCampaignMember is None:
        return []
    stmt = select(CrmCampaignMember).where(
        CrmCampaignMember.tenant_id == tenant_id, CrmCampaignMember.campaign_id == campaign_id
    )
    return db.scalars(stmt).all()


def campaign_calculate_roi(db: Session, tenant_id: int, campaign_id: int) -> dict:
    campaign = get_campaign_by_id(db, tenant_id, campaign_id)
    if campaign is None:
        return {"roi": None, "cost": None, "revenue": None}
    cost = Decimal(str(campaign.actual_cost or 0))
    revenue = Decimal(str(campaign.actual_revenue or 0))
    if cost > 0:
        roi = float((revenue - cost) / cost)
    else:
        roi = None
    return {
        "roi": roi,
        "cost": float(cost),
        "revenue": float(revenue),
        "budget": float(campaign.budget) if campaign.budget is not None else None,
    }


# ============================
# Sales Target (销售目标)
# ============================
def create_sales_target(
    db: Session,
    tenant_id: int,
    period_type: str,
    period_start: date,
    period_end: date,
    dimension: str,
    metric: str,
    target_value: Decimal,
    currency: str = "CNY",
    owner_user_id: int | None = None,
    created_by: int | None = None,
    dimension_id: int | None = None,
):
    if CrmSalesTarget is None:
        return None
    item = CrmSalesTarget(
        tenant_id=tenant_id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        dimension=dimension,
        dimension_id=dimension_id,
        metric=metric,
        target_value=Decimal(str(target_value)),
        currency=currency,
        owner_user_id=owner_user_id,
        created_by=created_by,
        is_active=True,
    )
    db.add(item)
    db.flush()
    return item


def get_sales_target_by_id(db: Session, tenant_id: int, target_id: int):
    if CrmSalesTarget is None:
        return None
    return db.scalar(
        select(CrmSalesTarget).where(CrmSalesTarget.tenant_id == tenant_id, CrmSalesTarget.id == target_id)
    )


def list_sales_targets(
    db: Session,
    tenant_id: int,
    period_type: str | None = None,
    dimension: str | None = None,
    owner_user_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
):
    if CrmSalesTarget is None:
        return []
    stmt = select(CrmSalesTarget).where(CrmSalesTarget.tenant_id == tenant_id)
    if period_type:
        stmt = stmt.where(CrmSalesTarget.period_type == period_type)
    if dimension:
        stmt = stmt.where(CrmSalesTarget.dimension == dimension)
    if owner_user_id is not None:
        stmt = stmt.where(CrmSalesTarget.owner_user_id == owner_user_id)
    stmt = stmt.order_by(CrmSalesTarget.period_start.desc(), CrmSalesTarget.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def update_sales_target(db: Session, target, **kwargs):
    if target is None:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(target, k, v)
    db.flush()
    return target


def deactivate_sales_target(db: Session, target):
    if target is None:
        return None
    if hasattr(target, "is_active"):
        target.is_active = False
    db.flush()
    return target


def calculate_target_achievement(db: Session, tenant_id: int, target_id: int) -> dict:
    target = get_sales_target_by_id(db, tenant_id, target_id)
    if target is None:
        return {"target": None, "actual": None, "achievement_ratio": None}

    metric = (target.metric or "").lower()
    owner_user_id = target.owner_user_id
    period_start = target.period_start
    period_end = target.period_end

    actual = Decimal("0")
    if metric in {"amount", "revenue", "sales"}:
        # 简单估算：取所属期间内 owner 对应的商机金额
        stmt = select(func.sum(CrmOpportunity.amount)).where(
            CrmOpportunity.tenant_id == tenant_id,
            CrmOpportunity.is_active.is_(True),
            CrmOpportunity.status == "won",
            CrmOpportunity.created_at >= datetime.combine(period_start, datetime.min.time()),
            CrmOpportunity.created_at <= datetime.combine(period_end, datetime.max.time()),
        )
        if owner_user_id is not None:
            stmt = stmt.where(CrmOpportunity.owner_user_id == owner_user_id)
        value = db.scalar(stmt)
        actual = Decimal(str(value or 0))
    elif metric in {"count", "leads"}:
        stmt = select(func.count(CrmOpportunity.id)).where(
            CrmOpportunity.tenant_id == tenant_id,
            CrmOpportunity.is_active.is_(True),
            CrmOpportunity.created_at >= datetime.combine(period_start, datetime.min.time()),
            CrmOpportunity.created_at <= datetime.combine(period_end, datetime.max.time()),
        )
        if owner_user_id is not None:
            stmt = stmt.where(CrmOpportunity.owner_user_id == owner_user_id)
        value = db.scalar(stmt) or 0
        actual = Decimal(str(value))

    target_value = Decimal(str(target.target_value or 0))
    ratio = float(actual / target_value) if target_value > 0 else None
    return {
        "target": float(target_value),
        "actual": float(actual),
        "achievement_ratio": ratio,
    }


# ============================
# Customer Profile / 360
# ============================
def recalculate_customer_profile(db: Session, tenant_id: int, customer_id: int):
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id)
    )
    if customer is None:
        return None
    # 商机统计
    total_opp = db.scalar(
        select(func.count(CrmOpportunity.id)).where(
            CrmOpportunity.tenant_id == tenant_id,
            CrmOpportunity.customer_id == customer_id,
            CrmOpportunity.is_active.is_(True),
        )
    ) or 0
    won_opp = db.scalar(
        select(func.count(CrmOpportunity.id)).where(
            CrmOpportunity.tenant_id == tenant_id,
            CrmOpportunity.customer_id == customer_id,
            CrmOpportunity.status == "won",
        )
    ) or 0
    amount_sum = db.scalar(
        select(func.sum(CrmOpportunity.amount)).where(
            CrmOpportunity.tenant_id == tenant_id,
            CrmOpportunity.customer_id == customer_id,
            CrmOpportunity.status == "won",
        )
    ) or Decimal("0")

    # 等级根据成交商机金额粗略划分
    amount_sum = Decimal(str(amount_sum or 0))
    if amount_sum >= Decimal("1000000"):
        grade = "A"
    elif amount_sum >= Decimal("100000"):
        grade = "B"
    else:
        grade = "C"

    if hasattr(customer, "grade"):
        customer.grade = grade
    if hasattr(customer, "total_opportunity_count"):
        customer.total_opportunity_count = int(total_opp)
    if hasattr(customer, "won_opportunity_count"):
        customer.won_opportunity_count = int(won_opp)
    if hasattr(customer, "total_amount"):
        customer.total_amount = amount_sum
    db.flush()
    return customer


def get_customer_360(db: Session, tenant_id: int, customer_id: int) -> dict:
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id)
    )
    if customer is None:
        return {}

    contacts = list_customer_contacts(db, tenant_id, customer_id)
    tags = [link.tag for link in db.scalars(
        select(CustomerTagLink).where(
            CustomerTagLink.tenant_id == tenant_id, CustomerTagLink.customer_id == customer_id
        ).options(selectinload(CustomerTagLink.tag))
    ).all() if link.tag is not None]
    opportunities = list_opportunities(db, tenant_id, customer_id)

    total_opp = len(opportunities)
    won_opp = [o for o in opportunities if getattr(o, "status", "") == "won"]
    amount_sum = Decimal("0")
    for o in won_opp:
        amount_sum += Decimal(str(getattr(o, "amount", 0) or 0))
    activity_count = db.scalar(
        select(func.count(CrmOpportunityActivity.id)).join(
            CrmOpportunity, CrmOpportunity.id == CrmOpportunityActivity.opportunity_id
        ).where(
            CrmOpportunity.tenant_id == tenant_id,
            CrmOpportunity.customer_id == customer_id,
        )
    ) or 0

    return {
        "customer": customer,
        "contacts": contacts,
        "tags": tags,
        "opportunities": opportunities,
        "summary": {
            "opportunity_total": int(total_opp),
            "opportunity_won": int(len(won_opp)),
            "won_amount": float(amount_sum),
            "activity_total": int(activity_count),
        },
    }
