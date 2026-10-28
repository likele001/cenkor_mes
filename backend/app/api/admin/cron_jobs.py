# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""
定时任务管理 API
- GET /admin/cron-jobs — 列表（附带 saas_mode，供前端决定是否隐藏部署级运维）
- PUT /admin/cron-jobs/{id} — 更新（修改后发 Redis reload 信号）
- POST /admin/cron-jobs/reload — 手动触发重载
- GET /admin/cron-jobs/defaults — 获取系统默认任务定义
- GET /admin/cron-jobs/worker/status — Celery Worker 状态（只读）
- POST /admin/cron-jobs/worker/restart — 优雅重启 Worker（SaaS 模式 403）
- POST /admin/cron-jobs/beat/status — Celery Beat（systemd 单元）状态（只读）
- POST /admin/cron-jobs/beat/restart — Redis 退出信号重启 Beat（SaaS 模式 403）

定时任务与 Worker/Beat 都是部署级全局资源，页面与接口统一要求 setting.manage；
SaaS 模式下重启会影响全部租户，收敛给平台运维，租户端只保留只读状态。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import redis as redis_lib

from app.core.config import settings
from app.core.deps import get_db, require_permissions
from app.core.response import ok
from app.crud.platform_setting import is_saas_mode_enabled
from app.models.cron_job import CronJob
from app.services.worker_control import (
    get_beat_status,
    get_worker_status,
    request_beat_restart,
    request_worker_restart,
)

router = APIRouter(dependencies=[Depends(require_permissions(["setting.manage"]))])

RELOAD_KEY = "celery:beat:reload"

WORKER_SAAS_BLOCK_MSG = "Worker 管理为部署级运维操作，SaaS 模式下请联系平台运维"
BEAT_SAAS_BLOCK_MSG = "Beat 管理为部署级运维操作，SaaS 模式下请联系平台运维"


class CronJobUpdateIn(BaseModel):
    enabled: bool | None = None
    cron_minute: str | None = Field(None, max_length=10)
    cron_hour: str | None = Field(None, max_length=10)
    cron_day_of_month: str | None = Field(None, max_length=10)
    cron_month_of_year: str | None = Field(None, max_length=10)
    cron_day_of_week: str | None = Field(None, max_length=10)
    description: str | None = Field(None, max_length=255)


@router.get("")
def list_cron_jobs(db: Session = Depends(get_db)):
    """获取所有定时任务；saas_mode 供前端决定 Worker/Beat 运维是否可见"""
    stmt = select(CronJob).order_by(CronJob.id)
    jobs = db.execute(stmt).scalars().all()
    return ok({
        "items": [j.to_dict() for j in jobs],
        "saas_mode": is_saas_mode_enabled(db),
    })


@router.put("/{job_id}")
def update_cron_job(job_id: int, data: CronJobUpdateIn, db: Session = Depends(get_db)):
    """更新定时任务配置，修改后通知 Beat 重载"""
    job = db.get(CronJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(job, k, v)

    db.commit()
    db.refresh(job)

    # 通知 Beat 重新加载
    try:
        r = redis_lib.from_url(settings.REDIS_URL)
        r.set(RELOAD_KEY, "1", ex=60)
        r.close()
    except Exception:
        pass

    return ok(job.to_dict(), msg="保存成功，调度器将在 10 秒内生效")


@router.post("/reload")
def reload_cron_jobs():
    """手动触发 Beat 重新加载调度配置（10秒内生效）"""
    try:
        r = redis_lib.from_url(settings.REDIS_URL)
        r.set(RELOAD_KEY, "1", ex=60)
        r.close()
        return ok(None, msg="重载信号已发送，调度器将在 10 秒内重新加载")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/defaults")
def get_default_cron_jobs():
    """返回系统默认任务定义（用于前端参考）"""
    from app.celery_app import DEFAULT_CRON_JOBS
    return ok(DEFAULT_CRON_JOBS)


@router.get("/worker/status")
def worker_status_api():
    """Celery Worker 在线状态与正在执行的任务（只读）"""
    return ok(get_worker_status())


@router.post("/worker/restart")
def worker_restart_api(db: Session = Depends(get_db)):
    """优雅重启 Worker：广播 shutdown，worker 跑完在飞任务后由 systemd 拉起新代码"""
    if is_saas_mode_enabled(db):
        raise HTTPException(status_code=403, detail=WORKER_SAAS_BLOCK_MSG)
    result = request_worker_restart()
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result.get("error") or "Worker 重启失败")
    return ok(result, msg="Worker 正在重启，约 10 秒内恢复")


@router.post("/beat/status")
def beat_status_api():
    """Celery Beat（systemd 单元）运行状态（只读）"""
    return ok(get_beat_status())


@router.post("/beat/restart")
def beat_restart_api(db: Session = Depends(get_db)):
    """重启 Beat：写 Redis 退出信号，Beat 自行退出后由 systemd 拉起新进程加载最新调度表"""
    if is_saas_mode_enabled(db):
        raise HTTPException(status_code=403, detail=BEAT_SAAS_BLOCK_MSG)
    result = request_beat_restart()
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result.get("error") or "Beat 重启失败")
    return ok(result, msg="Beat 正在重启，约 5 秒内恢复")
