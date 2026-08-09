from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_permissions, get_current_user, get_db, require_any_permissions
from app.core.response import ok
from app.crud.crm import (
    create_customer_tag,
    get_customer_tag_by_id,
    get_customer_tag_by_name,
    list_all_opportunities,
    list_customer_tags,
    list_public_pool_opportunities,
    opportunity_stats,
    recycle_stale_opportunities,
    update_customer_tag,
)
from app.crud.crm import get_opportunity_by_id
from app.crud.notification import create_notification
from app.crud.tenant_setting import get_setting, upsert_setting
from app.models.user import User
from app.schemas.crm import CustomerTagCreateIn, CustomerTagUpdateIn
from app.services.crm_scope import (
    apply_opportunity_scope,
    can_access_lead,
    can_access_quotation,
    can_access_contract,
    can_access_campaign,
    can_access_sales_target,
    crm_has_full_access,
)


# --- 防御式辅助：若底层 crud/schemas 尚未实现，则统一返回 501 ---
def _crm_crud():
    """延迟获取 app.crud.crm 模块，用于 getattr 查找可能不存在的函数。"""
    import app.crud.crm as _crm
    return _crm


def _crm_schemas():
    import app.schemas.crm as _sch
    return _sch


def _item_to_dict(x) -> dict:
    """把 ORM 对象尽可能转 dict，字段缺失则置 None。"""
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    data: dict = {}
    columns = getattr(getattr(type(x), "__table__", None), "columns", None)
    if columns is not None:
        for col in columns:
            try:
                data[col.name] = getattr(x, col.name)
            except Exception:
                data[col.name] = None
    else:
        for attr in ("id", "code", "name", "title", "customer_id", "opportunity_id", "owner_user_id",
                     "status", "stage", "grade", "amount", "probability", "source",
                     "expected_close_date", "valid_until", "sign_date", "start_date", "end_date",
                     "renewal_notice_days", "is_active", "remark", "type", "color",
                     "target_amount", "actual_amount", "achievement_rate", "period_type",
                     "period_start", "period_end", "roi", "spent_amount", "leads_count",
                     "customers_count", "opportunities_count", "won_amount", "version",
                     "created_by", "created_at", "updated_at", "tenant_id"):
            try:
                if hasattr(x, attr):
                    data[attr] = getattr(x, attr)
            except Exception:
                data[attr] = None
    return data


def _not_implemented(msg: str = "该功能的底层实现尚未就绪"):
    raise HTTPException(status_code=501, detail=msg)


def _call(fn_name: str, default=None, **kwargs):
    mod = _crm_crud()
    fn = getattr(mod, fn_name, None)
    if not callable(fn):
        return default
    try:
        return fn(**kwargs)
    except TypeError:
        # 不兼容签名：返回 default，上层自行决定
        return default


def _payload_dict(payload) -> dict:
    if hasattr(payload, "model_dump"):
        try:
            return payload.model_dump(exclude_unset=True)
        except Exception:
            pass
    if hasattr(payload, "dict"):
        try:
            return payload.dict(exclude_unset=True)
        except Exception:
            pass
    return {k: v for k, v in vars(payload).items() if not k.startswith("_")}


def _require_customer_manage_safe(user: User | None, permission_codes: list[str]) -> None:
    """需 customer.manage 权限的检查。"""
    if user is not None and user.is_superuser:
        return
    if "customer.manage" not in permission_codes:
        raise HTTPException(status_code=403, detail="需要客户管理权限")


router = APIRouter(dependencies=[Depends(require_any_permissions(["customer.manage", "crm.sales"]))])

RECYCLE_DAYS_KEY = "crm.public_pool.recycle_days"
FOLLOWUP_REMIND_ENABLED_KEY = "crm.followup.remind_enabled"
FOLLOWUP_REMIND_DAYS_BEFORE_KEY = "crm.followup.remind_days_before"


def _recycle_days(db: Session, tenant_id: int) -> int:
    s = get_setting(db, tenant_id=tenant_id, key=RECYCLE_DAYS_KEY)
    if not s or not s.value:
        return 30
    try:
        return int(str(s.value).strip())
    except Exception:
        return 30


def _auto_recycle(db: Session, user: User) -> list[tuple[int, int | None]]:
    days = _recycle_days(db, user.tenant_id)
    return recycle_stale_opportunities(db, tenant_id=user.tenant_id, days=days)


def _notify_recycled(db: Session, tenant_id: int, recycled: list[tuple[int, int | None]]) -> None:
    for opp_id, prev_owner in recycled:
        if not prev_owner:
            continue
        create_notification(
            db,            user_id=prev_owner,
            title="销售机会已回收至公海",
            content=f"销售机会 #{opp_id} 因长期未跟进已回收至公海池",
            level="warning",
            biz_type="crm_opportunity",
            biz_id=opp_id,
            feishu_event="crm.opportunity.recycled",
        )


def _opp_list_out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "title": x.title,
        "stage": x.stage,
        "status": x.status,
        "amount": float(x.amount) if x.amount is not None else None,
        "probability": x.probability,
        "expected_close_date": str(x.expected_close_date) if x.expected_close_date else None,
        "customer_id": x.customer_id,
        "customer_name": x.customer.name if getattr(x, "customer", None) else None,
        "owner_user_id": x.owner_user_id,
        "owner_name": x.owner.full_name if getattr(x, "owner", None) else None,
        "converted_order_id": getattr(x, "converted_order_id", None),
        "converted_order_code": x.converted_order.code if getattr(x, "converted_order", None) else None,
        "created_at": x.created_at,
    }


def _tag_out(x) -> dict:
    return {
        "id": x.id,
        "tenant_id": x.tenant_id,
        "name": x.name,
        "color": x.color,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _require_customer_manage(permission_codes: list[str]) -> None:
    if "customer.manage" not in permission_codes:
        raise HTTPException(status_code=403, detail="需要客户管理权限")


@router.get("/opportunities")
def list_opportunities_api(
    keyword: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    status: str | None = Query(default=None),
    owner_user_id: int | None = Query(default=None, ge=1),
    customer_id: int | None = Query(default=None, ge=1),
    has_order: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    recycled = _auto_recycle(db, user)
    if recycled:
        _notify_recycled(db, user.tenant_id, recycled)
        db.commit()
    scope = lambda stmt: apply_opportunity_scope(stmt, user, permission_codes)
    if not crm_has_full_access(user, permission_codes) and owner_user_id is None:
        owner_user_id = user.id
    items = list_all_opportunities(
        db,
        tenant_id=user.tenant_id,
        keyword=keyword,
        stage=stage,
        status=status,
        owner_user_id=owner_user_id,
        customer_id=customer_id,
        has_order=has_order,
        offset=offset,
        limit=limit,
        scope_stmt=scope,
    )
    return ok({"items": [_opp_list_out(x) for x in items]})


@router.get("/tags")
def list_tags_api(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_customer_tags(db, tenant_id=user.tenant_id, include_inactive=include_inactive)
    return ok({"items": [_tag_out(x) for x in items]})


@router.post("/tags")
def create_tag_api(
    payload: CustomerTagCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage(permission_codes)
    exists = get_customer_tag_by_name(db, tenant_id=user.tenant_id, name=payload.name)
    if exists:
        raise HTTPException(status_code=400, detail="标签已存在")
    item = create_customer_tag(db, tenant_id=user.tenant_id, name=payload.name, color=payload.color, is_active=payload.is_active)
    db.commit()
    return ok(_tag_out(item))


@router.put("/tags/{tag_id}")
def update_tag_api(
    tag_id: int,
    payload: CustomerTagUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage(permission_codes)
    item = get_customer_tag_by_id(db, tenant_id=user.tenant_id, tag_id=tag_id)
    if not item:
        raise HTTPException(status_code=400, detail="标签不存在")
    if payload.name is not None and payload.name != item.name:
        exists = get_customer_tag_by_name(db, tenant_id=user.tenant_id, name=payload.name)
        if exists:
            raise HTTPException(status_code=400, detail="标签已存在")
    update_customer_tag(db, item, name=payload.name, color=payload.color, is_active=payload.is_active)
    db.commit()
    return ok(_tag_out(item))


@router.delete("/tags/{tag_id}")
def delete_tag_api(
    tag_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage(permission_codes)
    item = get_customer_tag_by_id(db, tenant_id=user.tenant_id, tag_id=tag_id)
    if not item:
        raise HTTPException(status_code=400, detail="标签不存在")
    update_customer_tag(db, item, is_active=False)
    db.commit()
    return ok({"id": item.id})


@router.get("/public-pool/opportunities")
def list_public_pool_api(
    keyword: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recycled = _auto_recycle(db, user)
    if recycled:
        _notify_recycled(db, user.tenant_id, recycled)
        db.commit()
    items = list_public_pool_opportunities(
        db,
        tenant_id=user.tenant_id,
        keyword=keyword,
        stage=stage,
        status=status,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_opp_list_out(x) for x in items]})


@router.post("/public-pool/opportunities/{opportunity_id}/claim")
def claim_opportunity_api(
    opportunity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    opp = get_opportunity_by_id(db, tenant_id=user.tenant_id, opportunity_id=opportunity_id, with_activities=False)
    if not opp:
        raise HTTPException(status_code=400, detail="销售机会不存在")
    if opp.owner_user_id is not None:
        raise HTTPException(status_code=400, detail="该机会已被领取")
    opp.owner_user_id = user.id
    create_notification(
        db,        user_id=user.id,
        title="已领取销售机会",
        content=f"您已领取销售机会 {opp.code}：{opp.title}",
        level="info",
        biz_type="crm_opportunity",
        biz_id=opp.id,
        feishu_event="crm.opportunity.assigned",
    )
    db.commit()
    return ok({"id": opp.id, "owner_user_id": opp.owner_user_id})


@router.post("/public-pool/opportunities/{opportunity_id}/release")
def release_opportunity_api(
    opportunity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    if not user.is_superuser and "customer.manage" not in permission_codes:
        raise HTTPException(status_code=403, detail="仅管理员可释放")
    opp = get_opportunity_by_id(db, tenant_id=user.tenant_id, opportunity_id=opportunity_id, with_activities=False)
    if not opp:
        raise HTTPException(status_code=400, detail="销售机会不存在")
    opp.owner_user_id = None
    db.commit()
    return ok({"id": opp.id, "owner_user_id": opp.owner_user_id})


@router.post("/public-pool/recycle")
def recycle_public_pool_api(
    days: int | None = Query(default=None, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    if not user.is_superuser and "customer.manage" not in permission_codes:
        raise HTTPException(status_code=403, detail="仅管理员可回收")
    recycled = recycle_stale_opportunities(db, tenant_id=user.tenant_id, days=days or _recycle_days(db, user.tenant_id))
    if recycled:
        _notify_recycled(db, user.tenant_id, recycled)
    db.commit()
    return ok({"recycled": len(recycled), "days": days or _recycle_days(db, user.tenant_id)})


@router.get("/opportunities/stats")
def opportunity_stats_api(
    month: str | None = Query(default=None, max_length=7),
    group_by: str = Query(default="stage", max_length=32),
    owner_user_id: int | None = Query(default=None, ge=1),
    customer_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    recycled = _auto_recycle(db, user)
    if recycled:
        _notify_recycled(db, user.tenant_id, recycled)
        db.commit()
    if not crm_has_full_access(user, permission_codes) and owner_user_id is None:
        owner_user_id = user.id
    df = date_from
    dt = date_to
    if month and not (df or dt):
        y, m = month.split("-")
        start = date(int(y), int(m), 1)
        if int(m) == 12:
            end = date(int(y) + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(int(y), int(m) + 1, 1) - timedelta(days=1)
        df = start
        dt = end
    df_dt = datetime(df.year, df.month, df.day) if df else None
    dt_dt = datetime(dt.year, dt.month, dt.day, 23, 59, 59) if dt else None
    try:
        items = opportunity_stats(
            db,
            tenant_id=user.tenant_id,
            group_by=group_by,
            date_from=df_dt,
            date_to=dt_dt,
            owner_user_id=owner_user_id,
            customer_id=customer_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="group_by 不支持")
    total_count = sum(int(x.get("count") or 0) for x in items)
    total_amount = sum(float(x.get("amount") or 0) for x in items)
    return ok({"items": items, "total_count": total_count, "total_amount": total_amount})


class CrmSettingsIn(BaseModel):
    recycle_days: int | None = Field(default=None, ge=1, le=365)
    followup_remind_enabled: bool | None = None
    followup_remind_days_before: int | None = Field(default=None, ge=0, le=30)


@router.get("/settings")
def get_crm_settings_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage(permission_codes)
    enabled = get_setting(db, tenant_id=user.tenant_id, key=FOLLOWUP_REMIND_ENABLED_KEY)
    days_before = get_setting(db, tenant_id=user.tenant_id, key=FOLLOWUP_REMIND_DAYS_BEFORE_KEY)
    return ok(
        {
            "recycle_days": _recycle_days(db, user.tenant_id),
            "followup_remind_enabled": str(enabled.value).lower() not in ("0", "false", "no") if enabled and enabled.value else True,
            "followup_remind_days_before": int(str(days_before.value).strip()) if days_before and days_before.value else 0,
        }
    )


@router.put("/settings")
def update_crm_settings_api(
    payload: CrmSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage(permission_codes)
    if payload.recycle_days is not None:
        upsert_setting(db, tenant_id=user.tenant_id, key=RECYCLE_DAYS_KEY, value=str(payload.recycle_days))
    if payload.followup_remind_enabled is not None:
        upsert_setting(db, tenant_id=user.tenant_id, key=FOLLOWUP_REMIND_ENABLED_KEY, value="1" if payload.followup_remind_enabled else "0")
    if payload.followup_remind_days_before is not None:
        upsert_setting(db, tenant_id=user.tenant_id, key=FOLLOWUP_REMIND_DAYS_BEFORE_KEY, value=str(payload.followup_remind_days_before))
    db.commit()
    return ok({"updated": True})


@router.get("/dashboard-summary")
def crm_dashboard_summary_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    from sqlalchemy import func, select

    from app.models.crm import CrmOpportunity, CrmOpportunityActivity

    scope = lambda stmt: apply_opportunity_scope(stmt, user, permission_codes)
    open_stmt = scope(
        select(func.count(CrmOpportunity.id)).where(
            CrmOpportunity.tenant_id == user.tenant_id,
            CrmOpportunity.is_active.is_(True),
            CrmOpportunity.status == "open",
        )
    )
    open_count = int(db.scalar(open_stmt) or 0)

    pool_stmt = select(func.count(CrmOpportunity.id)).where(
        CrmOpportunity.tenant_id == user.tenant_id,
        CrmOpportunity.owner_user_id.is_(None),
        CrmOpportunity.is_active.is_(True),
        CrmOpportunity.status == "open",
    )
    pool_count = int(db.scalar(pool_stmt) or 0)

    now = datetime.now(timezone.utc)
    due_stmt = (
        select(func.count(CrmOpportunityActivity.id))
        .join(CrmOpportunity, CrmOpportunity.id == CrmOpportunityActivity.opportunity_id)
        .where(
            CrmOpportunityActivity.tenant_id == user.tenant_id,
            CrmOpportunityActivity.next_follow_up_at.is_not(None),
            CrmOpportunityActivity.next_follow_up_at <= now,
            CrmOpportunity.is_active.is_(True),
            CrmOpportunity.status == "open",
        )
    )
    if not crm_has_full_access(user, permission_codes):
        due_stmt = due_stmt.where(CrmOpportunity.owner_user_id == user.id)
    due_count = int(db.scalar(due_stmt) or 0)

    return ok({"open_opportunities": open_count, "public_pool": pool_count, "due_followups": due_count})


class AfterSaleUpdateIn(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    solution: str | None = None


@router.get("/after-sales")
def list_after_sales_api(
    order_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    from app.crud.after_sale import list_after_sales

    items = list_after_sales(db, order_id=order_id, status=status, offset=offset, limit=limit)
    return ok(
        {
            "items": [
                {
                    "id": x.id,
                    "code": x.code,
                    "order_id": x.order_id,
                    "sale_type": x.sale_type,
                    "reason": x.reason,
                    "solution": x.solution,
                    "status": x.status,
                    "created_by": x.created_by,
                    "created_at": x.created_at,
                    "updated_at": x.updated_at,
                }
                for x in items
            ]
        }
    )


@router.put("/after-sales/{after_sale_id}")
def update_after_sale_api(
    after_sale_id: int,
    payload: AfterSaleUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    from app.crud.after_sale import get_after_sale_by_id, update_after_sale
    from app.crud.crm import create_opportunity_activity
    from app.crud.order import get_order_by_id

    item = get_after_sale_by_id(db, after_sale_id=after_sale_id)
    if not item:
        raise HTTPException(status_code=400, detail="售后单不存在")
    if payload.status and payload.status not in ("pending", "processing", "done", "rejected"):
        raise HTTPException(status_code=400, detail="状态无效")
    prev_status = item.status
    update_after_sale(db, item, status=payload.status, solution=payload.solution)
    if payload.status == "done" and prev_status != "done":
        order = get_order_by_id(db, order_id=item.order_id, with_items=False)
        if order:
            if getattr(order, "opportunity_id", None):
                note = f"售后单 {item.code} 已完结"
                if payload.solution:
                    note += f"：{payload.solution}"
                create_opportunity_activity(
                    db,
                    tenant_id=user.tenant_id,
                    opportunity_id=order.opportunity_id,
                    action_type="after_sale_visit",
                    content=note,
                    created_by=user.id,
                )
            if order.customer and order.customer.owner_user_id:
                create_notification(
                    db,                    user_id=order.customer.owner_user_id,
                    title="售后已完结",
                    content=f"售后单 {item.code} 已处理完成",
                    level="info",
                    biz_type="after_sale",
                    biz_id=item.id,
                )
    db.commit()
    return ok({"id": item.id, "status": item.status})


# ============================================================
# Leads 线索
# ============================================================

@router.get("/leads")
def list_leads_api(
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    owner_user_id: int | None = Query(default=None, ge=1),
    is_public_pool: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "list_leads", None)
    if not callable(fn):
        _not_implemented()
    if not crm_has_full_access(user, permission_codes) and owner_user_id is None:
        owner_user_id = user.id
    items = fn(
        db,
        tenant_id=user.tenant_id,
        keyword=keyword,
        status=status,
        source=source,
        grade=grade,
        owner_user_id=owner_user_id,
        is_public_pool=is_public_pool,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.post("/leads")
def create_lead_api(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "create_lead", None)
    if not callable(fn):
        _not_implemented()
    data = _payload_dict(payload)
    if data.get("owner_user_id") is None and not crm_has_full_access(user, permission_codes):
        data["owner_user_id"] = user.id
    lead = fn(db, tenant_id=user.tenant_id, **data)
    db.commit()
    return ok({"id": getattr(lead, "id", None), "code": getattr(lead, "code", None)})


@router.get("/leads/{lead_id}")
def get_lead_api(
    lead_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "get_lead_by_id", None)
    if not callable(fn):
        _not_implemented()
    lead = fn(db, tenant_id=user.tenant_id, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if getattr(lead, "is_active", True) is False:
        raise HTTPException(status_code=404, detail="线索不存在")
    if getattr(lead, "tenant_id", None) != user.tenant_id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="无权访问")
    if not can_access_lead(db, user, lead, permission_codes):
        raise HTTPException(status_code=403, detail="无权访问该线索")
    return ok(_item_to_dict(lead))


@router.put("/leads/{lead_id}")
def update_lead_api(
    lead_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_lead_by_id", None)
    upd_fn = getattr(_crm_crud(), "update_lead", None)
    if not callable(get_fn) or not callable(upd_fn):
        _not_implemented()
    lead = get_fn(db, tenant_id=user.tenant_id, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if getattr(lead, "is_active", True) is False:
        raise HTTPException(status_code=400, detail="该线索已停用")
    if getattr(lead, "tenant_id", None) != user.tenant_id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="无权访问")
    if not can_access_lead(db, user, lead, permission_codes):
        raise HTTPException(status_code=403, detail="无权修改该线索")
    data = _payload_dict(payload)
    lead = upd_fn(db, lead, **data)
    db.commit()
    return ok({"id": getattr(lead, "id", lead_id)})


@router.delete("/leads/{lead_id}")
def deactivate_lead_api(
    lead_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_lead_by_id", None)
    dea_fn = getattr(_crm_crud(), "deactivate_lead", None)
    if not callable(get_fn) or not callable(dea_fn):
        _not_implemented()
    lead = get_fn(db, tenant_id=user.tenant_id, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if getattr(lead, "tenant_id", None) != user.tenant_id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="无权访问")
    if not can_access_lead(db, user, lead, permission_codes):
        raise HTTPException(status_code=403, detail="无权修改该线索")
    dea_fn(db, lead)
    db.commit()
    return ok({"id": lead_id, "is_active": False})


@router.post("/leads/{lead_id}/convert")
def convert_lead_api(
    lead_id: int,
    payload: dict = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_lead_by_id", None)
    conv_fn = getattr(_crm_crud(), "convert_lead", None)
    if not callable(get_fn) or not callable(conv_fn):
        _not_implemented()
    lead = get_fn(db, tenant_id=user.tenant_id, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if getattr(lead, "is_active", True) is False:
        raise HTTPException(status_code=400, detail="该线索已停用")
    if not can_access_lead(db, user, lead, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该线索")
    data = _payload_dict(payload) if payload else {}
    result = conv_fn(db, user.tenant_id, lead.id, user.id, **data)
    db.commit()
    return ok(_item_to_dict(result) if result is not None else {"converted": True, "lead_id": lead_id})


@router.post("/leads/{lead_id}/claim")
def claim_lead_api(
    lead_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_lead_by_id", None)
    if not callable(get_fn):
        _not_implemented()
    lead = get_fn(db, tenant_id=user.tenant_id, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if getattr(lead, "owner_user_id", None) is not None:
        raise HTTPException(status_code=400, detail="该线索已被认领")
    lead.owner_user_id = user.id
    create_notification(
        db,        user_id=user.id,
        title="已认领线索",
        content=f"您已认领线索 {getattr(lead, 'code', lead_id)}",
        level="info",
        biz_type="crm_lead",
        biz_id=lead_id,
    )
    db.commit()
    return ok({"id": lead_id, "owner_user_id": user.id})


@router.post("/leads/{lead_id}/release")
def release_lead_api(
    lead_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_lead_by_id", None)
    if not callable(get_fn):
        _not_implemented()
    lead = get_fn(db, tenant_id=user.tenant_id, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if not can_access_lead(db, user, lead, permission_codes):
        raise HTTPException(status_code=403, detail="无权释放该线索")
    lead.owner_user_id = None
    db.commit()
    return ok({"id": lead_id, "owner_user_id": None})


@router.post("/leads/public-pool/recycle")
def recycle_leads_api(
    days: int = Query(default=30, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage_safe(user, permission_codes)
    recycle_fn = getattr(_crm_crud(), "recycle_stale_leads", None)
    if not callable(recycle_fn):
        _not_implemented("公海回收的 crud 函数未实现")
    recycled = recycle_fn(db, tenant_id=user.tenant_id, days=days)
    recycled_count = len(recycled) if isinstance(recycled, list) else int(recycled or 0)
    db.commit()
    return ok({"recycled": recycled_count, "days": days})


@router.get("/leads/{lead_id}/activities")
def list_lead_activities_api(
    lead_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_lead_by_id", None)
    list_fn = getattr(_crm_crud(), "list_lead_activities", None)
    if not callable(list_fn):
        # 兜底：用通用活动查询
        get_fn = get_fn  # noqa: F841
        _not_implemented("活动列表 crud 函数未实现")
    lead = get_fn(db, tenant_id=user.tenant_id, lead_id=lead_id) if callable(get_fn) else None
    if lead is not None:
        if not can_access_lead(db, user, lead, permission_codes):
            raise HTTPException(status_code=403, detail="无权访问")
    items = list_fn(db, tenant_id=user.tenant_id, lead_id=lead_id, offset=offset, limit=limit)
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.post("/leads/{lead_id}/activities")
def create_lead_activity_api(
    lead_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_lead_by_id", None)
    create_fn = getattr(_crm_crud(), "create_lead_activity", None)
    if not callable(create_fn):
        _not_implemented()
    lead = get_fn(db, tenant_id=user.tenant_id, lead_id=lead_id) if callable(get_fn) else None
    if lead is not None and not can_access_lead(db, user, lead, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该线索")
    data = _payload_dict(payload)
    item = create_fn(db, tenant_id=user.tenant_id, lead_id=lead_id, created_by=user.id, **data)
    db.commit()
    return ok({"id": getattr(item, "id", None)})


@router.get("/leads/stats/summary")
def lead_summary_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "lead_summary", None)
    if not callable(fn):
        _not_implemented()
    owner_user_id = user.id if not crm_has_full_access(user, permission_codes) else None
    result = fn(db, tenant_id=user.tenant_id)
    return ok(_item_to_dict(result) if result is not None else {})


# ============================================================
# Quotations 报价单
# ============================================================

@router.get("/quotations")
def list_quotations_api(
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: int | None = Query(default=None, ge=1),
    opportunity_id: int | None = Query(default=None, ge=1),
    owner_user_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "list_quotations", None)
    if not callable(fn):
        _not_implemented()
    if not crm_has_full_access(user, permission_codes) and owner_user_id is None:
        owner_user_id = user.id
    items = fn(
        db,
        tenant_id=user.tenant_id,
        keyword=keyword,
        status=status,
        customer_id=customer_id,
        opportunity_id=opportunity_id,
        owner_user_id=owner_user_id,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.post("/quotations")
def create_quotation_api(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "create_quotation", None)
    if not callable(fn):
        _not_implemented()
    data = _payload_dict(payload)
    if data.get("owner_user_id") is None and not crm_has_full_access(user, permission_codes):
        data["owner_user_id"] = user.id
    q = fn(db, tenant_id=user.tenant_id, **data)
    db.commit()
    return ok({"id": getattr(q, "id", None), "code": getattr(q, "code", None)})


@router.get("/quotations/{quotation_id}")
def get_quotation_api(
    quotation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_quotation_by_id", None)
    if not callable(get_fn):
        _not_implemented()
    q = get_fn(db, tenant_id=user.tenant_id, quotation_id=quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="报价单不存在")
    if getattr(q, "is_active", True) is False:
        raise HTTPException(status_code=400, detail="该报价单已停用")
    if not can_access_quotation(db, user, q, permission_codes):
        raise HTTPException(status_code=403, detail="无权访问该报价单")
    items = []
    items_fn = getattr(_crm_crud(), "list_quotation_items", None)
    if callable(items_fn):
        items = items_fn(db, tenant_id=user.tenant_id, quotation_id=quotation_id)
    out = _item_to_dict(q)
    out["items"] = [_item_to_dict(x) for x in items]
    return ok(out)


@router.put("/quotations/{quotation_id}")
def update_quotation_api(
    quotation_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_quotation_by_id", None)
    upd_fn = getattr(_crm_crud(), "update_quotation", None)
    if not callable(get_fn) or not callable(upd_fn):
        _not_implemented()
    q = get_fn(db, tenant_id=user.tenant_id, quotation_id=quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="报价单不存在")
    if getattr(q, "is_active", True) is False:
        raise HTTPException(status_code=400, detail="该报价单已停用")
    if not can_access_quotation(db, user, q, permission_codes):
        raise HTTPException(status_code=403, detail="无权修改该报价单")
    data = _payload_dict(payload)
    q = upd_fn(db, q, **data)
    db.commit()
    return ok({"id": getattr(q, "id", quotation_id)})


@router.post("/quotations/{quotation_id}/new-version")
def new_quotation_version_api(
    quotation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_quotation_by_id", None)
    ver_fn = getattr(_crm_crud(), "new_quotation_version", None)
    if not callable(get_fn) or not callable(ver_fn):
        _not_implemented()
    q = get_fn(db, tenant_id=user.tenant_id, quotation_id=quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="报价单不存在")
    if not can_access_quotation(db, user, q, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该报价单")
    new_q = ver_fn(db, q, tenant_id=user.tenant_id, user_id=user.id)
    db.commit()
    return ok({
        "id": getattr(new_q, "id", None),
        "code": getattr(new_q, "code", None),
        "version": getattr(new_q, "version", None),
    })


@router.post("/quotations/{quotation_id}/send")
def send_quotation_api(
    quotation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_quotation_by_id", None)
    send_fn = getattr(_crm_crud(), "send_quotation", None)
    if not callable(get_fn) or not callable(send_fn):
        _not_implemented()
    q = get_fn(db, tenant_id=user.tenant_id, quotation_id=quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="报价单不存在")
    if not can_access_quotation(db, user, q, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该报价单")
    send_fn(db, q, user_id=user.id)
    db.commit()
    return ok({"id": quotation_id, "status": "sent"})


@router.post("/quotations/{quotation_id}/reject")
def reject_quotation_api(
    quotation_id: int,
    payload: dict = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_quotation_by_id", None)
    rej_fn = getattr(_crm_crud(), "reject_quotation", None)
    if not callable(get_fn) or not callable(rej_fn):
        _not_implemented()
    q = get_fn(db, tenant_id=user.tenant_id, quotation_id=quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="报价单不存在")
    if not can_access_quotation(db, user, q, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该报价单")
    data = _payload_dict(payload) if payload else {}
    rej_fn(db, q, user_id=user.id, **data)
    db.commit()
    return ok({"id": quotation_id, "status": "rejected"})


@router.post("/quotations/{quotation_id}/convert-to-order")
def convert_quotation_to_order_api(
    quotation_id: int,
    payload: dict = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_quotation_by_id", None)
    conv_fn = getattr(_crm_crud(), "convert_quotation_to_order", None)
    if not callable(get_fn) or not callable(conv_fn):
        _not_implemented()
    q = get_fn(db, tenant_id=user.tenant_id, quotation_id=quotation_id)
    if not q:
        raise HTTPException(status_code=404, detail="报价单不存在")
    if not can_access_quotation(db, user, q, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该报价单")
    data = _payload_dict(payload) if payload else {}
    result = conv_fn(db, user.tenant_id, q.id, user.id, **data)
    db.commit()
    if isinstance(result, dict):
        return ok(result)
    return ok({
        "order_id": getattr(result, "id", None) if result is not None else None,
        "order_code": getattr(result, "code", None) if result is not None else None,
    })


# ============================================================
# Contracts 合同
# ============================================================

@router.get("/contracts")
def list_contracts_api(
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: int | None = Query(default=None, ge=1),
    owner_user_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "list_contracts", None)
    if not callable(fn):
        _not_implemented()
    if not crm_has_full_access(user, permission_codes) and owner_user_id is None:
        owner_user_id = user.id
    items = fn(
        db,
        tenant_id=user.tenant_id,
        keyword=keyword,
        status=status,
        customer_id=customer_id,
        owner_user_id=owner_user_id,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.post("/contracts")
def create_contract_api(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "create_contract", None)
    if not callable(fn):
        _not_implemented()
    data = _payload_dict(payload)
    if data.get("owner_user_id") is None and not crm_has_full_access(user, permission_codes):
        data["owner_user_id"] = user.id
    c = fn(db, tenant_id=user.tenant_id, **data)
    db.commit()
    return ok({"id": getattr(c, "id", None), "code": getattr(c, "code", None)})


@router.get("/contracts/{contract_id}")
def get_contract_api(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_contract_by_id", None)
    if not callable(get_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, contract_id=contract_id)
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")
    if not can_access_contract(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权访问该合同")
    items = []
    plans_fn = getattr(_crm_crud(), "list_contract_payment_plans", None)
    if callable(plans_fn):
        items = plans_fn(db, tenant_id=user.tenant_id, contract_id=contract_id)
    out = _item_to_dict(c)
    out["payment_plans"] = [_item_to_dict(x) for x in items]
    return ok(out)


@router.put("/contracts/{contract_id}")
def update_contract_api(
    contract_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_contract_by_id", None)
    upd_fn = getattr(_crm_crud(), "update_contract", None)
    if not callable(get_fn) or not callable(upd_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, contract_id=contract_id)
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")
    if not can_access_contract(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权修改该合同")
    data = _payload_dict(payload)
    c = upd_fn(db, c, **data)
    db.commit()
    return ok({"id": getattr(c, "id", contract_id)})


@router.post("/contracts/{contract_id}/renew")
def renew_contract_api(
    contract_id: int,
    payload: dict = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_contract_by_id", None)
    renew_fn = getattr(_crm_crud(), "renew_contract", None)
    if not callable(get_fn) or not callable(renew_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, contract_id=contract_id)
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")
    if not can_access_contract(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该合同")
    data = _payload_dict(payload) if payload else {}
    new_c = renew_fn(db, user.tenant_id, c.id, user.id, **data)
    db.commit()
    return ok({"id": getattr(new_c, "id", None), "code": getattr(new_c, "code", None)})


@router.post("/contracts/{contract_id}/terminate")
def terminate_contract_api(
    contract_id: int,
    payload: dict = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_contract_by_id", None)
    term_fn = getattr(_crm_crud(), "terminate_contract", None)
    if not callable(get_fn) or not callable(term_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, contract_id=contract_id)
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")
    if not can_access_contract(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该合同")
    data = _payload_dict(payload) if payload else {}
    term_fn(db, c, user_id=user.id, **data)
    c.status = "terminated"
    db.commit()
    return ok({"id": contract_id, "status": "terminated"})


@router.post("/contracts/{contract_id}/payment-plans/{plan_id}/record")
def record_contract_payment_api(
    contract_id: int,
    plan_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_contract_by_id", None)
    rec_fn = getattr(_crm_crud(), "record_contract_payment", None)
    if not callable(get_fn) or not callable(rec_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, contract_id=contract_id)
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")
    if not can_access_contract(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该合同")
    data = _payload_dict(payload)
    rec_fn(db, contract_id=contract_id, plan_id=plan_id, user_id=user.id, **data)
    db.commit()
    return ok({"contract_id": contract_id, "plan_id": plan_id, "recorded": True})


# ============================================================
# Win-Loss Reasons 胜负原因字典
# ============================================================

@router.get("/win-loss-reasons")
def list_win_loss_reasons_api(
    type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fn = getattr(_crm_crud(), "list_win_loss_reasons", None)
    if not callable(fn):
        _not_implemented()
    items = fn(db, tenant_id=user.tenant_id, type=type)
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.post("/win-loss-reasons")
def create_win_loss_reason_api(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage_safe(user, permission_codes)
    fn = getattr(_crm_crud(), "create_win_loss_reason", None)
    if not callable(fn):
        _not_implemented()
    data = _payload_dict(payload)
    item = fn(db, tenant_id=user.tenant_id, **data)
    db.commit()
    return ok({"id": getattr(item, "id", None)})


@router.put("/win-loss-reasons/{reason_id}")
def update_win_loss_reason_api(
    reason_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage_safe(user, permission_codes)
    get_fn = getattr(_crm_crud(), "get_win_loss_reason_by_id", None)
    upd_fn = getattr(_crm_crud(), "update_win_loss_reason", None)
    if not callable(get_fn) or not callable(upd_fn):
        _not_implemented()
    item = get_fn(db, tenant_id=user.tenant_id, reason_id=reason_id)
    if not item:
        raise HTTPException(status_code=404, detail="原因不存在")
    data = _payload_dict(payload)
    upd_fn(db, item, **data)
    db.commit()
    return ok({"id": reason_id})


@router.delete("/win-loss-reasons/{reason_id}")
def deactivate_win_loss_reason_api(
    reason_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage_safe(user, permission_codes)
    get_fn = getattr(_crm_crud(), "get_win_loss_reason_by_id", None)
    dea_fn = getattr(_crm_crud(), "deactivate_win_loss_reason", None)
    if not callable(get_fn) or not callable(dea_fn):
        _not_implemented()
    item = get_fn(db, tenant_id=user.tenant_id, reason_id=reason_id)
    if not item:
        raise HTTPException(status_code=404, detail="原因不存在")
    dea_fn(db, item)
    db.commit()
    return ok({"id": reason_id, "is_active": False})


# ============================================================
# Campaigns 市场活动
# ============================================================

@router.get("/campaigns")
def list_campaigns_api(
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    owner_user_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "list_campaigns", None)
    if not callable(fn):
        _not_implemented()
    if not crm_has_full_access(user, permission_codes) and owner_user_id is None:
        owner_user_id = user.id
    items = fn(
        db,
        tenant_id=user.tenant_id,
        keyword=keyword,
        status=status,
        owner_user_id=owner_user_id,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.post("/campaigns")
def create_campaign_api(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "create_campaign", None)
    if not callable(fn):
        _not_implemented()
    data = _payload_dict(payload)
    if data.get("owner_user_id") is None and not crm_has_full_access(user, permission_codes):
        data["owner_user_id"] = user.id
    item = fn(db, tenant_id=user.tenant_id, **data)
    db.commit()
    return ok({"id": getattr(item, "id", None), "code": getattr(item, "code", None)})


@router.get("/campaigns/{campaign_id}")
def get_campaign_api(
    campaign_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_campaign_by_id", None)
    if not callable(get_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="活动不存在")
    if not can_access_campaign(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权访问该活动")
    return ok(_item_to_dict(c))


@router.put("/campaigns/{campaign_id}")
def update_campaign_api(
    campaign_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_campaign_by_id", None)
    upd_fn = getattr(_crm_crud(), "update_campaign", None)
    if not callable(get_fn) or not callable(upd_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="活动不存在")
    if not can_access_campaign(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权修改该活动")
    data = _payload_dict(payload)
    upd_fn(db, c, **data)
    db.commit()
    return ok({"id": campaign_id})


@router.post("/campaigns/{campaign_id}/members")
def add_campaign_members_api(
    campaign_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_campaign_by_id", None)
    add_fn = getattr(_crm_crud(), "add_campaign_members", None)
    if not callable(get_fn) or not callable(add_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="活动不存在")
    if not can_access_campaign(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该活动")
    data = _payload_dict(payload)
    add_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id, **data)
    db.commit()
    return ok({"campaign_id": campaign_id, "added": True})


@router.get("/campaigns/{campaign_id}/members")
def list_campaign_members_api(
    campaign_id: int,
    member_type: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_campaign_by_id", None)
    list_fn = getattr(_crm_crud(), "list_campaign_members", None)
    if not callable(list_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id) if callable(get_fn) else None
    if c is not None and not can_access_campaign(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权访问该活动")
    items = list_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id, member_type=member_type, offset=offset, limit=limit)
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.delete("/campaigns/{campaign_id}/members/{member_type}/{member_id}")
def remove_campaign_member_api(
    campaign_id: int,
    member_type: str,
    member_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_campaign_by_id", None)
    rem_fn = getattr(_crm_crud(), "remove_campaign_member", None)
    if not callable(get_fn) or not callable(rem_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="活动不存在")
    if not can_access_campaign(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该活动")
    rem_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id, member_type=member_type, member_id=member_id)
    db.commit()
    return ok({"campaign_id": campaign_id, "member_type": member_type, "member_id": member_id, "removed": True})


@router.post("/campaigns/{campaign_id}/recalculate-roi")
def recalculate_campaign_roi_api(
    campaign_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_campaign_by_id", None)
    roi_fn = getattr(_crm_crud(), "recalculate_campaign_roi", None)
    if not callable(get_fn) or not callable(roi_fn):
        _not_implemented()
    c = get_fn(db, tenant_id=user.tenant_id, campaign_id=campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="活动不存在")
    if not can_access_campaign(db, user, c, permission_codes):
        raise HTTPException(status_code=403, detail="无权操作该活动")
    roi = roi_fn(db, c)
    db.commit()
    return ok({"campaign_id": campaign_id, "roi": roi})


# ============================================================
# Sales Targets 销售目标
# ============================================================

@router.get("/sales-targets")
def list_sales_targets_api(
    period_type: str | None = Query(default=None),
    owner_user_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "list_sales_targets", None)
    if not callable(fn):
        _not_implemented()
    if not crm_has_full_access(user, permission_codes) and owner_user_id is None:
        owner_user_id = user.id
    items = fn(
        db,
        tenant_id=user.tenant_id,
        period_type=period_type,
        owner_user_id=owner_user_id,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.post("/sales-targets")
def create_sales_target_api(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage_safe(user, permission_codes)
    fn = getattr(_crm_crud(), "create_sales_target", None)
    if not callable(fn):
        _not_implemented()
    data = _payload_dict(payload)
    item = fn(db, tenant_id=user.tenant_id, **data)
    db.commit()
    return ok({"id": getattr(item, "id", None)})


@router.get("/sales-targets/{target_id}")
def get_sales_target_api(
    target_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    get_fn = getattr(_crm_crud(), "get_sales_target_by_id", None)
    if not callable(get_fn):
        _not_implemented()
    t = get_fn(db, tenant_id=user.tenant_id, target_id=target_id)
    if not t:
        raise HTTPException(status_code=404, detail="目标不存在")
    if not can_access_sales_target(db, user, t, permission_codes):
        raise HTTPException(status_code=403, detail="无权访问该目标")
    return ok(_item_to_dict(t))


@router.put("/sales-targets/{target_id}")
def update_sales_target_api(
    target_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage_safe(user, permission_codes)
    get_fn = getattr(_crm_crud(), "get_sales_target_by_id", None)
    upd_fn = getattr(_crm_crud(), "update_sales_target", None)
    if not callable(get_fn) or not callable(upd_fn):
        _not_implemented()
    t = get_fn(db, tenant_id=user.tenant_id, target_id=target_id)
    if not t:
        raise HTTPException(status_code=404, detail="目标不存在")
    data = _payload_dict(payload)
    upd_fn(db, t, **data)
    db.commit()
    return ok({"id": target_id})


@router.delete("/sales-targets/{target_id}")
def deactivate_sales_target_api(
    target_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    _require_customer_manage_safe(user, permission_codes)
    get_fn = getattr(_crm_crud(), "get_sales_target_by_id", None)
    dea_fn = getattr(_crm_crud(), "deactivate_sales_target", None)
    if not callable(get_fn) or not callable(dea_fn):
        _not_implemented()
    t = get_fn(db, tenant_id=user.tenant_id, target_id=target_id)
    if not t:
        raise HTTPException(status_code=404, detail="目标不存在")
    dea_fn(db, t)
    db.commit()
    return ok({"id": target_id, "is_active": False})


# ============================================================
# Dashboard 看板聚合
# ============================================================

@router.get("/dashboard/sales-targets")
def crm_dashboard_sales_targets_api(
    period_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    fn = getattr(_crm_crud(), "dashboard_sales_targets", None)
    if not callable(fn):
        _not_implemented()
    owner_user_id = user.id if not crm_has_full_access(user, permission_codes) else None
    result = fn(db, tenant_id=user.tenant_id, period_type=period_type, owner_user_id=owner_user_id)
    if isinstance(result, dict):
        return ok(result)
    return ok(_item_to_dict(result) if result is not None else {})


# ============================================================
# 客户相关（报价 / 合同）
# ============================================================

@router.get("/customers/{customer_id}/contracts")
def list_customer_contracts_api(
    customer_id: int,
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    cust_fn = getattr(_crm_crud(), "get_customer_by_id", None)
    list_fn = getattr(_crm_crud(), "list_contracts", None)
    if not callable(list_fn):
        _not_implemented()
    if callable(cust_fn):
        cust = cust_fn(db, tenant_id=user.tenant_id, customer_id=customer_id)
        if cust is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        if not can_access_customer(db, user, cust, permission_codes):
            raise HTTPException(status_code=403, detail="无权访问该客户")
    items = list_fn(db, tenant_id=user.tenant_id, customer_id=customer_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_item_to_dict(x) for x in items]})


@router.get("/customers/{customer_id}/quotations")
def list_customer_quotations_api(
    customer_id: int,
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions),
):
    cust_fn = getattr(_crm_crud(), "get_customer_by_id", None)
    list_fn = getattr(_crm_crud(), "list_quotations", None)
    if not callable(list_fn):
        _not_implemented()
    if callable(cust_fn):
        cust = cust_fn(db, tenant_id=user.tenant_id, customer_id=customer_id)
        if cust is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        if not can_access_customer(db, user, cust, permission_codes):
            raise HTTPException(status_code=403, detail="无权访问该客户")
    items = list_fn(db, tenant_id=user.tenant_id, customer_id=customer_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_item_to_dict(x) for x in items]})
