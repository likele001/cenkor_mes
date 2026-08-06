"""工厂助手扩展上下文：CRM、采购、设备、成本毛利。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.models.crm import CrmOpportunity, CrmOpportunityActivity
from app.models.customer import Customer
from app.models.equipment import Equipment
from app.models.finance_ledger import FinanceLedger
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.services.ai.equipment_health import equipment_health_scores


def _ledger_profit(db: Session, start: date, end: date) -> dict:
    """流水账口径：收入(receipt) - 支出(payment)。"""
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
    gross_margin = float(gross_profit_d / revenue_d) if revenue_d > 0 else None
    return {
        "revenue": float(revenue_d),
        "cost": float(cost_d),
        "gross_profit": float(gross_profit_d),
        "gross_margin": gross_margin,
        "gross_margin_pct": round(gross_margin * 100, 2) if gross_margin is not None else None,
    }


def build_cost_context(db: Session, *, dashboard: dict) -> dict:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    month_start = today.replace(day=1)
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)

    today_ledger = _ledger_profit(db, today, tomorrow)
    month_ledger = _ledger_profit(db, month_start, next_month)

    labor_today = float((dashboard.get("today") or {}).get("salary_amount") or 0)
    labor_note = "今日计件工资（已审核报工），可作为人工成本参考"

    top_customers = db.execute(
        select(Customer.name, func.sum(FinanceLedger.amount).label("amount"))
        .select_from(FinanceLedger)
        .join(Customer, Customer.id == FinanceLedger.party_id)
        .where(
            FinanceLedger.party_type == "customer",
            FinanceLedger.direction == "in",
            FinanceLedger.category == "receipt",
            FinanceLedger.biz_date >= month_start,
            FinanceLedger.biz_date < next_month,
        )
        .group_by(Customer.id, Customer.name)
        .order_by(func.sum(FinanceLedger.amount).desc())
        .limit(5)
    ).all()

    return {
        "today": {
            "date": today.isoformat(),
            **today_ledger,
            "labor_cost_estimate": labor_today,
            "labor_cost_note": labor_note,
        },
        "month": {
            "month": today.strftime("%Y-%m"),
            **month_ledger,
            "top_customer_receipts": [
                {"customer_name": r.name, "amount": float(r.amount or 0)} for r in top_customers
            ],
        },
        "notes": [
            "毛利率 = (收入流水 - 支出流水) / 收入流水，数据来自财务流水账（收款/付款）",
            "若今日无流水记录，毛利率可能为空；可引导用户在财务管理补录流水",
        ],
    }


def build_crm_context(db: Session) -> dict:
    open_count = int(
        db.scalar(
            select(func.count(CrmOpportunity.id)).where(
                CrmOpportunity.is_active.is_(True),
                CrmOpportunity.status == "open",
            )
        )
        or 0
    )
    pool_count = int(
        db.scalar(
            select(func.count(CrmOpportunity.id)).where(
                CrmOpportunity.owner_user_id.is_(None),
                CrmOpportunity.is_active.is_(True),
                CrmOpportunity.status == "open",
            )
        )
        or 0
    )
    now = datetime.utcnow()
    due_followups = int(
        db.scalar(
            select(func.count(CrmOpportunityActivity.id))
            .join(CrmOpportunity, CrmOpportunity.id == CrmOpportunityActivity.opportunity_id)
            .where(
                CrmOpportunityActivity.next_follow_up_at.is_not(None),
                CrmOpportunityActivity.next_follow_up_at <= now,
                CrmOpportunity.is_active.is_(True),
                CrmOpportunity.status == "open",
            )
        )
        or 0
    )

    opps = db.scalars(
        select(CrmOpportunity)
        .where(
            CrmOpportunity.is_active.is_(True),
            CrmOpportunity.status == "open",
        )
        .options(selectinload(CrmOpportunity.customer))
        .order_by(CrmOpportunity.amount.is_(None), CrmOpportunity.amount.desc(), CrmOpportunity.id.desc())
        .limit(10)
    ).all()

    stage_rows = db.execute(
        select(CrmOpportunity.stage, func.count(CrmOpportunity.id), func.coalesce(func.sum(CrmOpportunity.amount), 0))
        .where(
            CrmOpportunity.is_active.is_(True),
            CrmOpportunity.status == "open",
        )
        .group_by(CrmOpportunity.stage)
    ).all()

    return {
        "open_opportunities": open_count,
        "public_pool": pool_count,
        "due_followups": due_followups,
        "pipeline_by_stage": [
            {"stage": str(s), "count": int(c), "amount": float(a or 0)} for s, c, a in stage_rows
        ],
        "top_opportunities": [
            {
                "id": o.id,
                "code": o.code,
                "title": o.title,
                "stage": o.stage,
                "amount": float(o.amount) if o.amount is not None else None,
                "customer_name": o.customer.name if o.customer else None,
                "in_public_pool": o.owner_user_id is None,
            }
            for o in opps
        ],
    }


def _purchase_order_amount(po: PurchaseOrder) -> float:
    total = Decimal("0")
    for it in po.items or []:
        total += Decimal(str(it.qty or 0)) * Decimal(str(it.unit_price or 0))
    return float(total)


def build_purchase_context(db: Session) -> dict:
    today = date.today()
    month = today.strftime("%Y-%m")

    status_rows = db.execute(
        select(PurchaseOrder.status, func.count(PurchaseOrder.id))
        .group_by(PurchaseOrder.status)
    ).all()
    by_status = {str(s): int(c) for s, c in status_rows}

    recent = db.scalars(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items))
        .order_by(PurchaseOrder.id.desc())
        .limit(10)
    ).all()
    recent_items = []
    for po in recent:
        supplier = po.supplier
        amt = _purchase_order_amount(po)
        recent_items.append(
            {
                "id": po.id,
                "code": po.code,
                "status": po.status,
                "supplier_name": supplier.name if supplier else None,
                "total_amount": amt,
                "created_at": po.created_at.isoformat() if po.created_at else None,
            }
        )

    month_net = db.scalar(
        select(
            func.coalesce(
                func.sum(PurchaseOrderItem.received_qty * PurchaseOrderItem.unit_price), 0
            )
            - func.coalesce(
                func.sum(PurchaseOrderItem.returned_qty * PurchaseOrderItem.unit_price), 0
            )
        )
        .select_from(PurchaseOrderItem)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id)
        .where(
            PurchaseOrder.status.not_in(["draft", "canceled"]),
            func.date_format(PurchaseOrder.confirmed_at, "%Y-%m") == month,
        )
    )

    pending_receive = int(
        db.scalar(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.status.in_(["confirmed", "partial_received"]),
            )
        )
        or 0
    )

    return {
        "by_status": by_status,
        "recent_orders": recent_items,
        "month": month,
        "month_net_purchase_amount": float(month_net or 0),
        "pending_receive_count": pending_receive,
    }


def build_equipment_context(db: Session) -> dict:
    today = date.today()
    eqs = db.scalars(select(Equipment).order_by(Equipment.id)).all()
    by_status: dict[str, int] = {}
    overdue_maintenance: list[dict] = []
    for eq in eqs:
        by_status[eq.status] = by_status.get(eq.status, 0) + 1
        if eq.next_maintenance_date and eq.next_maintenance_date < today and eq.status == "active":
            overdue_maintenance.append(
                {
                    "id": eq.id,
                    "code": eq.code,
                    "name": eq.name,
                    "next_maintenance_date": eq.next_maintenance_date.isoformat(),
                    "days_overdue": (today - eq.next_maintenance_date).days,
                }
            )

    health = equipment_health_scores(db, days=90)
    at_risk = [x for x in health.get("items") or [] if x.get("level") == "risk"][:8]

    return {
        "total": len(eqs),
        "by_status": by_status,
        "overdue_maintenance": overdue_maintenance[:10],
        "health_at_risk": at_risk,
        "health_summary": {
            "good": sum(1 for x in health.get("items") or [] if x.get("level") == "good"),
            "watch": sum(1 for x in health.get("items") or [] if x.get("level") == "watch"),
            "risk": sum(1 for x in health.get("items") or [] if x.get("level") == "risk"),
        },
    }