from datetime import date, datetime
from io import BytesIO
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from app.celery_app import celery
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.export_job import create_export_job, get_export_job_by_id, list_export_jobs
from app.tasks._sync_excel import make_excel_response
from app.crud.notification import create_notification
from app.crud.salary_item import (
    generate_time_salary_items_for_user as _generate_time_items,
    get_hourly_summary as _hourly_summary,
    list_hourly_items as _list_hourly_items,
)
from app.crud.salary_ledger import list_hourly_ledger, list_salary_ledger
from app.crud.salary_slip import ensure_salary_slip, list_salary_slips, reset_salary_slip_confirm
from app.models.export_job import ExportJob
from app.models.salary import SalaryItem
from app.models.salary_allowance import SalaryAllowance
from app.models.user import User


router = APIRouter(dependencies=[Depends(require_permissions(["salary.manage"]))])


def _month_default(month: str | None) -> str:
    return month or datetime.now().strftime("%Y-%m")


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


@router.get("/salary/ledger")
def salary_ledger_api(
    month: str | None = Query(default=None, max_length=7),
    user_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None, description="submitted/leader_approved/qc_approved/rejected"),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = list_salary_ledger(db, month=month,
        user_id=user_id,
        status=status,
        keyword=keyword,
        offset=offset,
        limit=limit,
    )
    return ok({"items": items, "total": total})


@router.get("/salary/export")
def export_salary_api(
    month: str | None = Query(default=None, max_length=7),
    user_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    month = _month_default(month)
    rows, _ = list_salary_ledger(db, month=month,
        user_id=user_id,
        status=status,
        keyword=keyword,
        offset=0,
        limit=50000,
    )

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "工资明细"
    ws.append(
        [
            "ID",
            "员工姓名",
            "订单号",
            "产品名称",
            "型号名称",
            "工序名称",
            "报工数量",
            "单价",
            "计件工资",
            "状态",
            "报工时间",
            "月份",
            "来源",
        ]
    )
    for r in rows:
        emp = r.get("user_full_name") or r.get("username") or r.get("user_id")
        qty = f"第{r['unit_seq']}件" if r.get("unit_seq") else r.get("reported_qty")
        reported_at = r.get("reported_at")
        if reported_at and hasattr(reported_at, "strftime"):
            reported_at = reported_at.strftime("%Y-%m-%d %H:%M:%S")
        ws.append(
            [
                r.get("salary_id") or r.get("id"),
                emp,
                r.get("order_code") or "",
                r.get("product_name") or "",
                r.get("sku_name") or "",
                r.get("process_name") or "",
                qty,
                float(r.get("unit_price") or 0),
                float(r.get("amount") or 0),
                r.get("status_label") or "",
                reported_at or "",
                r.get("month") or "",
                "件次" if r.get("source") == "unit" else "批量",
            ]
        )

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = f"salary_detail_{month}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/salary/export-jobs")
def create_salary_export_job_api(
    month: str | None = Query(default=None, max_length=7),
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    month = _month_default(month)
    job = create_export_job(
        db,
        job_type="salary_excel",
        created_by=user.id,
        params={"month": month, "user_id": user_id},
    )
    res = celery.send_task("salary.export_excel", args=[job.id])
    job.celery_task_id = res.id
    db.commit()
    db.refresh(job)
    return ok(_job_out(job))


@router.get("/salary/export-jobs/{job_id}")
def get_salary_export_job_api(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_export_job_by_id(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=400, detail="导出任务不存在")
    return ok(_job_out(job))


@router.get("/salary/export-jobs")
def list_salary_export_jobs_api(
    status: str | None = Query(default=None, max_length=16),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_export_jobs(
        db,
        job_type="salary_excel",
        status=status,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_job_out(x) for x in items]})


@router.get("/salary/slips")
def list_salary_slips_api(
    month: str | None = Query(default=None, max_length=7),
    user_id: int | None = Query(default=None, ge=1),
    signed: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    month = _month_default(month)

    user_ids = set(
        x[0]
        for x in db.execute(
            select(distinct(SalaryItem.user_id)).where(SalaryItem.month == month)
        ).all()
    )
    user_ids.update(
        x[0]
        for x in db.execute(
            select(distinct(SalaryAllowance.user_id)).where(SalaryAllowance.month == month
            )
        ).all()
    )
    for uid in user_ids:
        ensure_salary_slip(db, user_id=uid, month=month)
    db.flush()
    db.commit()

    items = list_salary_slips(
        db,
        month=month,
        user_id=user_id,
        signed=signed,
        offset=offset,
        limit=limit,
    )
    return ok(
        {
            "items": [
                {
                    "id": slip.id,
                    "user_id": slip.user_id,
                    "user_name": u.full_name,
                    "month": slip.month,
                    "total_qty": slip.total_qty,
                    "item_amount": float(slip.item_amount),
                    "hourly_amount": float(slip.hourly_amount),
                    "hourly_hours": float(slip.hourly_hours),
                    "bonus_amount": float(slip.bonus_amount),
                    "deduction_amount": float(slip.deduction_amount),
                    "net_amount": float(slip.net_amount),
                    "signature_attachment_id": slip.signature_attachment_id,
                    "signed_at": slip.signed_at,
                    "is_signed": slip.signed_at is not None,
                    "confirm_status": slip.confirm_status,
                    "reject_reason": slip.reject_reason,
                    "rejected_at": slip.rejected_at,
                }
                for slip, u in items
            ]
        }
    )


@router.get("/salary/slips/export")
def export_salary_slips_api(
    month: str | None = Query(default=None, max_length=7),
    signed: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.crud.salary_slip import list_salary_slips as _list_slips

    month = _month_default(month)
    items = _list_slips(db, month=month, signed=signed, offset=0, limit=999999)
    rows = []
    for slip, u in items:
        rows.append([
            u.full_name if u else "",
            slip.month,
            float(slip.net_amount),
            slip.confirm_status,
            str(slip.created_at) if slip.created_at else "",
        ])
    return make_excel_response(
        headers=["员工姓名", "月份", "实发金额", "状态", "创建时间"],
        rows=rows,
        filename=f"salary_slips_{month}.xlsx",
        sheet_name="工资条",
    )


@router.post("/salary/slips/{slip_id}/reset-confirm")
def reset_salary_slip_confirm_api(
    slip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        slip = reset_salary_slip_confirm(db, slip_id=slip_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    create_notification(
        db,
        user_id=slip.user_id,
        title="工资条需要重新确认",
        content=f"{slip.month} 工资条已被管理员重置，请重新签名确认",
        level="warning",
        biz_type="salary_slip",
        biz_id=slip.id,
        feishu_event="salary.slip_reset",
    )
    db.commit()
    return ok({"id": slip.id, "confirm_status": slip.confirm_status})


@router.post("/salary/slips/remind")
def remind_unsigned_salary_slips_api(
    month: str = Query(min_length=7, max_length=7, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """批量催签：向所有未签名且未拒签的员工发送提醒通知"""
    from app.crud.salary_slip import list_salary_slips
    items = list_salary_slips(db, month=month, signed=False)
    sent = 0
    for slip, emp in items:
        if slip.confirm_status == "rejected":
            continue
        create_notification(
            db,
            user_id=slip.user_id,
            title=f"{month} 工资条待确认",
            content=f"请尽快确认 {month} 工资条，如有疑问请联系管理员",
            level="info",
            biz_type="salary_slip",
            biz_id=slip.id,
            feishu_event="salary.slip_remind",
        )
        sent += 1
    db.commit()
    return ok({"month": month, "sent": sent, "skipped": len(items) - sent})


# ── 计时工资 ──


@router.get("/salary/hourly-items")
def list_hourly_items_api(
    month: str | None = Query(default=None, max_length=7),
    user_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """计时工资明细（按日）"""
    items, total = _list_hourly_items(
        db, month=month, user_id=user_id, offset=offset, limit=limit
    )
    result = []
    for s in items:
        u = s.user
        result.append({
            "id": s.id,
            "user_id": s.user_id,
            "user_name": u.full_name if u else None,
            "item_type": s.item_type,
            "work_date": s.work_date.isoformat() if s.work_date else None,
            "work_hours": float(s.work_hours) if s.work_hours else 0,
            "hourly_rate": float(s.unit_price),
            "amount": float(s.amount),
            "month": s.month,
            "is_absent": s.item_type == "absent",
        })
    return ok({"items": result, "total": total})


@router.post("/salary/generate-time-items")
def generate_time_items_api(
    date_from: str = Query(..., description="开始日期 YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="结束日期 YYYY-MM-DD，默认同 date_from"),
    user_id: int | None = Query(default=None, ge=1, description="员工 ID，不传则全部 hourly/mixed 员工"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """手动触发计时工资生成"""
    try:
        d_from = date.fromisoformat(date_from)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from 格式错误，需 YYYY-MM-DD")
    d_to = date.fromisoformat(date_to) if date_to else d_from

    if user_id:
        items = _generate_time_items(db, user_id=user_id, date_from=d_from, date_to=d_to)
    else:
        from app.models.user import User as UserModel
        from sqlalchemy import select as _select

        users = db.scalars(
            _select(UserModel).where(UserModel.is_active.is_(True),
                UserModel.salary_type.in_(["hourly", "mixed"]),
            )
        ).all()
        items = []
        for u in users:
            items.extend(_generate_time_items(db, user_id=u.id, date_from=d_from, date_to=d_to))
    db.commit()
    return ok({"generated": len(items), "date_from": date_from, "date_to": d_to.isoformat()})


@router.get("/salary/hourly-summary")
def hourly_summary_api(
    month: str | None = Query(default=None, max_length=7),
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """计时工资汇总"""
    data = _hourly_summary(db, month=month, user_id=user_id)
    return ok(data)


@router.get("/salary/hourly-ledger")
def hourly_ledger_api(
    month: str | None = Query(default=None, max_length=7),
    user_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """计时工资台账"""
    items, total = list_hourly_ledger(
        db, month=month, user_id=user_id, offset=offset, limit=limit
    )
    return ok({"items": items, "total": total})
