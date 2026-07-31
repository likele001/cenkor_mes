from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.dashboard import get_dashboard_charts, get_dashboard_summary
from app.crud.kanban import get_kanban_order_detail, list_kanban_orders
from app.models.dingtalk_push_log import DingtalkPushLog
from app.models.feishu_push_log import FeishuPushLog
from app.models.user import User
from app.models.wecom_push_log import WecomPushLog


router = APIRouter(dependencies=[Depends(require_permissions(["dashboard.view"]))])


@router.get("/summary")
def summary_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = get_dashboard_summary(db)
    return ok(data)


@router.get("/kanban/orders")
def kanban_orders_api(
    status: str | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    due_from: date | None = Query(default=None),
    due_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_kanban_orders(
        db,
        status=status,
        customer_id=customer_id,
        due_from=due_from,
        due_to=due_to,
        offset=offset,
        limit=limit,
    )
    return ok({"items": items})


@router.get("/kanban/orders/{order_id}")
def kanban_order_detail_api(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = get_kanban_order_detail(db, order_id=order_id)
    if not data:
        raise HTTPException(status_code=400, detail="订单不存在")
    return ok(data)


@router.get("/charts")
def charts_api(
    days: int = Query(default=14, ge=7, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """首页趋势图表数据（日报工趋势 + 工序排名）"""
    data = get_dashboard_charts(db, days=days)
    return ok(data)


@router.get("/push-stats")
def push_stats_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """今日推送统计：飞书 + 企业微信 + 钉钉 合并"""
    today_start = datetime.combine(date.today(), time.min)

    feishu_total = int(
        db.scalar(
            select(func.count(FeishuPushLog.id)).where(
                FeishuPushLog.created_at >= today_start,
            )
        )
        or 0
    )
    feishu_success = int(
        db.scalar(
            select(func.count(FeishuPushLog.id)).where(
                FeishuPushLog.created_at >= today_start,
                FeishuPushLog.status == "success",
            )
        )
        or 0
    )
    feishu_failed = int(
        db.scalar(
            select(func.count(FeishuPushLog.id)).where(
                FeishuPushLog.created_at >= today_start,
                FeishuPushLog.status == "failed",
            )
        )
        or 0
    )
    feishu_retry = int(
        db.scalar(
            select(func.count(FeishuPushLog.id)).where(
                FeishuPushLog.created_at >= today_start,
                FeishuPushLog.retry_count > 0,
            )
        )
        or 0
    )

    wecom_total = int(
        db.scalar(
            select(func.count(WecomPushLog.id)).where(
                WecomPushLog.created_at >= today_start,
            )
        )
        or 0
    )
    wecom_success = int(
        db.scalar(
            select(func.count(WecomPushLog.id)).where(
                WecomPushLog.created_at >= today_start,
                WecomPushLog.status == "success",
            )
        )
        or 0
    )
    wecom_failed = int(
        db.scalar(
            select(func.count(WecomPushLog.id)).where(
                WecomPushLog.created_at >= today_start,
                WecomPushLog.status == "failed",
            )
        )
        or 0
    )
    wecom_retry = int(
        db.scalar(
            select(func.count(WecomPushLog.id)).where(
                WecomPushLog.created_at >= today_start,
                WecomPushLog.retry_count > 0,
            )
        )
        or 0
    )

    dingtalk_total = int(
        db.scalar(
            select(func.count(DingtalkPushLog.id)).where(
                DingtalkPushLog.created_at >= today_start,
            )
        )
        or 0
    )
    dingtalk_success = int(
        db.scalar(
            select(func.count(DingtalkPushLog.id)).where(
                DingtalkPushLog.created_at >= today_start,
                DingtalkPushLog.status == "success",
            )
        )
        or 0
    )
    dingtalk_failed = int(
        db.scalar(
            select(func.count(DingtalkPushLog.id)).where(
                DingtalkPushLog.created_at >= today_start,
                DingtalkPushLog.status == "failed",
            )
        )
        or 0
    )
    dingtalk_retry = int(
        db.scalar(
            select(func.count(DingtalkPushLog.id)).where(
                DingtalkPushLog.created_at >= today_start,
                DingtalkPushLog.retry_count > 0,
            )
        )
        or 0
    )

    today_total = feishu_total + wecom_total + dingtalk_total
    today_success = feishu_success + wecom_success + dingtalk_success
    today_failed = feishu_failed + wecom_failed + dingtalk_failed
    today_retry = feishu_retry + wecom_retry + dingtalk_retry
    retry_rate = round((today_retry / today_total * 100), 1) if today_total else 0.0

    return ok({
        "today_total": today_total,
        "today_success": today_success,
        "today_failed": today_failed,
        "today_retry": today_retry,
        "retry_rate": retry_rate,
        "by_channel": {
            "feishu": {
                "total": feishu_total,
                "success": feishu_success,
                "failed": feishu_failed,
                "retry": feishu_retry,
            },
            "wecom": {
                "total": wecom_total,
                "success": wecom_success,
                "failed": wecom_failed,
                "retry": wecom_retry,
            },
            "dingtalk": {
                "total": dingtalk_total,
                "success": dingtalk_success,
                "failed": dingtalk_failed,
                "retry": dingtalk_retry,
            },
        },
    })
