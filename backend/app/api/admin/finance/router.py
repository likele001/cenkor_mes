from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.customer import get_customer_by_id
from app.crud.finance import calc_order_statement_amount, create_statement, get_statement_by_id, list_statements, update_statement_status
from app.crud.finance_ledger import create_ledger, list_ledgers
from app.crud.notification import create_notification
from app.models.customer import Customer
from app.models.finance_ledger import FinanceLedger
from app.models.material import Supplier
from app.models.user import User
from app.schemas.finance_ledger import FinanceLedgerCreateIn
from app.services.code_generator import BizType, resolve_code
from app.models.finance import Statement


router = APIRouter(dependencies=[Depends(require_permissions(["finance.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "customer_id": x.customer_id,
        "code": x.code,
        "period_start": str(x.period_start) if x.period_start else None,
        "period_end": str(x.period_end) if x.period_end else None,
        "total_amount": float(x.total_amount),
        "status": x.status,
        "remark": x.remark,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _ledger_out(x: FinanceLedger) -> dict:
    return {
        "id": x.id,
        "direction": x.direction,
        "category": x.category,
        "party_type": x.party_type,
        "party_id": x.party_id,
        "statement_type": x.statement_type,
        "statement_id": x.statement_id,
        "amount": float(x.amount),
        "biz_date": str(x.biz_date),
        "remark": x.remark,
        "created_by": x.created_by,
        "created_at": x.created_at,
    }


@router.get("")
def list_api(
    customer_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_statements(db, customer_id=customer_id, status=status, offset=offset, limit=limit)
    return ok({"items": [_out(x) for x in items]})


@router.get("/ledgers")
def list_ledgers_api(
    direction: str | None = Query(default=None),
    category: str | None = Query(default=None),
    party_type: str | None = Query(default=None),
    party_id: int | None = Query(default=None, ge=1),
    biz_date_from: date | None = Query(default=None),
    biz_date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_ledgers(
        db,
        direction=direction,
        category=category,
        party_type=party_type,
        party_id=party_id,
        biz_date_from=biz_date_from,
        biz_date_to=biz_date_to,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_ledger_out(x) for x in items]})


@router.post("/ledgers")
def create_ledger_api(
    payload: FinanceLedgerCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.party_type in {"customer", "supplier"} and not payload.party_id:
        raise HTTPException(status_code=400, detail="往来单位ID不能为空")
    x = create_ledger(
        db,
        direction=payload.direction,
        category=payload.category,
        party_type=payload.party_type,
        party_id=payload.party_id,
        statement_type=payload.statement_type,
        statement_id=payload.statement_id,
        amount=payload.amount,
        biz_date=payload.biz_date,
        remark=payload.remark,
        created_by=user.id,
    )
    db.commit()
    return ok(_ledger_out(x))


@router.get("/profit")
def profit_api(
    month: str = Query(min_length=7, max_length=7, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    y, m = month.split("-")
    year = int(y)
    mon = int(m)
    if mon < 1 or mon > 12:
        raise HTTPException(status_code=400, detail="月份不合法")
    start = date(year, mon, 1)
    if mon == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, mon + 1, 1)

    revenue = db.scalar(
        select(func.coalesce(func.sum(FinanceLedger.amount), 0)).where(
            FinanceLedger.direction == "in",
            FinanceLedger.category == "receipt",
            FinanceLedger.biz_date >= start,
            FinanceLedger.biz_date < end,
        )
    )
    cost = db.scalar(
        select(func.coalesce(func.sum(FinanceLedger.amount), 0)).where(
            FinanceLedger.direction == "out",
            FinanceLedger.category == "payment",
            FinanceLedger.biz_date >= start,
            FinanceLedger.biz_date < end,
        )
    )
    revenue_d = Decimal(str(revenue or 0))
    cost_d = Decimal(str(cost or 0))
    gross_profit_d = revenue_d - cost_d
    gross_margin = float(gross_profit_d / revenue_d) if revenue_d > 0 else 0.0

    cust_rows = db.execute(
        select(Customer.id, Customer.name, func.sum(FinanceLedger.amount).label("amount"))
        .select_from(FinanceLedger)
        .join(Customer, Customer.id == FinanceLedger.party_id)
        .where(
            FinanceLedger.party_type == "customer",
            FinanceLedger.direction == "in",
            FinanceLedger.category == "receipt",
            FinanceLedger.biz_date >= start,
            FinanceLedger.biz_date < end,
        )
        .group_by(Customer.id, Customer.name)
        .order_by(func.sum(FinanceLedger.amount).desc())
    ).all()

    sup_rows = db.execute(
        select(Supplier.id, Supplier.name, func.sum(FinanceLedger.amount).label("amount"))
        .select_from(FinanceLedger)
        .join(Supplier, Supplier.id == FinanceLedger.party_id)
        .where(
            FinanceLedger.party_type == "supplier",
            FinanceLedger.direction == "out",
            FinanceLedger.category == "payment",
            FinanceLedger.biz_date >= start,
            FinanceLedger.biz_date < end,
        )
        .group_by(Supplier.id, Supplier.name)
        .order_by(func.sum(FinanceLedger.amount).desc())
    ).all()

    return ok(
        {
            "month": month,
            "revenue": float(revenue_d),
            "cost": float(cost_d),
            "gross_profit": float(gross_profit_d),
            "gross_margin": gross_margin,
            "breakdown": {
                "customers": [{"customer_id": int(r.id), "customer_name": r.name, "amount": float(r.amount)} for r in cust_rows],
                "suppliers": [{"supplier_id": int(r.id), "supplier_name": r.name, "amount": float(r.amount)} for r in sup_rows],
            },
        }
    )


@router.post("")
def create_api(
    customer_id: int = Query(ge=1),
    code: str | None = Query(default=None),
    period_start: str | None = Query(default=None),
    period_end: str | None = Query(default=None),
    remark: str | None = Query(default=None, max_length=500),
    order_ids: str = Query(min_length=1, description="逗号分隔的订单ID"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = get_customer_by_id(db, customer_id=customer_id)
    if not c:
        raise HTTPException(status_code=400, detail="客户不存在")

    from app.crud.order import get_order_by_id
    oid_list = [int(x.strip()) for x in order_ids.split(",") if x.strip()]
    amounts: list[tuple[int, Decimal]] = []
    for oid in oid_list:
        order = get_order_by_id(db, order_id=oid, with_items=True)
        if not order:
            raise HTTPException(status_code=400, detail=f"订单 {oid} 不存在")
        if order.customer_id != customer_id:
            raise HTTPException(status_code=400, detail=f"订单 {oid} 不属于该客户")
        try:
            amt = calc_order_statement_amount(db, order=order)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        amounts.append((oid, amt))

    import datetime as dt
    ps = dt.date.fromisoformat(period_start) if period_start else None
    pe = dt.date.fromisoformat(period_end) if period_end else None

    stmt_code = resolve_code(
        db,
        biz_type=BizType.CUSTOMER_STATEMENT,
        code=code,
        exists=lambda c: db.scalar(
            select(Statement.id).where(Statement.code == c)
        ) is not None,
        duplicate_msg="对账单号已存在",
    )
    stmt = create_statement(
        db,
        customer_id=customer_id,
        code=stmt_code,
        order_amounts=amounts,
        period_start=ps,
        period_end=pe,
        remark=remark,
    )
    cust = get_customer_by_id(db, customer_id=customer_id)
    if cust and cust.user_id:
        create_notification(
            db,
            user_id=cust.user_id,
            title="新对账单待确认",
            content=f"对账单 {stmt.code} 已发布，请登录确认",
            level="info",
            biz_type="statement",
            biz_id=stmt.id,
            feishu_event="statement.published",
        )
    db.commit()
    return ok(_out(stmt))


@router.post("/{statement_id}/confirm")
def confirm_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_statement_by_id(db, statement_id=statement_id)
    if not item:
        raise HTTPException(status_code=400, detail="对账单不存在")
    if item.status != "draft":
        raise HTTPException(status_code=400, detail="状态不允许确认")
    update_statement_status(db, item, "confirmed")
    today = datetime.now().date()
    create_ledger(
        db,
        direction="in",
        category="receipt",
        party_type="customer",
        party_id=item.customer_id,
        statement_type="statement",
        statement_id=item.id,
        amount=item.total_amount,
        biz_date=today,
        remark=f"客户对账单{item.code}确认应收",
        created_by=user.id,
    )
    db.commit()
    return ok({"id": item.id, "status": "confirmed"})


@router.post("/{statement_id}/mark-paid")
def mark_paid_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_statement_by_id(db, statement_id=statement_id)
    if not item:
        raise HTTPException(status_code=400, detail="对账单不存在")
    if item.status == "paid":
        return ok({"id": item.id, "status": item.status, "updated_at": item.updated_at})
    if item.status != "confirmed":
        raise HTTPException(status_code=400, detail="状态不允许标记已收款")
    update_statement_status(db, item, "paid")
    db.commit()
    db.refresh(item)
    return ok({"id": item.id, "status": item.status, "updated_at": item.updated_at})



from app.api.admin.finance.supplier_statements import router as supplier_statements_router
router.include_router(supplier_statements_router)

@router.get("/{statement_id}")
def get_api(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_statement_by_id(db, statement_id=statement_id)
    if not item:
        raise HTTPException(status_code=400, detail="对账单不存在")
    data = _out(item)
    data["customer"] = {"id": item.customer.id, "code": item.customer.code, "name": item.customer.name} if item.customer else None
    data["items"] = [
        {
            "order_id": si.order_id,
            "order_code": si.order.code if si.order else None,
            "amount": float(si.amount),
        }
        for si in item.items
    ]
    return ok(data)

