from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.crud.rbac import get_user_permission_codes
from app.models.crm import CrmOpportunity
from app.models.customer import Customer
from app.models.user import User

# 可能尚未定义的扩展模型：采用延迟导入以避免 ImportError
try:
    from app.models.crm import CrmContract, CrmLead, CrmQuotation
except ImportError:  # pragma: no cover
    CrmLead = None
    CrmQuotation = None
    CrmContract = None


def crm_has_full_access(user: User, permission_codes: list[str] | None = None) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    codes = permission_codes if permission_codes is not None else []
    return "customer.manage" in codes


def _user_permission_codes(db: Session, user: User) -> list[str]:
    return get_user_permission_codes(db, user.id)


def can_access_owned_item(user: User, owner_user_id: int | None, permission_codes: list[str]) -> bool:
    """通用：超级用户 / customer.manage => 可访问；普通销售需 owner_user_id 匹配。"""
    if getattr(user, "is_superuser", False):
        return True
    codes = permission_codes if permission_codes is not None else []
    if "customer.manage" in codes:
        return True
    if "crm.sales" not in codes:
        return False
    return owner_user_id is None or owner_user_id == getattr(user, "id", None)


def can_access_customer(db: Session, user: User, customer: Customer, permission_codes: list[str] | None = None) -> bool:
    codes = permission_codes if permission_codes is not None else _user_permission_codes(db, user)
    return can_access_owned_item(user, getattr(customer, "owner_user_id", None), codes)


def can_access_opportunity(db: Session, user: User, opp, permission_codes: list[str] | None = None) -> bool:
    codes = permission_codes if permission_codes is not None else _user_permission_codes(db, user)
    return can_access_owned_item(user, getattr(opp, "owner_user_id", None), codes)


def can_access_lead(db: Session, user: User, lead_or_id, permission_codes: list[str] | None = None) -> bool:
    codes = permission_codes if permission_codes is not None else _user_permission_codes(db, user)
    if crm_has_full_access(user, codes):
        return True
    if "crm.sales" not in codes:
        return False
    if isinstance(lead_or_id, int):
        if CrmLead is None:
            return False
        lead = db.scalar(select(CrmLead).where(CrmLead.id == int(lead_or_id)))
    else:
        lead = lead_or_id
    if lead is None:
        return False
    return getattr(lead, "owner_user_id", None) is None or getattr(lead, "owner_user_id", None) == user.id


def can_access_quotation(db: Session, user: User, quotation_or_id, permission_codes: list[str] | None = None) -> bool:
    codes = permission_codes if permission_codes is not None else _user_permission_codes(db, user)
    if crm_has_full_access(user, codes):
        return True
    if "crm.sales" not in codes:
        return False
    if isinstance(quotation_or_id, int):
        if CrmQuotation is None:
            return False
        quotation = db.scalar(select(CrmQuotation).where(CrmQuotation.id == int(quotation_or_id)))
    else:
        quotation = quotation_or_id
    if quotation is None:
        return False
    return getattr(quotation, "owner_user_id", None) is None or getattr(quotation, "owner_user_id", None) == user.id


def can_access_contract(db: Session, user: User, contract_or_id, permission_codes: list[str] | None = None) -> bool:
    codes = permission_codes if permission_codes is not None else _user_permission_codes(db, user)
    if crm_has_full_access(user, codes):
        return True
    if "crm.sales" not in codes:
        return False
    if isinstance(contract_or_id, int):
        if CrmContract is None:
            return False
        contract = db.scalar(select(CrmContract).where(CrmContract.id == int(contract_or_id)))
    else:
        contract = contract_or_id
    if contract is None:
        return False
    return getattr(contract, "owner_user_id", None) is None or getattr(contract, "owner_user_id", None) == user.id


def can_access_campaign(db: Session, user: User, campaign, permission_codes: list[str] | None = None) -> bool:
    return can_access_owned_item(user, getattr(campaign, "owner_user_id", None), permission_codes)


def can_access_sales_target(db: Session, user: User, target, permission_codes: list[str] | None = None) -> bool:
    return can_access_owned_item(user, getattr(target, "owner_user_id", None), permission_codes)


def apply_customer_scope(stmt: Select, user: User, permission_codes: list[str]) -> Select:
    if crm_has_full_access(user, permission_codes):
        return stmt
    if "crm.sales" not in permission_codes:
        return stmt.where(Customer.id == -1)
    return stmt.where(or_(Customer.owner_user_id.is_(None), Customer.owner_user_id == user.id))


def apply_opportunity_scope(stmt: Select, user: User, permission_codes: list[str]) -> Select:
    if crm_has_full_access(user, permission_codes):
        return stmt
    if "crm.sales" not in permission_codes:
        return stmt.where(CrmOpportunity.id == -1)
    return stmt.where(or_(CrmOpportunity.owner_user_id.is_(None), CrmOpportunity.owner_user_id == user.id))


def _apply_owned_scope(stmt: Select, model, user: User, permission_codes: list[str], owner_attr: str = "owner_user_id") -> Select:
    """通用：若 model 有 owner_user_id，则做数据域过滤。"""
    if crm_has_full_access(user, permission_codes):
        return stmt
    if "crm.sales" not in permission_codes:
        if model is not None:
            col = getattr(model, "id", None)
            if col is not None:
                return stmt.where(col == -1)
        return stmt.where(False)
    if model is not None:
        col = getattr(model, owner_attr, None)
        if col is not None:
            return stmt.where(or_(col.is_(None), col == user.id))
    return stmt


def apply_lead_scope(stmt: Select, user: User, permission_codes: list[str]) -> Select:
    return _apply_owned_scope(stmt, CrmLead, user, permission_codes)


def apply_quotation_scope(stmt: Select, user: User, permission_codes: list[str]) -> Select:
    return _apply_owned_scope(stmt, CrmQuotation, user, permission_codes)


def apply_contract_scope(stmt: Select, user: User, permission_codes: list[str]) -> Select:
    return _apply_owned_scope(stmt, CrmContract, user, permission_codes)


def apply_campaign_scope(stmt: Select, user: User, permission_codes: list[str]) -> Select:
    try:
        from app.models.crm import CrmCampaign  # type: ignore
    except Exception:
        CrmCampaign = None
    return _apply_owned_scope(stmt, CrmCampaign, user, permission_codes)


def apply_sales_target_scope(stmt: Select, user: User, permission_codes: list[str]) -> Select:
    try:
        from app.models.crm import CrmSalesTarget  # type: ignore
    except Exception:
        CrmSalesTarget = None
    return _apply_owned_scope(stmt, CrmSalesTarget, user, permission_codes)
