import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.crud.after_sale import create_after_sale, list_after_sales, list_shipments_by_order
from app.crud.customer import get_customer_by_user_id
from app.crud.customer_product import list_customer_product_ids
from app.crud.finance import get_statement_by_id, list_statements, update_statement_status
from app.crud.finance_ledger import create_ledger
from app.crud.kanban import build_order_progress_for_loaded_order, get_order_progress_summary
from app.models.finance import StatementItem
from app.models.product import Product
from app.models.sku import Sku
from app.crud.notification import create_notification, notify_users_with_permission
from app.crud.order import reject_order, submit_order_for_review
from app.models.order import Order, OrderItem
from app.schemas.order import CustomerPlaceOrderIn
from app.models.task import Task
from app.models.user import User
from app.models.work_order import WorkOrder
from app.services.display_label import product_display_name, sku_display_name
from app.services.sku_scope import apply_finished_product_sku_filter, is_material_product

router = APIRouter()

def _sku_public(s: Sku) -> dict:
    return {
        "id": s.id,
        "code": s.code,
        "name": s.name,
        "display_name": sku_display_name(s.name, s.code),
        "product_id": s.product_id,
        "color": s.color,
        "material": s.material,
        "spec": s.spec,
        "remark": s.remark,
        "created_at": s.created_at,
    }

def _product_public(p: Product) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "display_name": product_display_name(p.name, p.description, p.code, p.category),
        "category": p.category,
    }

@router.get("/catalog")
def catalog_api(
    product_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """客户浏览产品/型号（仅显示该客户已配置的可下单产品）"""
    _ensure_customer_user(user)
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案，请联系管理员在客户管理中绑定登录账号")

    allowed_ids = list_customer_product_ids(db, customer_id=customer.id)
    if not allowed_ids:
        return ok({
            "items": [],
            "products": [],
            "hint": "管理员尚未为您配置可下单产品，请联系工厂在「客户详情-可下单产品」中设置",
        })

    sku_stmt = select(Sku).where(Sku.is_active.is_(True),
        Sku.product_id.in_(allowed_ids))
    sku_stmt = apply_finished_product_sku_filter(sku_stmt)
    if product_id:
        if product_id not in allowed_ids:
            raise HTTPException(status_code=400, detail="该产品不在您的可下单范围内")
        sku_stmt = sku_stmt.where(Sku.product_id == product_id)
    if keyword:
        kw = f"%{keyword}%"
        from sqlalchemy import or_
        sku_stmt = sku_stmt.where(
            or_(Sku.code.like(kw), Sku.name.like(kw), Sku.color.like(kw), Sku.material.like(kw))
        )
    skus = db.scalars(sku_stmt.order_by(Sku.id.desc()).limit(100)).all()

    products_stmt = (
        select(Product)
        .where(Product.is_active.is_(True), Product.id.in_(allowed_ids))
        .order_by(Product.id)
    )
    products = [p for p in db.scalars(products_stmt).all() if not is_material_product(p)]

    return ok({
        "items": [_sku_public(s) for s in skus],
        "products": [_product_public(p) for p in products],
    })

def _ensure_customer_user(user: User) -> None:
    roles = {r.code for r in user.roles}
    if "customer" not in roles and not user.is_superuser:
        raise HTTPException(status_code=403, detail="仅客户账号可访问")

@router.post("/orders")
def place_order_api(
    payload: CustomerPlaceOrderIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    from app.crud.sku import get_sku_by_id

    _ensure_customer_user(user)
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案，请联系管理员在客户管理中绑定登录账号")
    allowed_ids = set(list_customer_product_ids(db, customer_id=customer.id))
    if not allowed_ids:
        raise HTTPException(status_code=400, detail="尚未配置可下单产品，请联系工厂管理员")
    if not payload.items:
        raise HTTPException(status_code=400, detail="请至少选择一行型号")

    from app.crud.order import get_order_by_code
    from app.services.code_generator import BizType, resolve_code

    code = resolve_code(
        db,
        biz_type=BizType.ORDER,
        code=None,
        exists=lambda c: get_order_by_code(db, c) is not None)
    status = "pending_confirm" if payload.submit else "draft"
    order = Order(
        customer_id=customer.id,
        code=code,
        status=status,
        remark=payload.remark,
        due_date=payload.due_date)
    lines = []
    for idx, row in enumerate(payload.items, start=1):
        sku = get_sku_by_id(db, sku_id=row.sku_id)
        if not sku or not sku.is_active:
            raise HTTPException(status_code=400, detail=f"型号#{row.sku_id}不可用")
        if sku.product_id not in allowed_ids:
            raise HTTPException(status_code=400, detail=f"型号 {sku.code} 不在您的可下单范围内")
        lines.append(
            OrderItem(
                line_no=idx,
                sku_id=row.sku_id,
                qty=row.qty,
                remark=row.remark)
        )
    order.items = lines
    db.add(order)
    db.flush()
    if status == "pending_confirm":
        notify_users_with_permission(
            db,
            permission_code="order.manage",
            title="新客户订单待审核",
            content=f"订单 {order.code} 待确认，请及时处理。",
            level="warning",
            biz_type="order",
            biz_id=order.id)
        try:
            from app.services.feishu.notify import emit_feishu_event

            emit_feishu_event(db, "order.customer_submitted",
                title="新客户订单待审核",
                content=f"订单 {order.code} 待确认，请及时处理。",
                level="warning",
                biz_type="order",
                biz_id=order.id)
        except Exception:
            pass
    db.commit()
    db.refresh(order)
    return ok({"id": order.id, "code": order.code, "status": order.status, "created_at": order.created_at})

@router.post("/orders/legacy")
def place_order_legacy_api(
    sku_id: int = Query(ge=1),
    qty: int = Query(ge=1),
    remark: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """兼容旧版单行 Query 下单"""
    payload = CustomerPlaceOrderIn(
        items=[{"sku_id": sku_id, "qty": qty, "remark": remark}],
        remark=remark,
        submit=True)
    return place_order_api(payload, db, user)

@router.post("/orders/{order_id}/submit")
def submit_order_api(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_customer_user(user)
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案")
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.customer_id == customer.id)
    )
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")
    try:
        submit_order_for_review(db, order)
        notify_users_with_permission(
            db,
            permission_code="order.manage",
            title="客户订单待审核",
            content=f"订单 {order.code} 已提交，请审核。",
            biz_type="order",
            biz_id=order.id)
        try:
            from app.services.feishu.notify import emit_feishu_event

            emit_feishu_event(db, "order.customer_submitted",
                title="客户订单待审核",
                content=f"订单 {order.code} 已提交，请审核。",
                level="warning",
                biz_type="order",
                biz_id=order.id)
        except Exception:
            pass
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok({"id": order.id, "status": order.status})

@router.get("/orders")
def my_orders_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        return ok({"items": []})
    stmt = select(Order).where(Order.customer_id == customer.id).order_by(Order.id.desc()).limit(50)
    orders = db.scalars(stmt).all()
    return ok({"items": [{"id": o.id, "code": o.code, "status": o.status, "due_date": str(o.due_date) if o.due_date else None,
            "remark": o.remark, "created_at": o.created_at} for o in orders]})

@router.get("/orders/{order_id}")
def my_order_detail_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案")
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == customer.id)
        .options(selectinload(Order.items).selectinload(OrderItem.sku))
    )
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")
    summary = get_order_progress_summary(db, order_id=order.id)
    return ok(
        {
            "id": order.id,
            "code": order.code,
            "status": order.status,
            "due_date": str(order.due_date) if order.due_date else None,
            "remark": order.remark,
            "total_qty": summary["total_qty"],
            "done_qty": summary["done_qty"],
            "progress": summary["progress"],
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": [
                {
                    "id": it.id,
                    "line_no": it.line_no,
                    "sku": _sku_public(it.sku) if it.sku else None,
                    "qty": int(it.qty),
                    "remark": it.remark,
                }
                for it in order.items
            ],
        }
    )

@router.get("/orders/{order_id}/progress")
def my_order_progress_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案")
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == customer.id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.sku),
            selectinload(Order.work_orders).selectinload(WorkOrder.sku),
            selectinload(Order.work_orders).selectinload(WorkOrder.tasks).selectinload(Task.process))
    )
    if not order:
        raise HTTPException(status_code=400, detail="订单不存在")
    data = build_order_progress_for_loaded_order(db, order)
    return ok(data)

@router.get("/statements")
def my_statements_api(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        return ok({"items": []})
    items = list_statements(
        db,
        customer_id=customer.id,
        status=status,
        offset=offset,
        limit=limit)
    return ok(
        {
            "items": [
                {
                    "id": x.id,
                    "code": x.code,
                    "period_start": str(x.period_start) if x.period_start else None,
                    "period_end": str(x.period_end) if x.period_end else None,
                    "total_amount": float(x.total_amount),
                    "status": x.status,
                    "remark": x.remark,
                    "created_at": x.created_at,
                    "updated_at": x.updated_at,
                }
                for x in items
            ]
        }
    )

@router.get("/statements/{statement_id}")
def my_statement_detail_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案")
    item = get_statement_by_id(db, statement_id=statement_id)
    if not item or item.customer_id != customer.id:
        raise HTTPException(status_code=400, detail="对账单不存在")
    return ok(
        {
            "id": item.id,
            "code": item.code,
            "period_start": str(item.period_start) if item.period_start else None,
            "period_end": str(item.period_end) if item.period_end else None,
            "total_amount": float(item.total_amount),
            "status": item.status,
            "remark": item.remark,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "items": [
                {
                    "order_id": si.order_id,
                    "order_code": si.order.code if si.order else None,
                    "amount": float(si.amount),
                }
                for si in item.items
            ],
        }
    )

@router.post("/statements/{statement_id}/ack")
def my_statement_ack_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案")
    item = get_statement_by_id(db, statement_id=statement_id)
    if not item or item.customer_id != customer.id:
        raise HTTPException(status_code=400, detail="对账单不存在")
    if item.status not in {"draft", "confirmed", "paid"}:
        raise HTTPException(status_code=400, detail="对账单状态不可确认")
    if item.status == "draft":
        update_statement_status(db, item, "confirmed")
        notify_users_with_permission(
            db,
            permission_code="finance.manage",
            title="客户已确认对账单",
            content=f"客户已确认对账单 {item.code}",
            level="info",
            biz_type="statement",
            biz_id=item.id,
            feishu_event="statement.customer_ack")
        if customer.owner_user_id:
            create_notification(
                db,
                user_id=customer.owner_user_id,
                title="客户已确认对账单",
                content=f"对账单 {item.code} 客户已确认",
                level="info",
                biz_type="statement",
                biz_id=item.id)
        db.commit()
        db.refresh(item)
    return ok({"id": item.id, "status": item.status, "updated_at": item.updated_at})

@router.post("/statements/{statement_id}/mark-paid")
def my_statement_mark_paid_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案")
    item = get_statement_by_id(db, statement_id=statement_id)
    if not item or item.customer_id != customer.id:
        raise HTTPException(status_code=400, detail="对账单不存在")
    if item.status == "paid":
        return ok({"id": item.id, "status": item.status, "updated_at": item.updated_at})
    if item.status != "confirmed":
        raise HTTPException(status_code=400, detail="对账单未确认")
    update_statement_status(db, item, "paid")
    create_ledger(
        db,
        direction="in",
        category="receipt",
        party_type="customer",
        party_id=customer.id,
        statement_type="statement",
        statement_id=item.id,
        amount=item.total_amount,
        biz_date=datetime.now().date(),
        remark=f"客户对账单{item.code}收款",
        created_by=user.id)
    db.commit()
    db.refresh(item)
    return ok({"id": item.id, "status": item.status, "updated_at": item.updated_at})

@router.get("/statements/{statement_id}/download")
def my_statement_download_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    customer = get_customer_by_user_id(db, user_id=user.id)
    if not customer:
        raise HTTPException(status_code=400, detail="无客户档案")
    item = get_statement_by_id(db, statement_id=statement_id)
    if not item or item.customer_id != customer.id:
        raise HTTPException(status_code=400, detail="对账单不存在")

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["statement_code", "period_start", "period_end", "status", "total_amount", "order_code", "amount"])
    for si in item.items:
        si: StatementItem
        w.writerow(
            [
                item.code,
                str(item.period_start) if item.period_start else "",
                str(item.period_end) if item.period_end else "",
                item.status,
                str(float(item.total_amount)),
                si.order.code if si.order else "",
                str(float(si.amount)),
            ]
        )
    content = "\ufeff" + buf.getvalue()
    filename = f"{item.code}.csv"
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

# ── 发货与售后 ──

def _ensure_customer(db: Session, user: User):
    cust = get_customer_by_user_id(db, user_id=user.id)
    if not cust:
        raise HTTPException(status_code=400, detail="无客户档案")
    return cust

@router.get("/orders/{order_id}/shipments")
def my_order_shipments_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_customer(db, user)
    items = list_shipments_by_order(db, order_id=order_id)
    return ok({
        "items": [
            {
                "id": s.id,
                "code": s.code,
                "logistics_company": s.logistics_company,
                "logistics_no": s.logistics_no,
                "status": s.status,
                "shipped_at": s.shipped_at,
                "remark": s.remark,
            }
            for s in items
        ]
    })

@router.get("/orders/{order_id}/after-sales")
def my_order_after_sales_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    _ensure_customer(db, user)
    items = list_after_sales(db, order_id=order_id)
    return ok({
        "items": [
            {
                "id": a.id,
                "code": a.code,
                "sale_type": a.sale_type,
                "reason": a.reason,
                "solution": a.solution,
                "status": a.status,
                "created_at": a.created_at,
            }
            for a in items
        ]
    })

@router.post("/orders/{order_id}/after-sales")
def create_my_after_sale_api(
    order_id: int,
    sale_type: str = Query(default="return"),
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    cust = _ensure_customer(db, user)
    from app.crud.order import get_order_by_id
    order = get_order_by_id(db, order_id=order_id)
    if not order or order.customer_id != cust.id:
        raise HTTPException(status_code=400, detail="订单不存在")
    if sale_type not in ("return", "exchange", "repair", "other"):
        raise HTTPException(status_code=400, detail="售后类型无效")
    a = create_after_sale(db, order_id=order_id, sale_type=sale_type, reason=reason, created_by=user.id)
    notify_users_with_permission(
        db,
        permission_code="customer.manage",
        title="客户提交售后申请",
        content=f"订单 {order.code} 售后申请 {a.code}：{reason or sale_type}",
        level="warning",
        biz_type="after_sale",
        biz_id=a.id,
        feishu_event="after_sale.created")
    if order.customer and getattr(order.customer, "owner_user_id", None):
        create_notification(
            db,
            user_id=order.customer.owner_user_id,
            title="客户提交售后申请",
            content=f"订单 {order.code} 售后 {a.code}",
            level="warning",
            biz_type="after_sale",
            biz_id=a.id)
    db.commit()
    db.refresh(a)
    return ok({
        "id": a.id,
        "code": a.code,
        "sale_type": a.sale_type,
        "status": a.status,
        "created_at": a.created_at,
    })
