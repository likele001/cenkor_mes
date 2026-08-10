"""生产自动化编排服务"""

from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.automation_log import create_automation_log
from app.crud.notification import notify_users_with_permission
from app.crud.order import get_order_by_id, order_has_work_orders
from app.crud.production_calendar import get_calendar_day
from app.crud.production_plan import (
    create_plan,
    get_plan_by_id,
    get_plan_with_order_info,
    release_plan,
    update_plan,
)
from app.crud.tenant_setting import get_setting
from app.models.production_plan import ProductionPlan
from app.schemas.production_plan import AutoDispatchIn
from app.services.plan_auto_dispatch import execute_auto_dispatch
from app.services.plan_readiness import build_plan_readiness
from app.services.planning_optimizer import optimize_plan_schedule
from app.services.production_automation_settings import get_automation_settings


def log_automation(
    db: Session,
    *,
    tenant_id: int,
    trigger: str,
    action: str,
    status: str,
    biz_type: str | None = None,
    biz_id: int | None = None,
    message: str | None = None,
    detail: dict | list | None = None,
    created_by: int | None = None,
):
    return create_automation_log(
        db,
                trigger=trigger,
        action=action,
        status=status,
        biz_type=biz_type,
        biz_id=biz_id,
        message=message,
        detail=detail,
        created_by=created_by,
    )


def precheck_order_for_automation(
    db: Session,
    tenant_id: int,
    order_id: int,
    *,
    allow_shortage: bool = False,
) -> dict:
    order = get_order_by_id(db, order_id, with_items=False)
    if not order:
        return {"ok": False, "checks": [{"level": "error", "message": "订单不存在"}]}
    checks: list[dict] = []
    if order.status != "confirmed":
        checks.append({"level": "error", "message": f"订单状态为 {order.status}，需先审核通过"})
    if order_has_work_orders(db, order_id):
        checks.append({"level": "warn", "message": "订单已下发投产，无需重复自动化"})
    try:
        readiness = build_plan_readiness(db, order_id=order_id)
    except ValueError as e:
        checks.append({"level": "error", "message": str(e)})
        readiness = None
    if readiness:
        if readiness["process"]["missing_route_count"]:
            checks.append({"level": "error", "message": readiness["blockers"] and readiness["blockers"][0] or "工艺路线缺失"})
        if readiness["process"]["missing_price_count"]:
            checks.append({"level": "error", "message": "型号×工序工价不完整"})
        if readiness["kitting"]["missing_bom_count"]:
            checks.append({"level": "error", "message": "BOM 未配置"})
        if readiness["kitting"]["shortage_count"] and not allow_shortage:
            checks.append({"level": "error", "message": f"缺料 {readiness['kitting']['shortage_count']} 项，需允许缺料或补货"})
        elif readiness["kitting"]["shortage_count"]:
            checks.append({"level": "warn", "message": f"缺料 {readiness['kitting']['shortage_count']} 项，已允许缺料"})
    ok = not any(c["level"] == "error" for c in checks)
    return {"ok": ok, "checks": checks, "readiness": readiness}


def precheck_plan_for_automation(db: Session, tenant_id: int, plan_id: int) -> dict:
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        return {"ok": False, "checks": [{"level": "error", "message": "计划不存在"}]}
    checks: list[dict] = []
    if plan.status not in ("planned", "in_progress"):
        checks.append({"level": "warn", "message": f"计划状态 {plan.status}"})
    return {"ok": True, "checks": checks, "plan_status": plan.status}


def _get_workdays_setting(db: Session, tenant_id: int) -> list[int]:
    it = get_setting(db, "plan.calendar.workdays")
    if not it or not it.value:
        return [1, 2, 3, 4, 5, 6]
    try:
        v = json.loads(it.value)
        if isinstance(v, list):
            out = [int(x) for x in v if 1 <= int(x) <= 7]
            return out or [1, 2, 3, 4, 5, 6]
    except Exception:
        pass
    return [1, 2, 3, 4, 5, 6]


def _is_workday_db(db: Session, tenant_id: int, d: date, workdays: list[int]) -> bool:
    it = get_calendar_day(db, day=d)
    if it is not None:
        return bool(it.is_workday)
    return int(d.isoweekday()) in workdays


def _normalize_to_workday(db: Session, tenant_id: int, d: date, *, direction: int, workdays: list[int]) -> date:
    cur = d
    for _ in range(400):
        if _is_workday_db(db, tenant_id, cur, workdays):
            return cur
        cur = cur + timedelta(days=direction)
    return d


def _shift_workdays(db: Session, tenant_id: int, d: date, delta: int, workdays: list[int]) -> date:
    if delta == 0:
        return d
    step = 1 if delta > 0 else -1
    remain = abs(int(delta))
    cur = d
    while remain > 0:
        cur = cur + timedelta(days=step)
        cur = _normalize_to_workday(db, tenant_id, cur, direction=step, workdays=workdays)
        remain -= 1
    return cur


def run_auto_schedule(db: Session, tenant_id: int, plan_id: int, mode: str = "backward") -> dict:
    row = get_plan_with_order_info(db, plan_id)
    if not row:
        raise ValueError("生产计划不存在")
    plan, _, _, _, _ = row
    order = get_order_by_id(db, plan.order_id, with_items=False)
    if not order:
        raise ValueError("订单不存在")
    if mode not in ("backward", "forward"):
        raise ValueError("mode 参数错误")

    workdays = _get_workdays_setting(db, tenant_id)
    start = plan.start_date
    end = plan.end_date
    work_days = plan.work_days
    if work_days is None or work_days <= 0:
        if start and end:
            work_days = (end - start).days + 1
        else:
            work_days = 1

    if mode == "backward":
        if not end:
            end = order.due_date
        if not end:
            start = date.today()
            start = _normalize_to_workday(db, tenant_id, start, direction=1, workdays=workdays)
            end = _shift_workdays(db, tenant_id, start, int(work_days) - 1, workdays)
            update_plan(db, plan=plan, start_date=start, end_date=end, work_days=int(work_days))
            return {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "work_days": int(work_days),
                "mode": "forward",
                "note": "订单未设置交期，已从今日正排",
            }
        end = _normalize_to_workday(db, tenant_id, end, direction=-1, workdays=workdays)
        start = _shift_workdays(db, tenant_id, end, -(int(work_days) - 1), workdays)
    else:
        if not start:
            raise ValueError("缺少开始日期，无法正排")
        start = _normalize_to_workday(db, tenant_id, start, direction=1, workdays=workdays)
        end = _shift_workdays(db, tenant_id, start, int(work_days) - 1, workdays)

    update_plan(db, plan=plan, start_date=start, end_date=end, work_days=int(work_days))
    return {"start_date": start.isoformat(), "end_date": end.isoformat(), "work_days": int(work_days), "mode": mode}


def apply_optimizer_dates(db: Session, tenant_id: int, plan_id: int) -> dict:
    opt = optimize_plan_schedule(db, plan_id)
    if not opt.get("ok"):
        raise ValueError(opt.get("error") or "排产优化失败")
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise ValueError("生产计划不存在")
    sd = date.fromisoformat(str(opt["suggest_start_date"])[:10])
    ed = date.fromisoformat(str(opt["suggest_end_date"])[:10])
    wd = int(opt.get("suggest_work_days") or 1)
    update_plan(db, plan=plan, start_date=sd, end_date=ed, work_days=wd)
    return {"schedule": opt, "start_date": sd.isoformat(), "end_date": ed.isoformat()}


def run_auto_release(db: Session, tenant_id: int, plan_id: int, user_id: int, allow_shortage: bool) -> dict:
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise ValueError("生产计划不存在")
    return release_plan(
    db,
        plan=plan,
        releaser_user_id=user_id,
        allow_shortage=allow_shortage,
    )


def run_auto_dispatch(
    db: Session,
    tenant_id: int,
    plan_id: int,
    user_id: int,
    *,
    auto_release: bool,
    allow_shortage: bool,
    unassigned_only: bool = True,
) -> dict:
    payload = AutoDispatchIn(
        auto_release=auto_release,
        allow_shortage=allow_shortage,
        unassigned_only=unassigned_only,
    )
    return execute_auto_dispatch(db, tenant_id=tenant_id, plan_id=plan_id, user_id=user_id, payload=payload)


def run_schedule_pipeline(
    db: Session,
    tenant_id: int,
    plan_id: int,
    user_id: int,
    *,
    engine: str = "ortools",
    auto_release: bool = False,
    auto_dispatch: bool = False,
    allow_shortage: bool = False,
    trigger: str = "plan_saved",
) -> dict:
    settings = get_automation_settings(db, tenant_id)
    if not settings.get("enabled"):
        log_automation(
            db,
            tenant_id=tenant_id,
            trigger=trigger,
            action="pipeline",
            status="skipped",
            biz_type="plan",
            biz_id=plan_id,
            message="自动化总开关未启用",
            created_by=user_id,
        )
        return {"skipped": True, "reason": "disabled"}

    result: dict = {"steps": []}
    try:
        if engine == "ortools":
            sched = apply_optimizer_dates(db, tenant_id, plan_id)
        else:
            sched = run_auto_schedule(db, tenant_id, plan_id, mode="backward")
        result["schedule"] = sched
        result["steps"].append("schedule")
        db.flush()

        release_info = None
        dispatch_info = None
        if auto_release or auto_dispatch:
            release_info = run_auto_release(db, tenant_id, plan_id, user_id, allow_shortage)
            result["release"] = release_info
            result["steps"].append("release")
            db.flush()

        if auto_dispatch:
            dispatch_info = run_auto_dispatch(
                db,
                tenant_id,
                plan_id,
                user_id,
                auto_release=False,
                allow_shortage=allow_shortage,
            )
            result["dispatch"] = dispatch_info
            result["steps"].append("dispatch")

        log_automation(
            db,
            tenant_id=tenant_id,
            trigger=trigger,
            action="pipeline",
            status="success",
            biz_type="plan",
            biz_id=plan_id,
            message="自动化流水线完成",
            detail=result,
            created_by=user_id,
        )
        return result
    except ValueError as e:
        log_automation(
            db,
            tenant_id=tenant_id,
            trigger=trigger,
            action="pipeline",
            status="failed",
            biz_type="plan",
            biz_id=plan_id,
            message=str(e),
            detail=result,
            created_by=user_id,
        )
        notify_users_with_permission(
            db,
                        permission_code="plan.manage",
            title="生产自动化失败",
            content=str(e)[:500],
            level="warning",
            biz_type="automation",
            biz_id=plan_id,
        )
        try:
            from app.services.feishu.notify import emit_feishu_event

            emit_feishu_event(
                db,
                "plan.automation_failed",
                title="生产自动化失败",
                content=str(e)[:500],
                level="warning",
                biz_type="automation",
                biz_id=plan_id,
            )
        except Exception:
            pass
        raise


def auto_create_plan_for_order(
    db: Session,
    tenant_id: int,
    order_id: int,
    user_id: int,
    *,
    start_offset_days: int = 0,
    run_pipeline: bool = False,
) -> ProductionPlan | None:
    settings = get_automation_settings(db, tenant_id)
    if not settings.get("enabled"):
        return None

    pre = precheck_order_for_automation(
        db,
        tenant_id,
        order_id,
        allow_shortage=bool(settings.get("on_plan_saved", {}).get("allow_shortage")),
    )
    if not pre["ok"]:
        log_automation(
            db,
            tenant_id=tenant_id,
            trigger="order_confirm",
            action="create_plan",
            status="failed",
            biz_type="order",
            biz_id=order_id,
            message="; ".join(c["message"] for c in pre["checks"] if c["level"] == "error")[:500],
            detail=pre,
            created_by=user_id,
        )
        notify_users_with_permission(
            db,
                        permission_code="plan.manage",
            title="订单确认后自动建计划失败",
            content=pre["checks"][0]["message"] if pre["checks"] else "检查未通过",
            level="warning",
            biz_type="order",
            biz_id=order_id,
        )
        try:
            from app.services.feishu.notify import emit_feishu_event

            emit_feishu_event(
                db,
                "plan.automation_failed",
                title="订单确认后自动建计划失败",
                content=pre["checks"][0]["message"] if pre["checks"] else "检查未通过",
                level="warning",
                biz_type="order",
                biz_id=order_id,
            )
        except Exception:
            pass
        return None

    existing = db.scalar(
        select(ProductionPlan).where(
            ProductionPlan.order_id == order_id,
            ProductionPlan.status == "planned",
        )
    )
    if existing:
        plan = existing
    else:
        from app.services.code_generator import BizType, resolve_code
        from app.crud.production_plan import get_plan_by_code

        order = get_order_by_id(db, order_id, with_items=False)
        plan_code = resolve_code(
            db,
            biz_type=BizType.PRODUCTION_PLAN,
            code=None,
            exists=lambda c: get_plan_by_code(db, c) is not None,
            duplicate_msg="计划编号已存在",
        )
        start_date = None
        end_date = order.due_date if order else None
        if end_date and start_offset_days:
            end_date = end_date  # keep due as end; offset applied in pipeline
        plan = create_plan(
    db,
            order_id=order_id,
            code=plan_code,
            status="planned",
            start_date=start_date,
            end_date=end_date,
            work_days=None,
            remark="自动化创建",
            created_by=user_id,
        )
        log_automation(
            db,
            tenant_id=tenant_id,
            trigger="order_confirm",
            action="create_plan",
            status="success",
            biz_type="plan",
            biz_id=plan.id,
            message=f"已创建计划 {plan.code}",
            created_by=user_id,
        )

    if run_pipeline:
        opts = settings.get("on_plan_saved") or {}
        try:
            run_schedule_pipeline(
                db,
                tenant_id,
                plan.id,
                user_id,
                engine=str(opts.get("engine") or "ortools"),
                auto_release=bool(opts.get("auto_release")),
                auto_dispatch=bool(opts.get("auto_dispatch")),
                allow_shortage=bool(opts.get("allow_shortage")),
                trigger="order_confirm",
            )
        except ValueError:
            # 流水线失败已记日志并通知；订单确认与计划创建仍应成功
            pass
    return plan


def enqueue_plan_pipeline(tenant_id: int, plan_id: int, user_id: int, trigger: str = "plan_saved") -> None:
    from app.celery_app import celery

    celery.send_task(
        "production.automation.pipeline",
        args=[int(tenant_id), int(plan_id), int(user_id), trigger],
    )


def maybe_trigger_plan_automation(db: Session, tenant_id: int, plan_id: int, user_id: int, trigger: str = "plan_saved") -> bool:
    settings = get_automation_settings(db, tenant_id)
    if not settings.get("enabled"):
        return False
    opts = settings.get("on_plan_saved") or {}
    if not opts.get("run_schedule"):
        return False
    enqueue_plan_pipeline(tenant_id, plan_id, user_id, trigger)
    return True
