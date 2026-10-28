# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""生产排程自动化 Celery 任务"""
from celery import shared_task


@shared_task(name="production.automation.pipeline")
def production_automation_pipeline(
    plan_id: int | None = None,
    user_id: int | None = None,
    trigger: str = "plan_saved",
) -> dict:
    from app.core.db import SessionLocal
    from app.services.production_automation import run_schedule_pipeline
    from app.services.production_automation_settings import get_automation_settings

    db = SessionLocal()
    try:
        if plan_id is None:
            # 定时任务无参调用（cron_jobs）：扫出已到开始日的待排产计划逐个跑流水线
            return _run_scheduled_sweep(db, trigger="cron")
        settings = get_automation_settings(db)
        opts = settings.get("on_plan_saved") or {}
        result = run_schedule_pipeline(
            db,
            int(plan_id),
            user_id,
            engine=str(opts.get("engine") or "ortools"),
            auto_release=bool(opts.get("auto_release")),
            auto_dispatch=bool(opts.get("auto_dispatch")),
            allow_shortage=bool(opts.get("allow_shortage")),
            trigger=trigger,
        )
        db.commit()
        return {"ok": True, "result": result}
    except ValueError as e:
        try:
            db.commit()
        except Exception:
            db.rollback()
        return {"ok": False, "error": str(e)}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)[:500]}
    finally:
        db.close()


def _run_scheduled_sweep(db, *, trigger: str = "cron", today=None) -> dict:
    """定时无参入口：扫出「计划中且已到计划开始日」的计划逐个执行自动化流水线。

    单计划失败（ValueError）不影响其它计划——流水线内部已记审计日志并通知；
    失败计划的日志随最终 commit 一并保留。操作人以计划创建人为准。
    """
    from datetime import date

    from sqlalchemy import select

    from app.models.production_plan import ProductionPlan
    from app.services.production_automation import run_schedule_pipeline
    from app.services.production_automation_settings import get_automation_settings

    settings = get_automation_settings(db)
    opts = settings.get("on_plan_saved") or {}
    plans = db.scalars(
        select(ProductionPlan).where(
            ProductionPlan.status == "planned",
            ProductionPlan.start_date <= (today or date.today()),
        )
    ).all()
    results: list[dict] = []
    for plan in plans:
        plan_user = int(plan.created_by) if plan.created_by else None
        try:
            res = run_schedule_pipeline(
                db,
                int(plan.id),
                plan_user,
                engine=str(opts.get("engine") or "ortools"),
                auto_release=bool(opts.get("auto_release")),
                auto_dispatch=bool(opts.get("auto_dispatch")),
                allow_shortage=bool(opts.get("allow_shortage")),
                trigger=trigger,
            )
            results.append({"plan_id": int(plan.id), "ok": True, "result": res})
        except ValueError as e:
            results.append({"plan_id": int(plan.id), "ok": False, "error": str(e)})
    db.commit()
    return {"ok": True, "swept": len(results), "results": results}
