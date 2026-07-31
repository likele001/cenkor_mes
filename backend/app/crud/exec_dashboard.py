"""老板看板（Executive Dashboard）5 大指标聚合查询

指标定义：
1. 销售额（revenue）：订单状态=completed，amount 之和（按 period）
2. 毛利率（profit_margin）：(revenue - cost) / revenue * 100
3. 订单准交率（delivery_rate）：已确认订单中，实际完成时间 <= 交期的占比
4. 回款率（collection_rate）：finance_ledgers 中 incoming 累计 / 销售订单总金额
5. 产能利用率（capacity_utilization）：work_orders 实际工时 / 标准工时 * 100
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select, and_, or_
from sqlalchemy.orm import Session

from app.models.finance_ledger import FinanceLedger
from app.models.order import Order
from app.models.work_order import WorkOrder


@dataclass
class PeriodRange:
    start: datetime
    end: datetime
    prev_start: datetime
    prev_end: datetime

    @property
    def label(self) -> str:
        return self.start.strftime("%Y-%m-%d")


def get_period_range(period: str, today: date | None = None) -> PeriodRange:
    """根据 period 计算时间区间（含上期对比）"""
    today = today or date.today()
    if period == "today":
        start = datetime.combine(today, time.min)
        end = datetime.combine(today + timedelta(days=1), time.min)
        prev_start = start - timedelta(days=1)
        prev_end = start
    elif period == "week":
        # 本周一 0 点起
        this_monday = today - timedelta(days=today.weekday())
        start = datetime.combine(this_monday, time.min)
        end = start + timedelta(days=7)
        prev_start = start - timedelta(days=7)
        prev_end = start
    elif period == "month":
        first = today.replace(day=1)
        if first.month == 12:
            next_first = first.replace(year=first.year + 1, month=1)
        else:
            next_first = first.replace(month=first.month + 1)
        start = datetime.combine(first, time.min)
        end = datetime.combine(next_first, time.min)
        prev_end = start
        if first.month == 1:
            prev_first = first.replace(year=first.year - 1, month=12)
        else:
            prev_first = first.replace(month=first.month - 1)
        prev_start = datetime.combine(prev_first, time.min)
    elif period == "quarter":
        q = (today.month - 1) // 3 + 1
        first_month = (q - 1) * 3 + 1
        first = today.replace(month=first_month, day=1)
        if first_month + 3 > 12:
            next_first = first.replace(year=first.year + 1, month=1)
        else:
            next_first = first.replace(month=first_month + 3, day=1)
        start = datetime.combine(first, time.min)
        end = datetime.combine(next_first, time.min)
        prev_first = first - timedelta(days=1)
        prev_first = prev_first.replace(day=1)
        prev_start = datetime.combine(prev_first, time.min)
        prev_end = start
    else:
        # 默认本月
        return get_period_range("month", today)
    return PeriodRange(start=start, end=end, prev_start=prev_start, prev_end=prev_end)


def _safe_ratio(numerator: float | int | None, denominator: float | int | None) -> float:
    """安全计算比率（百分比，保留 2 位小数）"""
    n = float(numerator or 0)
    d = float(denominator or 0)
    if d == 0:
        return 0.0
    return round(n / d * 100, 2)


def _safe_delta(current: float, previous: float) -> float:
    """环比增量（百分点）"""
    return round(current - previous, 2)


def get_revenue(db: Session, period: PeriodRange) -> dict:
    """销售额：完成订单的 amount 之和（包含已确认+已完成，参考通用做法）"""
    revenue_row = db.execute(
        select(
            func.coalesce(func.sum(Order.amount), 0).label("rev"),
            func.count(Order.id).label("cnt"),
        ).where(
            Order.status.in_(("confirmed", "completed", "producing", "shipped")),
            Order.confirmed_at >= period.start,
            Order.confirmed_at < period.end,
        )
    ).one()
    revenue = float(revenue_row.rev or 0)
    order_count = int(revenue_row.cnt or 0)

    prev_row = db.execute(
        select(func.coalesce(func.sum(Order.amount), 0)).where(
            Order.status.in_(("confirmed", "completed", "producing", "shipped")),
            Order.confirmed_at >= period.prev_start,
            Order.confirmed_at < period.prev_end,
        )
    ).one()
    prev_revenue = float(prev_row[0] or 0)

    return {
        "value": round(revenue, 2),
        "prev_value": round(prev_revenue, 2),
        "order_count": order_count,
        "change_pct": _safe_ratio(revenue - prev_revenue, prev_revenue) if prev_revenue else 0.0,
    }


def get_profit_margin(db: Session, period: PeriodRange) -> dict:
    """毛利率：(收入 - 成本) / 收入 * 100%
    成本来源：orders.cost_amount（订单级成本）
    """
    row = db.execute(
        select(
            func.coalesce(func.sum(Order.amount), 0).label("rev"),
            func.coalesce(func.sum(Order.cost_amount), 0).label("cost"),
        ).where(
            Order.status.in_(("confirmed", "completed", "producing", "shipped")),
            Order.confirmed_at >= period.start,
            Order.confirmed_at < period.end,
        )
    ).one()
    revenue = float(row.rev or 0)
    cost = float(row.cost or 0)
    margin = _safe_ratio(revenue - cost, revenue) if revenue else 0.0

    prev_row = db.execute(
        select(
            func.coalesce(func.sum(Order.amount), 0).label("rev"),
            func.coalesce(func.sum(Order.cost_amount), 0).label("cost"),
        ).where(
            Order.status.in_(("confirmed", "completed", "producing", "shipped")),
            Order.confirmed_at >= period.prev_start,
            Order.confirmed_at < period.prev_end,
        )
    ).one()
    prev_margin = _safe_ratio(float(prev_row.rev or 0) - float(prev_row.cost or 0), prev_row.rev or 0)

    has_cost_data = cost > 0 or revenue > 0
    return {
        "value": margin,
        "prev_value": prev_margin,
        "change_pct": _safe_delta(margin, prev_margin),
        "has_cost_data": has_cost_data,
    }


def get_delivery_rate(db: Session, period: PeriodRange) -> dict:
    """订单准交率：在截止日期前（含当天）完成（或确认完成）的订单 / 已确认订单总数
    判断逻辑：actual_completed_at <= due_date（按天比较）
    """
    # 总订单：已确认且在期内
    total_row = db.execute(
        select(func.count(Order.id)).where(
            Order.due_date.isnot(None),
            Order.confirmed_at >= period.start,
            Order.confirmed_at < period.end,
        )
    ).one()
    total = int(total_row[0] or 0)

    on_time_row = db.execute(
        select(func.count(Order.id)).where(
            Order.due_date.isnot(None),
            Order.confirmed_at >= period.start,
            Order.confirmed_at < period.end,
            Order.actual_completed_at.isnot(None),
            func.date(Order.actual_completed_at) <= Order.due_date,
        )
    ).one()
    on_time = int(on_time_row[0] or 0)

    rate = _safe_ratio(on_time, total)

    prev_total_row = db.execute(
        select(func.count(Order.id)).where(
            Order.due_date.isnot(None),
            Order.confirmed_at >= period.prev_start,
            Order.confirmed_at < period.prev_end,
        )
    ).one()
    prev_total = int(prev_total_row[0] or 0)

    prev_on_time_row = db.execute(
        select(func.count(Order.id)).where(
            Order.due_date.isnot(None),
            Order.confirmed_at >= period.prev_start,
            Order.confirmed_at < period.prev_end,
            Order.actual_completed_at.isnot(None),
            func.date(Order.actual_completed_at) <= Order.due_date,
        )
    ).one()
    prev_on_time = int(prev_on_time_row[0] or 0)
    prev_rate = _safe_ratio(prev_on_time, prev_total)

    return {
        "value": rate,
        "prev_value": prev_rate,
        "on_time": on_time,
        "total": total,
        "change_pct": _safe_delta(rate, prev_rate),
    }


def get_collection_rate(db: Session, period: PeriodRange) -> dict:
    """回款率：期内财务账本中 direction=in 的累计 / 期内销售订单总金额
    """
    revenue_row = db.execute(
        select(func.coalesce(func.sum(Order.amount), 0)).where(
            Order.status.in_(("confirmed", "completed", "producing", "shipped")),
            Order.confirmed_at >= period.start,
            Order.confirmed_at < period.end,
        )
    ).one()
    revenue = float(revenue_row[0] or 0)

    collection_row = db.execute(
        select(func.coalesce(func.sum(FinanceLedger.amount), 0)).where(
            FinanceLedger.direction == "in",
            FinanceLedger.biz_date >= period.start.date(),
            FinanceLedger.biz_date < period.end.date(),
        )
    ).one()
    collected = float(collection_row[0] or 0)

    rate = _safe_ratio(collected, revenue)

    prev_revenue = float(
        db.execute(
            select(func.coalesce(func.sum(Order.amount), 0)).where(
                Order.status.in_(("confirmed", "completed", "producing", "shipped")),
                Order.confirmed_at >= period.prev_start,
                Order.confirmed_at < period.prev_end,
            )
        ).one()[0]
        or 0
    )

    prev_collected = float(
        db.execute(
            select(func.coalesce(func.sum(FinanceLedger.amount), 0)).where(
                FinanceLedger.direction == "in",
                FinanceLedger.biz_date >= period.prev_start.date(),
                FinanceLedger.biz_date < period.prev_end.date(),
            )
        ).one()[0]
        or 0
    )
    prev_rate = _safe_ratio(prev_collected, prev_revenue)

    return {
        "value": rate,
        "prev_value": prev_rate,
        "collected": round(collected, 2),
        "pending": round(max(revenue - collected, 0), 2),
        "change_pct": _safe_delta(rate, prev_rate),
    }


def get_capacity_utilization(db: Session, period: PeriodRange) -> dict:
    """产能利用率：实际工时 / 标准工时 * 100%
    仅统计期内已创建工单
    """
    row = db.execute(
        select(
            func.coalesce(func.sum(WorkOrder.standard_hours), 0).label("std"),
            func.coalesce(func.sum(WorkOrder.actual_hours), 0).label("act"),
            func.count(WorkOrder.id).label("cnt"),
        ).where(
            WorkOrder.created_at >= period.start,
            WorkOrder.created_at < period.end,
        )
    ).one()
    standard = float(row.std or 0)
    actual = float(row.act or 0)
    util = _safe_ratio(actual, standard) if standard else 0.0

    prev_row = db.execute(
        select(
            func.coalesce(func.sum(WorkOrder.standard_hours), 0),
            func.coalesce(func.sum(WorkOrder.actual_hours), 0),
        ).where(
            WorkOrder.created_at >= period.prev_start,
            WorkOrder.created_at < period.prev_end,
        )
    ).one()
    prev_util = _safe_ratio(float(prev_row[1] or 0), float(prev_row[0] or 0)) if prev_row[0] else 0.0

    return {
        "value": util,
        "prev_value": prev_util,
        "standard_hours": round(standard, 2),
        "actual_hours": round(actual, 2),
        "work_order_count": int(row.cnt or 0),
        "change_pct": _safe_delta(util, prev_util),
    }


def get_exec_dashboard_summary(db: Session, period: str = "month") -> dict:
    """老板看板 5 大指标聚合入口"""
    period_range = get_period_range(period)

    revenue = get_revenue(db, period_range)
    profit = get_profit_margin(db, period_range)
    delivery = get_delivery_rate(db, period_range)
    collection = get_collection_rate(db, period_range)
    capacity = get_capacity_utilization(db, period_range)

    return {
        "period": period,
        "period_start": period_range.start.isoformat(),
        "period_end": period_range.end.isoformat(),
        "revenue": revenue,
        "profit_margin": profit,
        "delivery_rate": delivery,
        "collection_rate": collection,
        "capacity_utilization": capacity,
    }


def get_revenue_trend(db: Session, days: int = 30) -> list[dict]:
    """销售额趋势（按天聚合）"""
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, time.min)

    rows = db.execute(
        select(
            func.date(Order.confirmed_at).label("d"),
            func.coalesce(func.sum(Order.amount), 0).label("rev"),
            func.count(Order.id).label("cnt"),
        ).where(
            Order.status.in_(("confirmed", "completed", "producing", "shipped")),
            Order.confirmed_at >= start_dt,
        ).group_by(func.date(Order.confirmed_at)).order_by(func.date(Order.confirmed_at))
    ).all()

    by_date = {str(r.d): float(r.rev or 0) for r in rows}

    series = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        key = d.isoformat()
        series.append({
            "date": key,
            "amount": by_date.get(key, 0),
        })

    return series


def get_order_status_distribution(db: Session) -> list[dict]:
    """订单状态分布（饼图）"""
    rows = db.execute(
        select(Order.status, func.count(Order.id).label("cnt")).where(
            Order.status.in_(("draft", "pending_confirm", "confirmed", "producing", "shipped", "completed", "cancelled")),
        ).group_by(Order.status)
    ).all()
    return [{"status": r.status, "count": int(r.cnt or 0)} for r in rows]


def get_top_customers(db: Session, period: PeriodRange, limit: int = 5) -> list[dict]:
    """Top N 客户（按销售额）"""
    from app.models.customer import Customer

    rows = db.execute(
        select(
            Customer.id.label("cid"),
            Customer.name.label("cname"),
            func.coalesce(func.sum(Order.amount), 0).label("rev"),
            func.count(Order.id).label("cnt"),
        ).join(Customer, Order.customer_id == Customer.id).where(
            Order.status.in_(("confirmed", "completed", "producing", "shipped")),
            Order.confirmed_at >= period.start,
            Order.confirmed_at < period.end,
        ).group_by(Customer.id, Customer.name).order_by(func.sum(Order.amount).desc()).limit(limit)
    ).all()

    return [
        {
            "customer_id": r.cid,
            "customer_name": r.cname,
            "amount": float(r.rev or 0),
            "order_count": int(r.cnt or 0),
        }
        for r in rows
    ]


def get_top_skus(db: Session, period: PeriodRange, limit: int = 5) -> list[dict]:
    """Top N 产品（按销售额，需 join order_items）"""
    from app.models.order import OrderItem
    from app.models.sku import Sku

    rows = db.execute(
        select(
            OrderItem.sku_id.label("sid"),
            Sku.code.label("scode"),
            Sku.name.label("sname"),
            func.coalesce(func.sum(OrderItem.subtotal), 0).label("rev"),
            func.coalesce(func.sum(OrderItem.qty), 0).label("qty"),
        ).join(Order, Order.id == OrderItem.order_id).join(Sku, OrderItem.sku_id == Sku.id).where(
            Order.status.in_(("confirmed", "completed", "producing", "shipped")),
            Order.confirmed_at >= period.start,
            Order.confirmed_at < period.end,
        ).group_by(OrderItem.sku_id, Sku.code, Sku.name).order_by(func.sum(OrderItem.subtotal).desc()).limit(limit)
    ).all()

    return [
        {
            "sku_id": r.sid,
            "sku_code": r.scode,
            "sku_name": r.sname,
            "quantity": int(r.qty or 0),
            "amount": float(r.rev or 0),
        }
        for r in rows
    ]


def get_overdue_orders(db: Session, limit: int = 10) -> list[dict]:
    """逾期未完成订单"""
    from app.models.customer import Customer

    today = date.today()
    rows = db.execute(
        select(
            Order.id,
            Order.code,
            Order.customer_id,
            Customer.name.label("cname"),
            Order.due_date,
            Order.amount,
        ).join(Customer, Order.customer_id == Customer.id).where(
            Order.due_date.isnot(None),
            Order.due_date < today,
            Order.status.notin_(("completed", "cancelled")),
        ).order_by(Order.due_date.asc()).limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "customer_name": r.cname,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "days_overdue": (today - r.due_date).days if r.due_date else 0,
            "amount": float(r.amount or 0),
        }
        for r in rows
    ]