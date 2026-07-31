from datetime import date, datetime
from decimal import Decimal
from html import escape
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.attachment import create_attachment
from app.crud.customer import get_customer_by_id, list_customers
from app.crud.notification import create_notification
from app.crud.order import (
    confirm_order,
    create_order,
    delete_order,
    get_order_by_code,
    get_order_by_id,
    get_order_item_lock_info,
    list_orders,
    order_has_active_production_plan,
    order_has_work_orders,
    order_is_production_locked,
    reject_order,
    update_order,
    update_order_items)
from app.crud.print_template import (
    get_print_template_by_code,
    get_print_template_by_id,
    html_to_pdf_bytes,
    render_print_template,
    wrap_pdf_html_with_page_number)
from app.crud.sku import get_sku_by_id, list_skus
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.services.display_label import order_sku_option_label
from app.schemas.order import OrderCreateIn, OrderUpdateIn
from app.services.code_generator import BizType, resolve_code
from app.storage import get_active_storage
from app.tasks._sync_excel import make_excel_response
from app.services.order_import import (
    OrderImportParams,
    build_import_template_bytes,
    import_single_order_from_excel)

router = APIRouter(dependencies=[Depends(require_permissions(["order.manage"]))])

def _sku_ref_out(sku) -> dict:
    product = sku.product if hasattr(sku, "product") and sku.product else None
    pn, sm, _ = order_sku_option_label(
        product_name=product.name if product else None,
        product_description=product.description if product else None,
        product_code=product.code if product else None,
        product_category=product.category if product else None,
        sku_name=sku.name,
        sku_code=sku.code,
        sku_color=sku.color,
        sku_material=sku.material,
        sku_spec=sku.spec)
    return {
        "id": sku.id,
        "code": sku.code,
        "name": sku.name,
        "product_id": sku.product_id,
        "product_name": pn,
        "sku_name": sm,
        "display_label": f"{pn} · {sm}" if pn else sm,
    }

def _item_out(x, order=None, db: Session | None = None) -> dict:
    sku = x.sku if hasattr(x, "sku") else None
    out = {
        "id": x.id,
        "order_id": x.order_id,
        "line_no": x.line_no,
        "sku_id": x.sku_id,
        "qty": x.qty,
        "remark": x.remark,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
        "sku": _sku_ref_out(sku) if sku else None,
        "locked": False,
        "lock_reason": None,
    }
    if order is not None and db is not None:
        lock = get_order_item_lock_info(db, order, x)
        out["locked"] = lock["locked"]
        out["lock_reason"] = lock["lock_reason"]
    return out

def _order_detail_out(db: Session, order) -> dict:
    data = _out(order)
    data["order_plan_locked"] = order_has_active_production_plan(db, order.id) if order.status != "draft" else False
    data["order_production_locked"] = order_is_production_locked(db, order.id) if order.status != "draft" else False
    data["has_work_orders"] = order_has_work_orders(db, order.id)
    data["items"] = [_item_out(x, order=order, db=db) for x in order.items]
    return data

def _out(x) -> dict:
    cust = x.customer if hasattr(x, "customer") else None
    return {
        "id": x.id,
        "customer_id": x.customer_id,
        "code": x.code,
        "status": x.status,
        "due_date": x.due_date,
        "remark": x.remark,
        "confirmed_at": x.confirmed_at,
        "confirmed_by": x.confirmed_by,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
        "customer": {"id": cust.id, "name": cust.name, "code": cust.code} if cust else None,
    }

def _list_out(order) -> dict:
    data = _out(order)
    items = list(getattr(order, "items", None) or [])
    total_qty = sum(int(getattr(it, "qty", 0) or 0) for it in items)
    labels: list[str] = []
    for it in items:
        sku = getattr(it, "sku", None)
        if not sku:
            continue
        product = getattr(sku, "product", None)
        pn, sm, label = order_sku_option_label(
            product_name=product.name if product else None,
            product_description=product.description if product else None,
            product_code=product.code if product else None,
            product_category=product.category if product else None,
            sku_name=sku.name,
            sku_code=sku.code,
            sku_color=sku.color,
            sku_material=sku.material,
            sku_spec=sku.spec)
        labels.append(f"{label} x{it.qty}")
    data["total_qty"] = total_qty
    data["sku_summary"] = "，".join(labels) if labels else None
    data["can_delete"] = order.status == "draft"
    return data

@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    customer_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    if customer_id is not None:
        c = get_customer_by_id(db, customer_id=customer_id)
        if not c:
            raise HTTPException(status_code=400, detail="客户不存在")
    items = list_orders(
        db,
        keyword=keyword,
        customer_id=customer_id,
        status=status,
        offset=offset,
        limit=limit)
    return ok({"items": [_list_out(x) for x in items]})

@router.get("/export")
def export_orders_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    items = list_orders(db, keyword=None, customer_id=None, status=None, offset=0, limit=999999)
    headers = ["订单号", "客户名称", "SKU编码", "SKU名称", "数量", "状态", "交期", "创建时间"]
    rows = []
    for o in items:
        cust_name = o.customer.name if o.customer else ""
        for it in (o.items or []):
            sku = getattr(it, "sku", None)
            rows.append([o.code, cust_name, sku.code if sku else "", sku.name if sku else "", str(it.qty), o.status, str(o.due_date or ""), str(o.created_at)])
    return make_excel_response(headers, rows, "orders.xlsx", "订单")

@router.get("/import-template")
def download_import_template_api():
    """下载订单导入 Excel 模板。"""
    data = build_import_template_bytes()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="order_import_template.xlsx"',
            "Content-Length": str(len(data)),
        })

def _form_bool(raw: str | None, default: bool = True) -> bool:
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")

def _form_optional_date(raw: str | None) -> date | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"交期格式无效：{s}，请使用 YYYY-MM-DD")

def _form_unit_price(raw: str | None) -> Decimal:
    s = (raw or "").strip() or "1"
    try:
        v = Decimal(s)
    except Exception:
        raise HTTPException(status_code=400, detail=f"默认工价格式无效：{s}")
    if v < 0:
        raise HTTPException(status_code=400, detail="默认工价不能为负数")
    return v

@router.post("/import-excel")
def import_orders_excel_api(
    file: UploadFile = File(...),
    customer_id: int = Form(..., ge=1),
    order_name: str = Form(..., min_length=1, max_length=200),
    due_date: str = Form(default=""),
    remark: str = Form(default=""),
    order_code: str = Form(default=""),
    auto_create_product: str = Form(default="true"),
    auto_create_sku: str = Form(default="true"),
    default_unit_price: str = Form(default="1"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """导入单张订单：页面填写订单头，Excel 仅含产品/型号/数量等明细。"""
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 或 .xls 格式的 Excel 文件")
    raw = file.file.read()
    params = OrderImportParams(
        customer_id=customer_id,
        order_name=order_name.strip(),
        due_date=_form_optional_date(due_date),
        remark=remark.strip() or None,
        order_code=order_code.strip() or None,
        auto_create_product=_form_bool(auto_create_product, True),
        auto_create_sku=_form_bool(auto_create_sku, True),
        default_unit_price=_form_unit_price(default_unit_price))
    try:
        result = import_single_order_from_excel(db, params=params, raw=raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok(result)

@router.get("/meta/form-options")
def create_form_options_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """新建订单下拉：仅需 order.manage。路径使用 /meta/ 前缀，避免与 /{order_id} 整数路径冲突。"""
    customers = list_customers(db, keyword=None, offset=0, limit=200, include_inactive=False)
    skus = list_skus(
        db,
        product_id=None,
        keyword=None,
        offset=0,
        limit=200,
        include_inactive=False,
        finished_products_only=True)
    product_ids = {s.product_id for s in skus}
    product_map: dict[int, Product] = {}
    if product_ids:
        products = db.scalars(
            select(Product).where(Product.id.in_(product_ids))
        ).all()
        product_map = {p.id: p for p in products}
    sku_options = []
    for s in skus:
        p = product_map.get(s.product_id)
        pn, sm, label = order_sku_option_label(
            product_name=p.name if p else None,
            product_description=p.description if p else None,
            product_code=p.code if p else None,
            product_category=p.category if p else None,
            sku_name=s.name,
            sku_code=s.code,
            sku_color=s.color,
            sku_material=s.material,
            sku_spec=s.spec)
        sku_options.append(
            {
                "id": s.id,
                "code": s.code,
                "product_id": s.product_id,
                "product_name": pn,
                "sku_name": sm,
                "display_label": label,
            }
        )
    return ok(
        {
            "customers": [{"id": c.id, "code": c.code, "name": c.name} for c in customers],
            "skus": sku_options,
        }
    )

@router.get("/{order_id}")
def get_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    item = get_order_by_id(db, order_id=order_id, with_items=True)
    if not item:
        raise HTTPException(status_code=400, detail="订单不存在")
    return ok(_order_detail_out(db, item))

@router.post("")
def create_api(
    payload: OrderCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    c = get_customer_by_id(db, customer_id=payload.customer_id)
    if not c:
        raise HTTPException(status_code=400, detail="客户不存在")
    order_code = resolve_code(
        db,
        biz_type=BizType.ORDER,
        code=payload.code,
        exists=lambda c: get_order_by_code(db, c) is not None,
        duplicate_msg="订单号已存在")

    seen_line_no: set[int] = set()
    items: list[tuple[int, int, int, str | None]] = []
    for it in payload.items:
        if it.line_no in seen_line_no:
            raise HTTPException(status_code=400, detail="订单明细行号重复")
        seen_line_no.add(it.line_no)
        sku = get_sku_by_id(db, sku_id=it.sku_id)
        if not sku:
            raise HTTPException(status_code=400, detail="产品型号不存在")
        if not sku.is_active:
            raise HTTPException(status_code=400, detail="产品型号已停用")
        items.append((it.line_no, it.sku_id, it.qty, it.remark))

    order = create_order(
        db,
        customer_id=payload.customer_id,
        code=order_code,
        due_date=payload.due_date,
        remark=payload.remark,
        items=items,
        opportunity_id=None)
    db.commit()
    item = get_order_by_id(db, order_id=order.id, with_items=True)
    if not item:
        raise HTTPException(status_code=500, detail="创建失败")
    return ok(_order_detail_out(db, item))

@router.delete("/{order_id}")
def delete_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    try:
        delete_order(db, order_id=order_id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok(None)

@router.put("/{order_id}")
def update_api(
    order_id: int,
    payload: OrderUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    order = get_order_by_id(db, order_id=order_id, with_items=True)
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")
    if order.status != "draft":
        if payload.customer_id is not None or payload.code is not None or payload.due_date is not None or payload.status is not None:
            raise HTTPException(status_code=400, detail="非草稿订单不允许修改关键信息")
    if payload.customer_id is not None:
        c = get_customer_by_id(db, customer_id=payload.customer_id)
        if not c:
            raise HTTPException(status_code=400, detail="客户不存在")
    if payload.code is not None and payload.code != order.code:
        exists = get_order_by_code(db, code=payload.code)
        if exists and exists.id != order.id:
            raise HTTPException(status_code=400, detail="订单号已存在")
    update_order(
        db,
        order=order,
        customer_id=payload.customer_id if order.status == "draft" else None,
        code=payload.code if order.status == "draft" else None,
        due_date=payload.due_date if order.status == "draft" else None,
        remark=payload.remark,
        status=payload.status if order.status == "draft" else None)
    if payload.items is not None:
        rows: list[tuple[int | None, int, int, int, str | None]] = []
        for it in payload.items:
            rows.append((it.id, it.line_no, it.sku_id, it.qty, it.remark))
        try:
            update_order_items(db, order, rows)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    item = get_order_by_id(db, order_id=order_id, with_items=True)
    if not item:
        raise HTTPException(status_code=500, detail="更新失败")
    return ok(_order_detail_out(db, item))

@router.post("/{order_id}/reject")
def reject_api(
    order_id: int,
    reason: str = Query(min_length=1, max_length=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.customer))
    )
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")
    try:
        reject_order(db, order, reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cust = order.customer
    if cust and cust.user_id:
        create_notification(
            db,
            user_id=cust.user_id,
            title="订单已驳回",
            content=f"订单 {order.code} 被驳回：{reason}",
            level="warning",
            biz_type="order",
            biz_id=order.id)
    db.commit()
    return ok({"id": order.id, "status": order.status})

@router.post("/{order_id}/confirm")
def confirm_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    order = get_order_by_id(db, order_id=order_id, with_items=False)
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")
    try:
        confirm_order(db, order=order, confirmer_user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    automation_plan_id = None
    automation_pipeline_ran = False
    automation_error = None
    from app.services.production_automation import auto_create_plan_for_order
    from app.services.production_automation_settings import get_automation_settings

    settings = get_automation_settings(db)
    if settings.get("enabled") and settings.get("on_order_confirm", {}).get("create_plan"):
        oc = settings.get("on_order_confirm") or {}
        run_pipeline = bool(oc.get("run_pipeline_after_create"))
        try:
            plan = auto_create_plan_for_order(db, order.id,
                user.id,
                start_offset_days=int(oc.get("start_offset_days") or 0),
                run_pipeline=run_pipeline)
            if plan:
                automation_plan_id = plan.id
                automation_pipeline_ran = run_pipeline
        except ValueError as e:
            automation_error = str(e)

    order_full = get_order_by_id(db, order_id=order.id, with_items=False)
    if order_full:
        cust = order_full.customer
        if cust and cust.user_id:
            create_notification(
                db,
                user_id=cust.user_id,
                title="订单已确认",
                content=f"您的订单 {order.code} 已确认，进入生产准备",
                level="info",
                biz_type="order",
                biz_id=order.id,
                feishu_event="order.confirmed")
        if cust and getattr(cust, "owner_user_id", None):
            create_notification(
                db,
                user_id=cust.owner_user_id,
                title="客户订单已确认",
                content=f"订单 {order.code} 已确认生产",
                level="info",
                biz_type="order",
                biz_id=order.id)

    db.commit()
    return ok({
        "order_id": order.id,
        "status": order.status,
        "work_order_count": 0,
        "automation_plan_id": automation_plan_id,
        "automation_pipeline_ran": automation_pipeline_ran,
        "automation_error": automation_error,
    })

def _order_items_html(items: list[dict]) -> str:
    rows = []
    for it in items:
        rows.append(
            "<tr>"
            f"<td style=\"padding:6px;border:1px solid #ddd;\">{escape(it.get('sku_code') or '')}</td>"
            f"<td style=\"padding:6px;border:1px solid #ddd;\">{escape(it.get('sku_name') or '')}</td>"
            f"<td style=\"padding:6px;border:1px solid #ddd;text-align:right;\">{it['qty']}</td>"
            f"<td style=\"padding:6px;border:1px solid #ddd;\">{escape(it.get('remark') or '')}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan=\"4\" style=\"padding:10px;border:1px solid #ddd;color:#999;text-align:center;\">无明细</td></tr>")
    return "".join(rows)

@router.get("/{order_id}/print")
def print_api(
    order_id: int,
    template_id: int | None = Query(default=None, ge=1),
    template_code: str = Query(default="order_detail", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    order = get_order_by_id(db, order_id=order_id, with_items=True)
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")

    tpl = None
    if template_id is not None:
        tpl = get_print_template_by_id(db, template_id=template_id)
    else:
        tpl = get_print_template_by_code(db, code=template_code)
    if not tpl or not tpl.is_active:
        example = (
            "<html><head><meta charset=\"utf-8\" />"
            "<style>@page{size:A4;margin:12mm}body{font-family:Arial,Helvetica,sans-serif;font-size:12px}"
            "h1{font-size:18px;margin:0 0 8px}table{width:100%;border-collapse:collapse}</style>"
            "</head><body>"
            "<h1>销售订单</h1>"
            "<div>订单号：{{ order.code }}</div>"
            "<div>客户：{{ customer.name }}</div>"
            "<div>状态：{{ order.status }}</div>"
            "<div>交期：{{ order.due_date }}</div>"
            "<div>备注：{{ order.remark }}</div>"
            "<div style=\"margin-top:10px\">明细：</div>"
            "<table><thead><tr>"
            "<th style=\"padding:6px;border:1px solid #ddd;text-align:left;\">型号编码</th>"
            "<th style=\"padding:6px;border:1px solid #ddd;text-align:left;\">型号名称</th>"
            "<th style=\"padding:6px;border:1px solid #ddd;text-align:right;\">数量</th>"
            "<th style=\"padding:6px;border:1px solid #ddd;text-align:left;\">备注</th>"
            "</tr></thead><tbody>{{ items_html }}</tbody></table>"
            "</body></html>"
        )
        raise HTTPException(
            status_code=400,
            detail=f"未找到可用打印模板（请在 系统管理-打印模板 创建 code={template_code} 的模板）。示例内容：{example}")

    cust = order.customer if hasattr(order, "customer") else None
    items = [
        {
            "sku_code": it.sku.code if it.sku else "",
            "sku_name": it.sku.name if it.sku else "",
            "qty": it.qty,
            "remark": it.remark or "",
        }
        for it in (order.items or [])
    ]
    html = render_print_template(
        tpl.content,
        {
            "order": {
                "id": order.id,
                "code": order.code,
                "status": order.status,
                "due_date": str(order.due_date) if order.due_date else "",
                "remark": order.remark or "",
                "confirmed_at": str(order.confirmed_at) if order.confirmed_at else "",
                "created_at": str(order.created_at),
            },
            "customer": {"id": cust.id, "code": cust.code, "name": cust.name} if cust else None,
            "items_html": _order_items_html(items),
            "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    return ok({"html": html, "order_id": order.id, "code": order.code, "template_id": tpl.id})

@router.get("/{order_id}/print-pdf")
def print_pdf_api(
    order_id: int,
    template_id: int | None = Query(default=None, ge=1),
    template_code: str = Query(default="order_detail", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    resp = print_api(order_id=order_id, template_id=template_id, template_code=template_code, db=db, user=user)
    html = (resp.get("data") or {}).get("html") if isinstance(resp, dict) else ""
    code = (resp.get("data") or {}).get("code") if isinstance(resp, dict) else ""
    if not html:
        raise HTTPException(status_code=500, detail="渲染失败")
    title = f"销售订单 {code or order_id}"
    wrapped = wrap_pdf_html_with_page_number(html, title=title, printed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    try:
        pdf_bytes = html_to_pdf_bytes(wrapped)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = f"order_{code or order_id}.pdf"
    storage = get_active_storage(db)
    bio = BytesIO(pdf_bytes)
    stored = storage.save(
        filename=filename,
        content_type="application/pdf",
        stream=bio,
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
