# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_permissions, get_current_user, get_db, require_any_permissions, require_permissions
from app.core.response import ok
from app.crud.attachment import create_attachment
from app.crud.customer import create_customer, get_customer_by_code, get_customer_by_id, list_customers, update_customer
from app.crud.customer_product import (
    get_customer_product_map,
    list_customer_product_ids,
    list_customer_products_with_detail,
    set_customer_product_pricing,
    set_customer_products,
)
from app.crud.customer_price_tier import (
    PRODUCT_WIDE_SKU_ID,
    get_price_tier_map,
    replace_price_tiers,
)
from app.crud.customer_sku_price import (
    get_customer_sku_price_map,
    list_customer_skus,
    set_customer_sku_prices,
)
from app.crud.print_template import (
    get_print_template_by_code,
    get_print_template_by_id,
    html_to_pdf_bytes,
    render_print_template,
    wrap_pdf_html_with_page_number)
from app.crud.user import get_user_by_id
from app.models.user import User
from app.schemas.customer import (
    CustomerCreateIn,
    CustomerPriceTiersSetIn,
    CustomerProductsPricingSetIn,
    CustomerProductsSetIn,
    CustomerSkuPricesSetIn,
    CustomerUpdateIn,
)
from app.services.code_generator import BizType, resolve_code
from app.services.customer_account import ensure_customer_login_user
from app.services.customer_pricing import resolve_price_rule, to_price_tiers
from app.storage import get_active_storage

router = APIRouter(
    dependencies=[Depends(require_any_permissions(["customer.manage", "customer.view"]))]
)


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
    price_map = get_customer_product_map(db, customer_id=c.id)

    def _row(p) -> dict:
        cfg = price_map.get(p.id)
        return {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "category": p.category,
            "price": str(cfg.price or 0) if cfg else "0",
            "min_qty": int(cfg.min_qty or 1) if cfg else 1,
            "currency": str(cfg.currency or "CNY") if cfg else "CNY",
        }

    return ok({
        "product_ids": [p.id for p in products],
        "items": [_row(p) for p in products],
    })


@router.put("/{customer_id}/products", dependencies=[Depends(require_permissions(["customer.manage"]))])
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


@router.put("/{customer_id}/products/pricing", dependencies=[Depends(require_permissions(["customer.manage"]))])
def set_customer_products_pricing_api(
    customer_id: int,
    payload: CustomerProductsPricingSetIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    """批量维护客户专属单价 / 起订量 / 币种（含显式 commit）。"""
    c = _need_customer(db, customer_id)
    try:
        rows = set_customer_product_pricing(
            db,
            customer_id=c.id,
            items=[item.model_dump() for item in payload.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 先在 commit 前把 ORM 属性取成纯值：expire_on_commit 之后再读会触发额外查询
    items = [
        {
            "product_id": r.product_id,
            "price": str(r.price or 0),
            "min_qty": int(r.min_qty or 1),
            "currency": str(r.currency or "CNY"),
        }
        for r in rows
    ]
    db.commit()
    return ok({"customer_id": c.id, "items": items})


@router.get("/{customer_id}/skus/pricing", dependencies=[Depends(require_permissions(["customer.view"]))])
def list_customer_skus_pricing_api(
    customer_id: int,
    product_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    """列出客户白名单产品下全部型号的生效价目。

    同时返回型号级原始配置与合并后的生效值，供管理端表格回显：
    型号级留空的字段在 `sku_*` 里是 null，在 `effective_*` 里是继承来的产品级值。
    """
    c = _need_customer(db, customer_id)
    product_map = get_customer_product_map(db, customer_id=c.id)
    sku_price_map = get_customer_sku_price_map(db, customer_id=c.id)
    tier_map = get_price_tier_map(db, customer_id=c.id)
    products = {p.id: p for p in list_customer_products_with_detail(db, customer_id=c.id)}

    items: list[dict] = []
    for sku in list_customer_skus(db, customer_id=c.id, product_id=product_id):
        product_cfg = product_map.get(sku.product_id)
        sku_cfg = sku_price_map.get(sku.id)
        sku_tiers = to_price_tiers(tier_map.get((sku.product_id, sku.id)))
        product_tiers = to_price_tiers(tier_map.get((sku.product_id, PRODUCT_WIDE_SKU_ID)))
        # 不传 qty：阶梯给起价，管理端表格用 effective_unit_price 展示「起」
        rule = resolve_price_rule(
            product_cfg,
            sku_cfg,
            sku_tiers=sku_tiers,
            product_tiers=product_tiers,
        )
        product = products.get(sku.product_id)
        items.append({
            "sku_id": sku.id,
            "sku_code": sku.code,
            "sku_name": sku.name,
            "product_id": sku.product_id,
            "product_name": product.name if product else "",
            "product_price": str(product_cfg.price or 0) if product_cfg else "0",
            "product_min_qty": int(product_cfg.min_qty or 1) if product_cfg else 1,
            "product_currency": str(product_cfg.currency or "CNY") if product_cfg else "CNY",
            "sku_price": str(sku_cfg.price) if sku_cfg is not None else None,
            "sku_min_qty": (
                int(sku_cfg.min_qty) if sku_cfg is not None and sku_cfg.min_qty is not None else None
            ),
            "sku_currency": sku_cfg.currency if sku_cfg is not None else None,
            "effective_unit_price": str(rule.unit_price) if rule else "0",
            "effective_min_qty": rule.min_qty if rule else 1,
            "effective_currency": rule.currency if rule else "CNY",
            "source": rule.source if rule else "none",
            "priced": rule is not None,
            "tier_count": len(rule.tiers) if rule else 0,
            "tiers": (
                [{"min_qty": t.min_qty, "price": str(t.price)} for t in rule.tiers]
                if rule
                else []
            ),
        })
    return ok({"customer_id": c.id, "items": items})


@router.put("/{customer_id}/skus/pricing", dependencies=[Depends(require_permissions(["customer.manage"]))])
def set_customer_skus_pricing_api(
    customer_id: int,
    payload: CustomerSkuPricesSetIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    """批量维护客户型号级价目（含显式 commit）。

    `price` 传 0 表示删除该型号覆盖、回落产品级；`min_qty` / `currency` 传 null 表示继承产品级。
    """
    c = _need_customer(db, customer_id)
    try:
        rows = set_customer_sku_prices(
            db,
            customer_id=c.id,
            items=[item.model_dump() for item in payload.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # commit 前先取纯值：expire_on_commit 之后再读 ORM 属性会触发额外查询
    items = [
        {
            "sku_id": r.sku_id,
            "price": str(r.price or 0),
            "min_qty": int(r.min_qty) if r.min_qty is not None else None,
            "currency": r.currency,
        }
        for r in rows
    ]
    db.commit()
    return ok({"customer_id": c.id, "items": items})


@router.get("/{customer_id}/price-tiers", dependencies=[Depends(require_permissions(["customer.view"]))])
def list_customer_price_tiers_api(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    """列出客户阶梯价配置（产品通用 + 型号专属两种 scope）。

    产品通用档对所有白名单产品都返回（未配置时 `tiers` 为空数组），
    型号专属档只返回已配过档位的型号，避免把上百个型号全拉给前端。
    """
    c = _need_customer(db, customer_id)
    product_map = get_customer_product_map(db, customer_id=c.id)
    tier_map = get_price_tier_map(db, customer_id=c.id)
    sku_price_map = get_customer_sku_price_map(db, customer_id=c.id)
    products = {p.id: p for p in list_customer_products_with_detail(db, customer_id=c.id)}
    skus = {s.id: s for s in list_customer_skus(db, customer_id=c.id)}

    def _tiers(product_id: int, sku_id: int) -> list[dict]:
        return [
            {"min_qty": int(r.min_qty), "price": str(r.price)}
            for r in tier_map.get((product_id, sku_id), [])
        ]

    product_items = []
    for product_id, cfg in sorted(product_map.items()):
        product = products.get(product_id)
        product_items.append({
            "product_id": product_id,
            "product_name": product.name if product else "",
            "price": str(cfg.price or 0),
            "min_qty": int(cfg.min_qty or 1),
            "currency": str(cfg.currency or "CNY"),
            "tiers": _tiers(product_id, PRODUCT_WIDE_SKU_ID),
        })

    sku_items = []
    for (product_id, sku_id), rows in sorted(tier_map.items()):
        if sku_id == PRODUCT_WIDE_SKU_ID or not rows:
            continue
        sku = skus.get(sku_id)
        product = products.get(product_id)
        sku_cfg = sku_price_map.get(sku_id)
        sku_items.append({
            "sku_id": sku_id,
            "sku_code": sku.code if sku else "",
            "sku_name": sku.name if sku else "",
            "product_id": product_id,
            "product_name": product.name if product else "",
            "sku_price": str(sku_cfg.price) if sku_cfg is not None else None,
            "product_price": str(product_map[product_id].price or 0),
            "currency": str(product_map[product_id].currency or "CNY"),
            "tiers": _tiers(product_id, sku_id),
        })

    return ok({
        "customer_id": c.id,
        "products": product_items,
        "skus": sku_items,
        "sku_options": [
            {
                "sku_id": s.id,
                "sku_code": s.code,
                "sku_name": s.name,
                "product_id": s.product_id,
                "product_name": products[s.product_id].name if s.product_id in products else "",
            }
            for s in skus.values()
        ],
    })


@router.put("/{customer_id}/price-tiers", dependencies=[Depends(require_permissions(["customer.manage"]))])
def set_customer_price_tiers_api(
    customer_id: int,
    payload: CustomerPriceTiersSetIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    permission_codes: list[str] = Depends(get_current_permissions)):
    """按 scope 整组替换阶梯价（含显式 commit）。

    每个 scope 提交的是**完整档位列表**，不在列表里的档位即被删除；
    `tiers` 传空数组表示清空该 scope 的阶梯、回落到单一单价。
    """
    c = _need_customer(db, customer_id)
    try:
        rows = replace_price_tiers(
            db,
            customer_id=c.id,
            items=[item.model_dump() for item in payload.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # commit 前先取纯值：expire_on_commit 之后再读 ORM 属性会触发额外查询
    items = [
        {
            "product_id": r.product_id,
            "sku_id": r.sku_id,
            "min_qty": int(r.min_qty),
            "price": str(r.price),
        }
        for r in rows
    ]
    db.commit()
    return ok({"customer_id": c.id, "items": items})


@router.post("", dependencies=[Depends(require_permissions(["customer.manage"]))])
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


@router.put("/{customer_id}", dependencies=[Depends(require_permissions(["customer.manage"]))])
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


_CUSTOMER_PRINT_EXAMPLE = (
    "<html><head><meta charset=\"utf-8\" />"
    "<style>@page{size:A5;margin:10mm}body{font-family:Arial,Helvetica,sans-serif;font-size:12px}"
    "h1{font-size:18px;margin:0 0 8px}</style></head><body>"
    "<h1>客户名片</h1>"
    "<div>编码：{{ customer.code }}</div>"
    "<div>名称：{{ customer.name }}</div>"
    "<div>联系人：{{ customer.contact_name }}</div>"
    "<div>电话：{{ customer.contact_phone }}</div>"
    "<div>地址：{{ customer.address }}</div>"
    "<div>等级：{{ customer.customer_level }}　行业：{{ customer.industry }}</div>"
    "<div>负责人：{{ customer.owner_name }}</div>"
    "<div>备注：{{ customer.remark }}</div>"
    "<div style=\"margin-top:8px;color:#888\">打印时间：{{ printed_at }}</div>"
    "</body></html>"
)


def _customer_print_payload(db: Session, customer_id: int, template_id: int | None, template_code: str):
    """打印与打印 PDF 共用：模板解析 + 变量渲染。"""
    cust = _need_customer(db, customer_id)
    owner = get_user_by_id(db, user_id=cust.owner_user_id) if cust.owner_user_id else None
    if template_id is not None:
        tpl = get_print_template_by_id(db, template_id=template_id)
    else:
        tpl = get_print_template_by_code(db, code=template_code)
    if not tpl or not tpl.is_active:
        raise HTTPException(
            status_code=400,
            detail=(
                f"未找到可用打印模板（请在 系统管理-打印模板 创建 code={template_code} 的模板）。"
                f"示例内容：{_CUSTOMER_PRINT_EXAMPLE}"))
    html = render_print_template(
        tpl.content,
        {
            "customer": {
                "id": cust.id,
                "code": cust.code,
                "name": cust.name,
                "contact_name": cust.contact_name or "",
                "contact_phone": cust.contact_phone or "",
                "address": cust.address or "",
                "industry": getattr(cust, "industry", None) or "",
                "customer_level": getattr(cust, "customer_level", None) or "",
                "remark": cust.remark or "",
                "owner_name": (owner.full_name or owner.username) if owner else "",
            },
            "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    return cust, tpl, html


@router.get("/{customer_id}/print")
def print_api(
    customer_id: int,
    template_id: int | None = Query(default=None, ge=1),
    template_code: str = Query(default="customer_card", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    cust, tpl, html = _customer_print_payload(db, customer_id, template_id, template_code)
    return ok({"html": html, "customer_id": cust.id, "code": cust.code, "template_id": tpl.id})


@router.get("/{customer_id}/print-pdf")
def print_pdf_api(
    customer_id: int,
    template_id: int | None = Query(default=None, ge=1),
    template_code: str = Query(default="customer_card", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    cust, _tpl, html = _customer_print_payload(db, customer_id, template_id, template_code)
    printed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wrapped = wrap_pdf_html_with_page_number(
        html, title=f"客户 {cust.code or cust.id}", printed_at=printed_at)
    try:
        pdf_bytes = html_to_pdf_bytes(wrapped)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    storage = get_active_storage(db)
    filename = f"customer_{cust.code or cust.id}.pdf"
    stored = storage.save(
        filename=filename,
        content_type="application/pdf",
        stream=BytesIO(pdf_bytes),
        max_size=settings.FILE_MAX_UPLOAD_SIZE)
    att = create_attachment(
        db,
        uploader_id=user.id,
        storage_driver=stored.driver,
        storage_key=stored.key,
        original_filename=filename,
        content_type="application/pdf",
        size=stored.size,
        sha256=stored.sha256)
    db.commit()
    db.refresh(att)
    return ok({"attachment_id": att.id, "filename": att.original_filename, "url": f"/api/files/{att.id}?download=true"})
