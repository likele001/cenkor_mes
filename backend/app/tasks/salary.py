"""工资 / 计时 / 薪资导出 Celery 任务"""
import json
import logging
from datetime import date, datetime, timedelta, timezone
from io import BytesIO

from celery import shared_task
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.crud.attachment import create_attachment
from app.models.export_job import ExportJob
from app.models.process import Process
from app.models.salary import SalaryItem
from app.models.sku import Sku
from app.models.user import User
from app.storage import get_storage as get_active_storage

logger = logging.getLogger(__name__)


def calculate_salary_items(month: str | None = None) -> dict:
    return {"ok": True, "msg": "stub"}


def generate_salary_slips(month: str | None = None) -> dict:
    return {"ok": True, "msg": "stub"}


@shared_task(name="salary.export_excel")
def export_salary_excel(job_id: int) -> dict:
    """工资明细 Excel 导出 — 需要精细控制状态机，不使用 @db_task"""
    db = SessionLocal()
    try:
        job = db.scalar(select(ExportJob).where(ExportJob.id == job_id))
        if not job:
            return {"ok": False, "msg": "job_not_found"}
        if job.status in ("running", "success"):
            return {"ok": True, "status": job.status, "job_id": int(job.id)}

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.error_msg = None
        db.commit()

        params = {}
        if job.params_json:
            try:
                params = json.loads(job.params_json) or {}
            except Exception:
                params = {}
        month = str(params.get("month") or datetime.now().strftime("%Y-%m"))[:7]
        user_id = params.get("user_id")
        try:
            user_id = int(user_id) if user_id is not None else None
        except Exception:
            user_id = None

        stmt = (
            select(
                SalaryItem.id, SalaryItem.month, SalaryItem.user_id, User.full_name,
                SalaryItem.report_id, SalaryItem.sku_id, Sku.code.label("sku_code"),
                Sku.name.label("sku_name"), SalaryItem.process_id,
                Process.name.label("process_name"), SalaryItem.unit_price,
                SalaryItem.good_qty, SalaryItem.amount, SalaryItem.created_at,
            )
            .join(User, User.id == SalaryItem.user_id)
            .join(Sku, Sku.id == SalaryItem.sku_id)
            .join(Process, Process.id == SalaryItem.process_id)
            .where(SalaryItem.month == month)
            .order_by(SalaryItem.id.asc())
        )
        if user_id is not None and user_id > 0:
            stmt = stmt.where(SalaryItem.user_id == user_id)
        rows = db.execute(stmt).all()

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "工资明细"
        ws.append([
            "明细ID", "月份", "员工ID", "员工姓名", "报工ID", "型号ID",
            "型号编码", "型号名称", "工序ID", "工序名称", "单价", "合格数", "金额", "生成时间",
        ])
        for r in rows:
            ws.append([
                r.id, r.month, r.user_id, r.full_name, r.report_id, r.sku_id,
                r.sku_code, r.sku_name, r.process_id, r.process_name,
                float(r.unit_price), int(r.good_qty), float(r.amount),
                r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            ])

        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        filename = f"salary_detail_{month}{('_' + str(user_id)) if user_id else ''}.xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        storage = get_active_storage(db)
        stored = storage.save(
            filename=filename,
            content_type=content_type, stream=bio,
            max_size=settings.FILE_MAX_UPLOAD_SIZE,
        )
        if not job.created_by:
            raise ValueError("created_by 不能为空")
        att = create_attachment(
            db, uploader_id=int(job.created_by),
            storage_driver=stored.driver, storage_key=stored.key,
            original_filename=filename, content_type=content_type,
            size=int(stored.size), sha256=stored.sha256,
        )
        job.result_attachment_id = att.id
        job.status = "success"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"ok": True, "status": job.status, "job_id": int(job.id), "attachment_id": int(att.id)}
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            job = db.scalar(select(ExportJob).where(ExportJob.id == job_id))
            if job:
                job.status = "failed"
                job.error_msg = str(e)[:500]
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        return {"ok": False, "status": "failed", "job_id": int(job_id)}
    finally:
        db.close()


@shared_task(name="salary.daily_hourly_calc")
def daily_hourly_calc() -> dict:
    """每日凌晨计算前一天的计时工资"""
    from app.crud.salary_item import generate_all_time_salary_items

    db = SessionLocal()
    try:
        yesterday = date.today() - timedelta(days=1)
        n = generate_all_time_salary_items(db, target_date=yesterday)
        db.commit()
        return {"ok": True, "date": yesterday.isoformat(), "items_generated": n}
    except Exception:
        db.rollback()
        return {"ok": False, "error": "calculation failed"}
    finally:
        db.close()


@shared_task(name="salary.monthly_summary")
def monthly_salary_summary() -> dict:
    """每月初汇总上月的工资条（含计时）"""
    from app.crud.salary_slip import ensure_salary_slip

    db = SessionLocal()
    try:
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month = (first_of_month - timedelta(days=1)).strftime("%Y-%m")

        user_ids = [
            r[0]
            for r in db.execute(
                select(User.id).where(
                    User.is_active.is_(True),
                    User.salary_type.in_(["hourly", "mixed"]),
                )
            ).all()
        ]
        total = 0
        for uid in user_ids:
            ensure_salary_slip(db, user_id=uid, month=last_month)
            total += 1
        db.commit()
        return {"ok": True, "month": last_month, "slips_updated": total}
    except Exception:
        db.rollback()
        return {"ok": False, "error": "summary failed"}
    finally:
        db.close()
