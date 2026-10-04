# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""历史附件批量迁移服务（local → 目标云 provider）。

设计要点：
- 不依赖 Celery worker（本部署无 cenkormes worker），用进程内守护线程执行；
  任务状态持久化于 cloud_storage_migration_jobs，前端轮询 /migration/latest 看进度。
- 幂等可续跑：迁移后 attachment.storage_driver 变为 target，天然脱离 source 集合。
- 非破坏性：默认保留本地源文件（仅切换记录指向云端）。
- 完整性：上传后比对 sha256，不符则计为失败并回删刚上传的对象，绝不改记录。
"""
from __future__ import annotations

import threading
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.attachment import Attachment
from app.models.cloud_storage import CloudStorageMigrationJob
from app.services import cloud_storage_config as cfg_svc
from app.storage.factory import build_storage, registered_drivers

# 同一时刻仅允许一个迁移任务在跑（单 worker 进程，避免并发写云端/DB 抖动）
_lock = threading.Lock()


class MigrationError(ValueError):
    """迁移创建/启动阶段的校验错误。"""


def count_by_driver(db: Session, driver: str) -> int:
    return db.scalar(
        select(func.count()).select_from(Attachment).where(Attachment.storage_driver == driver)
    ) or 0


def get_running_job(db: Session) -> CloudStorageMigrationJob | None:
    return db.scalar(
        select(CloudStorageMigrationJob)
        .where(CloudStorageMigrationJob.status == "running")
        .order_by(CloudStorageMigrationJob.id.desc())
        .limit(1)
    )


def get_latest_job(db: Session) -> CloudStorageMigrationJob | None:
    return db.scalar(
        select(CloudStorageMigrationJob).order_by(CloudStorageMigrationJob.id.desc()).limit(1)
    )


def _job_out(job: CloudStorageMigrationJob) -> dict:
    return {
        "id": job.id,
        "source": job.source,
        "target": job.target,
        "total": job.total,
        "done": job.done,
        "failed": job.failed,
        "status": job.status,
        "error": job.error,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def create_migration_job(db: Session, target: str, source: str = "local", user_id: int | None = None) -> CloudStorageMigrationJob:
    """校验并创建迁移任务；不执行。执行由 run_migration_async 触发。"""
    if source != "local":
        raise MigrationError("当前仅支持从 local 迁移到云（云→云/下载源未实现）")
    if target not in cfg_svc.CLOUD_PROVIDERS:
        raise MigrationError(f"目标 provider 非法：{target}")
    if target not in registered_drivers():
        raise MigrationError(f"目标驱动 {target} 未内置，无法迁移")
    if not cfg_svc.is_configured(db, target):
        raise MigrationError(f"目标 provider {target} 尚未配置凭据")

    # 临界区：查重 + 建单原子化，杜绝并发双起（同进程线程）
    with _lock:
        running = get_running_job(db)
        if running:
            raise MigrationError(f"已有迁移任务 #{running.id} 正在运行，请等待完成")
        total = count_by_driver(db, source)
        job = CloudStorageMigrationJob(source=source, target=target, total=total, status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)
    return job


def _migrate_one(db: Session, att: Attachment, target_storage, source_storage) -> tuple[bool, str | None]:
    """迁移单条：读源→传目标→校验 sha→切记录。返回 (成功?, 错误信息)。"""
    try:
        src_path = source_storage.resolve_path(key=att.storage_key)
    except Exception as exc:  # noqa: BLE001
        return False, f"定位源文件失败: {exc}"
    if not src_path.exists():
        return False, f"源文件不存在: {att.storage_key}"
    try:
        with open(src_path, "rb") as fh:
            stored = target_storage.save(
                filename=att.original_filename,
                content_type=att.content_type,
                stream=fh,
                max_size=settings.FILE_MAX_UPLOAD_SIZE,
            )
    except Exception as exc:  # noqa: BLE001
        return False, f"上传失败: {exc}"
    # 完整性校验：sha256 必须与既有记录一致（同源同内容）
    if stored.sha256 != att.sha256:
        try:
            target_storage.delete(key=stored.key)
        except Exception:  # noqa: BLE001 - 回删失败不再影响判定
            pass
        return False, f"sha256 校验不符（记录 {att.sha256} vs 上传 {stored.sha256}）"
    att.storage_driver = stored.driver
    att.storage_key = stored.key
    return True, None


def run_migration(job_id: int) -> None:
    """在独立会话/线程中执行迁移任务；进度实时写库。"""
    db = SessionLocal()
    try:
        job = db.get(CloudStorageMigrationJob, job_id)
        if not job or job.status != "pending":
            return
        job.status = "running"
        job.started_at = datetime.now()
        db.commit()

        # 快照待迁移 id（避免失败项反复命中导致死循环）
        ids = list(db.scalars(
            select(Attachment.id).where(Attachment.storage_driver == job.source).order_by(Attachment.id)
        ).all())
        job.total = len(ids)
        db.commit()

        target_storage = build_storage(job.target, db=db)
        source_storage = build_storage(job.source, db=db)
        if target_storage.driver != job.target:
            job.status = "failed"
            job.error = f"目标驱动构造失败或降级为 {target_storage.driver}（凭据/依赖未就绪）"
            job.finished_at = datetime.now()
            db.commit()
            return

        done = failed = 0
        last_err: str | None = None
        for att_id in ids:
            att = db.get(Attachment, att_id)
            if not att or att.storage_driver != job.source:
                continue  # 已被迁移/删除，跳过
            ok, err = _migrate_one(db, att, target_storage, source_storage)
            if ok:
                done += 1
            else:
                failed += 1
                last_err = err
            job.done, job.failed = done, failed
            db.commit()  # 每条提交：进度即时可见，失败项不阻断整体

        job.status = "done" if (done > 0 or not ids) else "failed"
        if last_err and failed:
            job.error = f"{failed} 条失败，末条原因：{last_err}"
        job.finished_at = datetime.now()
        db.commit()
    except Exception as exc:  # noqa: BLE001 - 兜底，异常落库避免任务卡 running
        db.rollback()
        job = db.get(CloudStorageMigrationJob, job_id)
        if job:
            job.status = "failed"
            job.error = str(exc)[:500]
            job.finished_at = datetime.now()
            db.commit()
    finally:
        db.close()


def run_migration_async(job_id: int) -> None:
    """守护线程执行；本部署无 Celery worker，故用线程。"""
    t = threading.Thread(target=run_migration, args=(job_id,), daemon=True, name=f"cloud-migration-{job_id}")
    t.start()
