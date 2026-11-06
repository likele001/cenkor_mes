# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""老板看板（Executive Dashboard）API

提供 5 大经营指标的聚合查询与下钻数据。
权限点：exec_dashboard.view（require_pro 当前为空透传，单版本交付全员开放）
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions, require_pro
from app.core.response import ok
from app.core.business_cache import NS_DASHBOARD, TTL_DASHBOARD, cached
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


# 注：require_pro 目前为空透传（单版本交付，不区分社区/专业版）。
router = APIRouter(dependencies=[Depends(require_permissions(["exec_dashboard.view"])), Depends(require_pro("经营驾驶舱"))])


def _cached(endpoint: str, params: tuple, loader, *, user: User):
    """看板聚合读缓存：key 含端点 + 业务参数 + tenant。

    失效由 core/business_cache 的 Session 级事件按 namespace 自动完成；
    60s TTL 是最终一致的兜底，即使某张写入表未纳入 watcher 也不会长期脏读。
    """
    return ok(cached(
        NS_DASHBOARD,
        (endpoint, user.tenant_id) + tuple(params),
        TTL_DASHBOARD,
        loader,
    ))


@router.get("/summary")
def summary_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """老板看板 5 大指标聚合（销售额/毛利率/准交率/回款率/产能利用率）"""
    return _cached("summary", (period,), lambda: get_exec_dashboard_summary(db, period=period), user=user)


@router.get("/revenue")
def revenue_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅销售额（轻量调用）"""
    return _cached("revenue", (period,), lambda: get_revenue(db, period=get_period_range(period)), user=user)


@router.get("/profit-margin")
def profit_margin_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅毛利率"""
    return _cached("profit-margin", (period,), lambda: get_profit_margin(db, period=get_period_range(period)), user=user)


@router.get("/delivery-rate")
def delivery_rate_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅订单准交率"""
    return _cached("delivery-rate", (period,), lambda: get_delivery_rate(db, period=get_period_range(period)), user=user)


@router.get("/collection-rate")
def collection_rate_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅回款率"""
    return _cached("collection-rate", (period,), lambda: get_collection_rate(db, period=get_period_range(period)), user=user)


@router.get("/capacity-utilization")
def capacity_utilization_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """仅产能利用率"""
    return _cached("capacity-utilization", (period,), lambda: get_capacity_utilization(db, period=get_period_range(period)), user=user)


@router.get("/revenue-trend")
def revenue_trend_api(
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """销售额趋势（按天）"""
    return _cached("revenue-trend", (days,), lambda: get_revenue_trend(db, days=days), user=user)


@router.get("/order-status")
def order_status_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """订单状态分布（饼图）"""
    return _cached("order-status", (), lambda: get_order_status_distribution(db), user=user)


@router.get("/top-customers")
def top_customers_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Top N 客户"""
    return _cached("top-customers", (period, limit), lambda: get_top_customers(db, period=get_period_range(period), limit=limit), user=user)


@router.get("/top-skus")
def top_skus_api(
    period: str = Query(default="month", pattern="^(today|week|month|quarter)$"),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Top N 产品"""
    return _cached("top-skus", (period, limit), lambda: get_top_skus(db, period=get_period_range(period), limit=limit), user=user)


@router.get("/overdue-orders")
def overdue_orders_api(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """逾期订单"""
    return _cached("overdue-orders", (limit,), lambda: get_overdue_orders(db, limit=limit), user=user)