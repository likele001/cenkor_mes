"""生产排程自动化 Celery 任务"""
from celery import shared_task


@shared_task(name="production.automation.pipeline")
def production_automation_pipeline(plan_id: int, user_id: int, trigger: str = "plan_saved") -> dict:
    from app.core.db import SessionLocal
    from app.services.production_automation import run_schedule_pipeline
    from app.services.production_automation_settings import get_automation_settings

    db = SessionLocal()
    try:
        settings = get_automation_settings(db)
        opts = settings.get("on_plan_saved") or {}
        result = run_schedule_pipeline(
            db,
            plan_id,
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
