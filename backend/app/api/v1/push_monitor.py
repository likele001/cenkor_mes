"""推送队列监控API"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import redis as redis_lib

from app.core import deps
from app.core.config import settings
from app.core.deps import get_current_user, require_permissions
from app.models.feishu_push_log import FeishuPushLog
from app.models.wecom_push_log import WecomPushLog
from app.models.dingtalk_push_log import DingtalkPushLog
from app.models.user import User


# 系统级运行状态（含 Redis 全局队列长度），仅允许系统设置管理员查看
router = APIRouter(tags=["推送监控"], dependencies=[Depends(require_permissions(["setting.manage"]))])


def _get_redis_client():
    """获取Redis连接（统一使用配置的REDIS_URL，避免硬编码db不一致）"""
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _get_redis_stats():
    """获取Redis队列统计（系统级，无租户隔离）"""
    r = _get_redis_client()

    stats = {
        'queues': {},
        'total': 0
    }

    try:
        for queue in ['celery', 'default', 'ai']:
            try:
                length = r.llen(queue)
                stats['queues'][queue] = length
                stats['total'] += length
            except Exception:
                stats['queues'][queue] = 0
    finally:
        r.close()

    return stats


def _channel_stats(db: Session, tenant_id: int, model):
    """按租户统计某通道的今日推送数据"""
    today = datetime.utcnow().date()
    base = select(func.count(model.id)).where(
        model.tenant_id == tenant_id,
        func.date(model.created_at) == today,
    )
    total = db.scalar(base) or 0
    success = db.scalar(base.where(model.status == 'success')) or 0
    failed = db.scalar(base.where(model.status == 'failed')) or 0
    pending = db.scalar(base.where(model.status.in_(['pending', 'deferred']))) or 0
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "pending": pending,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0,
    }


@router.get("/status")
def get_push_status(
    db: Session = Depends(deps.get_db),
    user: User = Depends(get_current_user),
):
    """获取推送系统整体状态（仅当前租户数据）"""
    redis_stats = _get_redis_stats()

    feishu = _channel_stats(db, user.tenant_id, FeishuPushLog)
    wecom = _channel_stats(db, user.tenant_id, WecomPushLog)
    dingtalk = _channel_stats(db, user.tenant_id, DingtalkPushLog)

    is_healthy = (
        redis_stats['total'] < 100 and
        feishu['failed'] == 0 and
        wecom['failed'] == 0 and
        dingtalk['failed'] == 0
    )

    return {
        "code": 200,
        "msg": "获取成功",
        "data": {
            "timestamp": datetime.now().isoformat(),
            "healthy": is_healthy,
            "redis": redis_stats,
            "channels": {
                "feishu": feishu,
                "wecom": wecom,
                "dingtalk": dingtalk,
            },
            "summary": {
                "total": feishu["total"] + wecom["total"] + dingtalk["total"],
                "success": feishu["success"] + wecom["success"] + dingtalk["success"],
                "failed": feishu["failed"] + wecom["failed"] + dingtalk["failed"],
                "pending": feishu["pending"] + wecom["pending"] + dingtalk["pending"],
            },
        },
    }


_CHANNEL_MODEL_MAP = {
    "feishu": FeishuPushLog,
    "wecom": WecomPushLog,
    "dingtalk": DingtalkPushLog,
}


@router.get("/logs/{channel}")
def get_push_logs(
    channel: str,
    limit: int = 20,
    status: str = None,
    db: Session = Depends(deps.get_db),
    user: User = Depends(get_current_user),
):
    """获取推送日志（仅当前租户）"""
    model = _CHANNEL_MODEL_MAP.get(channel)
    if not model:
        return {"code": 400, "msg": "无效的渠道", "data": None}

    query = (
        db.query(model)
        .filter(model.tenant_id == user.tenant_id)
        .order_by(model.created_at.desc())
        .limit(limit)
    )

    if status:
        query = query.filter(model.status == status)

    logs = query.all()

    return {
        "code": 200,
        "msg": "获取成功",
        "data": [
            {
                "id": log.id,
                "event_code": log.event_code,
                "target_kind": log.target_kind,
                "target_ref": log.target_ref[:20] + "..." if len(log.target_ref) > 20 else log.target_ref,
                "title": log.title,
                "status": log.status,
                "error_msg": log.error_msg,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
            }
            for log in logs
        ],
    }


@router.post("/test/{channel}")
def test_push(
    channel: str,
    db: Session = Depends(deps.get_db),
    user: User = Depends(get_current_user),
):
    """测试推送通道（使用当前登录用户的租户）"""
    from app.services.notify_dispatcher import dispatch

    test_titles = {
        "feishu": "飞书推送测试",
        "wecom": "企业微信推送测试",
        "dingtalk": "钉钉推送测试",
    }

    try:
        count = dispatch(
            db,
            event_code="test.push",
            title=test_titles.get(channel, "推送测试"),
            content=f"这是一条来自LightMes系统的推送测试消息，发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            level="info",
            biz_type="test",
            biz_id=0,
        )
        db.commit()

        return {
            "code": 200,
            "msg": f"测试消息已发送到 {channel}，共 {count} 条",
            "data": {"count": count},
        }
    except Exception as e:
        db.rollback()
        return {
            "code": 500,
            "msg": f"推送失败：{str(e)[:200]}",
            "data": None,
        }


@router.post("/clear-queue")
def clear_celery_queue(
    user: User = Depends(get_current_user),
):
    """清空Celery队列（仅超级管理员可操作）"""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可清空队列")

    r = _get_redis_client()
    length = r.llen('celery')
    r.delete('celery')
    r.close()

    return {
        "code": 200,
        "msg": f"已清空celery队列，删除了 {length} 个任务",
        "data": {"cleared": length},
    }
