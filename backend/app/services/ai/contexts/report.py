from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.report_unit import count_draft_units, count_user_reported_units, sync_assignment_units
from app.crud.task_assignment import sum_user_reported_qty
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.services.report_mode_settings import get_default_report_mode, use_unit_report_mode


def _infer_unit_qty(result_type: str) -> tuple[int, int]:
    if result_type == "bad":
        return 0, 1
    return 1, 0


def build_report_assist_context(
    db: Session,
    tenant_id: int,
    *,
    task_id: int,
    user_id: int,
    result_type: str,
    remark: str,
    good_qty: int | None = None,
    bad_qty: int | None = None,
) -> dict:
    task = db.get(Task, task_id)
    if not task or task.tenant_id != tenant_id:
        return {}
    assign = db.scalar(
        select(TaskAssignment).where(
            TaskAssignment.tenant_id == tenant_id,
            TaskAssignment.task_id == task_id,
            TaskAssignment.user_id == user_id,
        )
    )
    assigned = int(assign.assigned_qty or 0) if assign else 0
    unit_mode = use_unit_report_mode(db, tenant_id)
    report_mode = get_default_report_mode(db, tenant_id)

    if unit_mode and assign:
        try:
            sync_assignment_units(db, assign)
            db.flush()
        except ValueError:
            pass
        reported = count_user_reported_units(db, tenant_id, task_id, user_id)
        remaining = count_draft_units(db, tenant_id, assign.id)
        if good_qty is None and bad_qty is None:
            good_qty, bad_qty = _infer_unit_qty(result_type)
    else:
        reported = sum_user_reported_qty(db, tenant_id, task_id, user_id)
        remaining = max(0, assigned - reported)

    return {
        "task_id": task_id,
        "task_code": task.task_code,
        "planned_qty": int(task.planned_qty or 0),
        "assigned_qty": assigned,
        "reported_qty": reported,
        "remaining_qty": remaining,
        "report_mode": report_mode,
        "use_unit_report": unit_mode,
        "result_type": result_type,
        "good_qty": good_qty,
        "bad_qty": bad_qty,
        "remark": (remark or "")[:500],
    }
