from datetime import date
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.celery_app import celery
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.export_job import create_export_job, list_export_jobs
from app.crud.report_stats import get_daily_trend, get_process_rank, get_production_summary, get_yield_summary
from app.models.export_job import ExportJob
from app.models.quality import DefectCode, InspectionRecord
from app.models.user import User

from app.api.admin.reports.purchase import router as purchase_router

router = APIRouter(dependencies=[Depends(require_permissions(["report.view"]))])
router.include_router(purchase_router)


def _job_out(x: ExportJob) -> dict:
    params = {}
    if x.params_json:
        try:
            params = json.loads(x.params_json) or {}
        except Exception:
            params = {}
    return {
        "id": x.id,
        "job_type": x.job_type,
        "status": x.status,
        "params": params,
        "result_attachment_id": x.result_attachment_id,
        "error_msg": x.error_msg,
        "created_by": x.created_by,
        "created_at": x.created_at,
        "started_at": x.started_at,
        "finished_at": x.finished_at,
    }


@router.get("/defect-pareto")
def defect_pareto_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """缺陷 Pareto 分析：按缺陷代码分组统计出现次数"""
    from datetime import datetime, timedelta
    from sqlalchemy import func, select

    today = date.today()
    d_from = date_from or (today - timedelta(days=30))
    d_to = date_to or today

    rows = db.execute(
        select(
            DefectCode.code,
            DefectCode.name,
            DefectCode.severity,
            func.count(InspectionRecord.id).label("cnt"),
        )
        .select_from(InspectionRecord)
        .join(DefectCode, DefectCode.id == InspectionRecord.defect_code_id)
        .where(
            InspectionRecord.result == "fail",
            InspectionRecord.defect_code_id.isnot(None),
            func.date(InspectionRecord.created_at) >= d_from,
            func.date(InspectionRecord.created_at) <= d_to,
        )
        .group_by(DefectCode.id, DefectCode.code, DefectCode.name, DefectCode.severity)
        .order_by(func.count(InspectionRecord.id).desc())
        .limit(limit)
    ).all()

    total = sum(int(r.cnt) for r in rows)
    cumulative = 0
    items = []
    for r in rows:
        cumulative += int(r.cnt)
        items.append({
            "defect_code": r.code,
            "defect_name": r.name,
            "severity": r.severity,
            "count": int(r.cnt),
            "pct": round(int(r.cnt) / total * 100, 1) if total else 0,
            "cumulative_pct": round(cumulative / total * 100, 1) if total else 0,
        })
    return ok({"items": items, "total": total})


@router.get("/production")
def production_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = get_production_summary(db, date_from=date_from, date_to=date_to)
    return ok(data)


@router.get("/yield")
def yield_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = get_yield_summary(db, date_from=date_from, date_to=date_to)
    return ok(data)


@router.get("/process-rank")
def process_rank_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = get_process_rank(db, date_from=date_from, date_to=date_to, limit=limit)
    return ok({"items": items})


@router.get("/daily-trend")
def daily_trend_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = get_daily_trend(db, date_from=date_from, date_to=date_to)
    return ok({"items": items})


# ── 导出 ──

@router.post("/export/production")
def export_production_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = create_export_job(
        db, job_type="report_production",
        created_by=user.id, params={"date_from": str(date_from) if date_from else None, "date_to": str(date_to) if date_to else None},
    )
    res = celery.send_task("report.production_excel", args=[job.id])
    job.celery_task_id = res.id
    db.commit()
    db.refresh(job)
    return ok(_job_out(job))


@router.post("/export/yield")
def export_yield_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = create_export_job(
        db, job_type="report_yield",
        created_by=user.id, params={"date_from": str(date_from) if date_from else None, "date_to": str(date_to) if date_to else None},
    )
    res = celery.send_task("report.yield_excel", args=[job.id])
    job.celery_task_id = res.id
    db.commit()
    db.refresh(job)
    return ok(_job_out(job))


@router.get("/export-jobs")
def export_jobs_api(
    job_type: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, max_length=16),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_export_jobs(
        db, job_type=job_type, status=status,
        offset=offset, limit=limit,
    )
    return ok({"items": [_job_out(x) for x in items]})
