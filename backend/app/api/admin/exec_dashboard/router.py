"""老板看板（Executive Dashboard）API

提供 5 大经营指标的聚合查询与下钻数据。
Pro 专属功能，权限点：exec_dashboard.view
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.exec_dashboard import (
    get_capacity_utilization,
    get_collection_rate,
    get_delivery_rate,
    get_exec_dashboard_summary,
    get_order_status_distribution,
    get_overdue_orders,
    get_profit_margin,
    get_revenue,
    get_revenue_trend,
    get_top_customers,
    get_top_skus,
    get_period_range,
)
from app.models.user import User


router = APIRouter(dependencies=[Depends(require_permissions(["exec_dashboard.view"]))])


@router.get("/summary")
def summary_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """老板看板 5 大指标聚合（销售额/毛利率/准交率/回款率/产能利用率）"""
    data = get_exec_dashboard_summary(db, period=period)
    return ok(data)


@router.get("/revenue")
def revenue_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅销售额（轻量调用）"""
    pr = get_period_range(period)
    data = get_revenue(db, period=pr)
    return ok(data)


@router.get("/profit-margin")
def profit_margin_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅毛利率"""
    pr = get_period_range(period)
    data = get_profit_margin(db, period=pr)
    return ok(data)


@router.get("/delivery-rate")
def delivery_rate_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅订单准交率"""
    pr = get_period_range(period)
    data = get_delivery_rate(db, period=pr)
    return ok(data)


@router.get("/collection-rate")
def collection_rate_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅回款率"""
    pr = get_period_range(period)
    data = get_collection_rate(db, period=pr)
    return ok(data)


@router.get("/capacity-utilization")
def capacity_utilization_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅产能利用率"""
    pr = get_period_range(period)
    data = get_capacity_utilization(db, period=pr)
    return ok(data)


@router.get("/revenue-trend")
def revenue_trend_api(
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """销售额趋势（按天）"""
    data = get_revenue_trend(db, days=days)
    return ok(data)


@router.get("/order-status")
def order_status_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """订单状态分布（饼图）"""
    data = get_order_status_distribution(db)
    return ok(data)


@router.get("/top-customers")
def top_customers_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Top N 客户"""
    pr = get_period_range(period)
    data = get_top_customers(db, period=pr, limit=limit)
    return ok(data)


@router.get("/top-skus")
def top_skus_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Top N 产品"""
    pr = get_period_range(period)
    data = get_top_skus(db, period=pr, limit=limit)
    return ok(data)


@router.get("/overdue-orders")
def overdue_orders_api(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """逾期订单"""
    data = get_overdue_orders(db, limit=limit)
    return ok(data)