# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""后台在线升级 / 回滚 API（仅超级管理员可用）。"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.models.upgrade_job import UpgradeJob
from app.models.user import User
from app.services import upgrade_service

router = APIRouter()


def get_superuser(user: User = Depends(get_current_user)) -> User:
    """升级/回滚是高危操作，只允许超级管理员。

    项目既有判定方式：User.is_superuser 布尔字段（见 admin/system/permissions.py 等处
    直接 `if not user.is_superuser: raise 403`）。这里沿用该字段，不做 role code 判断。
    """
    if not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="仅超级管理员可执行升级/回滚")
    return user


class StartIn(BaseModel):
    target_version: str
    skip_frontend: bool = False


class RollbackIn(BaseModel):
    job_id: int
    restore_db: bool = False


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _job_out(job: UpgradeJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "action": job.action,
        "from_version": job.from_version,
        "to_version": job.to_version,
        "status": job.status,
        "stage": job.stage,
        "from_ref": job.from_ref,
        "alembic_rev": job.alembic_rev,
        "backup_path": job.backup_path,
        "log_path": job.log_path,
        "operator_id": job.operator_id,
        "error": job.error,
        "started_at": _dt(job.started_at),
        "finished_at": _dt(job.finished_at),
    }


@router.get("/check")
def check_upgrade(_user: User = Depends(get_superuser)):
    """检查是否有新版本。"""
    try:
        data = upgrade_service.check_update()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ok(data)


@router.post("/start")
def start_upgrade(
    payload: StartIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_superuser),
):
    """创建升级任务并立即在后台线程执行。"""
    try:
        job = upgrade_service.create_job(db, "upgrade", payload.target_version, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    upgrade_service.log_note(job.id, f"skip_frontend={payload.skip_frontend}，操作人={user.username}")
    upgrade_service.run_job(job.id)
    return ok(_job_out(job))


@router.get("/jobs")
def list_jobs(
    db: Session = Depends(get_db),
    _user: User = Depends(get_superuser),
):
    """最近 20 条任务。"""
    upgrade_service.reconcile_restarts(db)  # 重启后旧进程线程已消失，这里补回任务状态
    rows = db.execute(select(UpgradeJob).order_by(UpgradeJob.id.desc()).limit(20)).scalars().all()
    return ok({"items": [_job_out(x) for x in rows]})


@router.get("/jobs/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_superuser),
):
    upgrade_service.reconcile_restarts(db)
    job = db.get(UpgradeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ok(_job_out(job))


@router.get("/jobs/{job_id}/log")
def get_job_log(
    job_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=2000, ge=1, le=10000),
    db: Session = Depends(get_db),
    _user: User = Depends(get_superuser),
):
    """任务执行日志（文本切片）。"""
    job = db.get(UpgradeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    content = upgrade_service.read_log(job_id, offset=offset, limit=limit)
    return ok({"content": content, "offset": offset, "length": len(content)})


@router.post("/jobs/{job_id}/verify")
def verify_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_superuser),
):
    """对指定任务做一次健康校验（awaiting_restart 后手动确认用）。"""
    try:
        result = upgrade_service.verify_job(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ok(result)


@router.post("/rollback")
def rollback(
    payload: RollbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_superuser),
):
    """按指定任务的 from_ref 回滚代码（可选恢复数据库备份）。"""
    try:
        job = upgrade_service.rollback_job(db, payload.job_id, payload.restore_db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    job.operator_id = user.id
    db.commit()
    db.refresh(job)
    upgrade_service.log_note(job.id, f"操作人={user.username}")
    return ok(_job_out(job))
