from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_permissions, get_current_user, get_db, require_any_permissions
from app.core.response import ok
from app.crud.customer import create_customer, get_customer_by_code, get_customer_by_id, list_customers, update_customer
from app.crud.customer_product import list_customer_product_ids, list_customer_products_with_detail, set_customer_products
from app.crud.user import get_user_by_id
from app.models.user import User
from app.schemas.customer import CustomerCreateIn, CustomerProductsSetIn, CustomerUpdateIn
from app.services.code_generator import BizType, resolve_code
from app.services.customer_account import ensure_customer_login_user

router = APIRouter(dependencies=[Depends(require_any_permissions(["customer.manage"]))])


def _out(x, db: Session | None = None) -> dict:
    login_username = None
    owner_name = None
    if x.user_id and db is not None:
        u = get_user_by_id(db, user_id=x.user_id)
        if u:
            login_username = u.username
    if getattr(x, "owner_user_id", None) and db is not None:
        ou = get_user_by_id(db, user_id=x.owner_user_id)
        if ou:
            owner_name = ou.full_name or ou.username
    product_count = 0
    if db is not None:
        product_count = len(list_customer_product_ids(db, x.id))
    return {
        "id": x.id,
        "user_id": x.user_id,
        "owner_user_id": getattr(x, "owner_user_id", None),
        "owner_name": owner_name,
        "login_username": login_username,
        "product_count": product_count,
        "code": x.code,
        "name": x.name,
        "contact_name": x.contact_name,
        "contact_phone": x.contact_phone,
        "address": x.address,
        "remark": x.remark,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _need_customer(db: Session, customer_id: int):
    c = get_customer_by_id(db, customer_id=customer_id)
    if not c:
        raise HTTPException(status_code=400, detail="客户不存在")
    return c


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    owner_user_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    items = list_customers(
        db,
        keyword=keyword,
        owner_user_id=owner_user_id,
        offset=offset,
        limit=limit,
        include_inactive=include_inactive)
    return ok({"items": [_out(x, db) for x in items]})


@router.get("/{customer_id}")
def get_api(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    item = _need_customer(db, customer_id)
    return ok(_out(item, db))


@router.get("/{customer_id}/products")
def list_customer_products_api(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    c = _need_customer(db, customer_id)
    products = list_customer_products_with_detail(db, customer_id=c.id)
    return ok(
        {
            "product_ids": [p.id for p in products],
            "items": [{"id": p.id, "code": p.code, "name": p.name, "category": p.category} for p in products],
        }
    )


@router.put("/{customer_id}/products")
def set_customer_products_api(
    customer_id: int,
    payload: CustomerProductsSetIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    c = _need_customer(db, customer_id)
    ids = set_customer_products(db, customer_id=c.id, product_ids=payload.product_ids)
    db.commit()
    return ok({"customer_id": c.id, "product_ids": ids})


@router.post("")
def create_api(
    payload: CustomerCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    customer_code = resolve_code(
        db,
        biz_type=BizType.CUSTOMER,
        code=payload.code,
        exists=lambda c: get_customer_by_code(db, c) is not None,
        duplicate_msg="客户编码已存在")
    owner_user_id = payload.owner_user_id if payload.owner_user_id else user.id
    ou = get_user_by_id(db, user_id=owner_user_id)
    if not ou:
        raise HTTPException(status_code=400, detail="负责人不存在")
    item = create_customer(
        db,
        code=customer_code,
        name=payload.name,
        user_id=None,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        address=payload.address,
        remark=payload.remark,
        is_active=payload.is_active,
        owner_user_id=owner_user_id)
    ensure_customer_login_user(db, item,
        user_id=payload.user_id,
        login_username=payload.login_username,
        login_password=payload.login_password)
    db.commit()
    return ok(_out(item, db))


@router.put("/{customer_id}")
def update_api(
    customer_id: int,
    payload: CustomerUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    item = _need_customer(db, customer_id)
    if payload.code is not None and payload.code != item.code:
        exists = get_customer_by_code(db, code=payload.code)
        if exists:
            raise HTTPException(status_code=400, detail="客户编码已存在")
    update_customer(
        db,
        item=item,
        code=payload.code,
        name=payload.name,
        user_id=item.user_id,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        address=payload.address,
        remark=payload.remark,
        is_active=payload.is_active,
        owner_user_id=payload.owner_user_id)
    if payload.user_id is not None or payload.login_username or payload.login_password:
        ensure_customer_login_user(db, item,
            user_id=payload.user_id,
            login_username=payload.login_username,
            login_password=payload.login_password)
    db.commit()
    return ok(_out(item, db))
