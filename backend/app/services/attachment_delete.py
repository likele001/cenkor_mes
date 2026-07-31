"""附件引用检查与删除"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.export_job import ExportJob
from app.models.report import Report
from app.models.report_unit import ReportUnit, ReportUnitAudit
from app.models.salary_slip import SalarySlip


def _id_in_csv_column(col, attachment_id: int):
    aid = str(attachment_id)
    return or_(
        col == aid,
        col.like(f"{aid},%"),
        col.like(f"%,{aid},%"),
        col.like(f"%,{aid}"),
    )


def attachment_is_referenced(db: Session, *, attachment_id: int) -> bool:
    if db.scalar(
        select(ReportUnit.id).where(
            or_(
                _id_in_csv_column(ReportUnit.employee_attachment_ids, attachment_id),
                _id_in_csv_column(ReportUnit.qc_attachment_ids, attachment_id),
            ),
        ).limit(1)
    ):
        return True
    if db.scalar(
        select(ReportUnitAudit.id).where(
            _id_in_csv_column(ReportUnitAudit.attachment_ids, attachment_id),
        ).limit(1)
    ):
        return True
    if db.scalar(
        select(Report.id).where(
            _id_in_csv_column(Report.attachment_ids, attachment_id),
        ).limit(1)
    ):
        return True
    if db.scalar(
        select(ExportJob.id).where(
            ExportJob.result_attachment_id == attachment_id,
        ).limit(1)
    ):
        return True
    if db.scalar(
        select(SalarySlip.id).where(
            SalarySlip.signature_attachment_id == attachment_id,
        ).limit(1)
    ):
        return True
    return False


def delete_attachment_record(db: Session, att: Attachment) -> None:
    db.delete(att)
    db.flush()
