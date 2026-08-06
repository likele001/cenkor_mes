"""工资 / 计时 / 薪资导出 Celery 任务"""
import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO

from celery import shared_task
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.crud.attachment import create_attachment
from app.crud.salary_slip import ensure_salary_slip
from app.models.export_job import ExportJob
from app.models.process import Process
from app.models.process_price import ProcessPrice
from app.models.report import Report
from app.models.salary import SalaryItem
from app.models.sku import Sku
from app.models.task import Task
from app.models.user import User
from app.models.work_order import WorkOrder
from app.storage import get_storage as get_active_storage

logger = logging.getLogger(__name__)


def calculate_salary_items(month: str | None = None) -> dict:
    """批量计算计件工资：扫描当月已终审(qc_approved)的报工记录，生成 SalaryItem

    审核通过时 calc_and_create_salary() 已逐条生成，此函数用于：
    1. 补漏：因异步或异常遗漏的报工
    2. 批量重算：管理员手动触发
    """
    if not month:
        month = datetime.now().strftime("%Y-%m")

    db = SessionLocal()
    try:
        # 查找当月所有已终审的报工，排除已生成工资明细的
        reports = db.scalars(
            select(Report).where(
                Report.status == "qc_approved",
                Report.created_at >= f"{month}-01",
                Report.created_at < _next_month(month),
            )
        ).all()

        created = 0
        skipped = 0
        for report in reports:
            # 检查是否已存在
            existing = db.scalar(
                select(SalaryItem).where(SalaryItem.report_id == report.id)
            )
            if existing:
                skipped += 1
                continue

            task = db.get(Task, report.task_id)
            if not task:
                skipped += 1
                continue
            wo = db.get(WorkOrder, task.work_order_id)
            if not wo:
                skipped += 1
                continue

            price = db.scalar(
                select(ProcessPrice).where(
                    ProcessPrice.sku_id == wo.sku_id,
                    ProcessPrice.process_id == task.process_id,
                    ProcessPrice.is_active.is_(True),
                )
            )
            if not price:
                logger.warning(
                    "报工 %s 缺少工价配置(sku=%s, process=%s)，跳过",
                    report.id, wo.sku_id, task.process_id,
                )
                skipped += 1
                continue

            unit_price = Decimal(str(price.unit_price))
            amount = Decimal(str(report.good_qty)) * unit_price

            item = SalaryItem(
                report_id=report.id,
                report_unit_id=None,
                user_id=report.report_user_id,
                sku_id=wo.sku_id,
                process_id=task.process_id,
                unit_price=unit_price,
                good_qty=report.good_qty,
                amount=amount,
                month=month,
            )
            db.add(item)
            created += 1

        db.commit()
        return {
            "ok": True,
            "month": month,
            "created": created,
            "skipped": skipped,
            "total_reports": len(reports),
        }
    except Exception as e:
        db.rollback()
        logger.error("计件工资计算失败: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def generate_salary_slips(month: str | None = None) -> dict:
    """批量生成工资条：汇总当月所有工资明细生成 SalarySlip

    按员工汇总计件工资 + 计时工资 + 奖金/扣款 = 实发工资
    """
    if not month:
        month = datetime.now().strftime("%Y-%m")

    db = SessionLocal()
    try:
        # 查找当月有工资明细的员工
        user_ids = set()
        for row in db.execute(
            select(SalaryItem.user_id).where(
                SalaryItem.month == month,
            ).distinct()
        ):
            user_ids.add(row[0])

        # 也包含有计时/考勤的员工
        from app.models.salary_allowance import SalaryAllowance
        for row in db.execute(
            select(SalaryAllowance.user_id).where(
                SalaryAllowance.month == month,
            ).distinct()
        ):
            user_ids.add(row[0])

        if not user_ids:
            return {"ok": True, "month": month, "slips_updated": 0, "msg": "当月无工资数据"}

        updated = 0
        for uid in sorted(user_ids):
            ensure_salary_slip(db, user_id=uid, month=month)
            updated += 1

        db.commit()
        return {"ok": True, "month": month, "slips_updated": updated}
    except Exception as e:
        db.rollback()
        logger.error("工资条生成失败: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def _next_month(month: str) -> str:
    """返回 YYYY-MM 的下个月第一天"""
    y, m = month.split("-")
    y, m = int(y), int(m)
    if m == 12:
        return f"{y + 1}-01-01"
    return f"{y}-{m + 1:02d}-01"


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
    """每月初汇总上月的工资条（含计件 + 计时 + 奖扣款）"""
    from app.crud.salary_slip import ensure_salary_slip

    db = SessionLocal()
    try:
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month = (first_of_month - timedelta(days=1)).strftime("%Y-%m")

        # 收集所有当月有工资数据的员工（计件 + 计时 + 奖扣款）
        user_ids = set()
        for row in db.execute(
            select(SalaryItem.user_id).where(SalaryItem.month == last_month).distinct()
        ):
            user_ids.add(row[0])

        from app.models.salary_allowance import SalaryAllowance
        for row in db.execute(
            select(SalaryAllowance.user_id).where(SalaryAllowance.month == last_month).distinct()
        ):
            user_ids.add(row[0])

        # 也包含 hourly/mixed 但可能无数据的员工
        for row in db.execute(
            select(User.id).where(
                User.is_active.is_(True),
                User.salary_type.in_(["hourly", "mixed"]),
            )
        ):
            user_ids.add(row[0])

        total = 0
        for uid in sorted(user_ids):
            ensure_salary_slip(db, user_id=uid, month=last_month)
            total += 1
        db.commit()
        return {"ok": True, "month": last_month, "slips_updated": total}
    except Exception:
        db.rollback()
        return {"ok": False, "error": "summary failed"}
    finally:
        db.close()
