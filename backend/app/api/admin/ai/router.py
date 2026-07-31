from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.models.user import User
from app.crud.ai_conversation import delete_conversation, list_conversations
from app.crud.ai_platform import list_ai_models
from app.schemas.ai import AiChatIn, AiGatewaySettingsIn, AiHelpIn, AiPromptSettingsIn, ScheduleApplyIn
from app.schemas.production_plan import AutoDispatchIn
from app.services.ai.alert_settings import get_alert_thresholds, save_alert_thresholds
from app.services.ai.alerts import list_recent_alerts, notify_pending_alerts, scan_tenant_alerts
from app.services.ai.causal_inference import analyze_yield_causes
from app.services.ai.client import AiCallError, AiNotConfiguredError
from app.services.ai.digital_twin import workshop_twin_snapshot
from app.services.ai.equipment_health import equipment_health_scores
from app.services.ai.gateway_settings import get_gateway_settings_admin, save_gateway_settings
from app.services.ai.pricing_ai import suggest_price_adjustments
from app.services.ai.prompt_settings import get_prompt_settings_admin, save_prompt_settings
from app.services.ai.rag_help import help_answer, reindex_docs, search_docs
from app.services.ai.stats import ai_usage_stats
from app.services.ai.scenes import audit_batch_summary, boss_qa, boss_qa_stream_chunks, plan_risk, plan_schedule, report_vision_audit
from app.services.ai.visual_quality import list_quality_genes
from app.services.planning_optimizer import optimize_plan_schedule
from app.services.ai.predict.equipment_predictor import train_equipment_model
from app.services.ai.predict.yield_predictor import detect_factory_anomalies, list_all_yield_predictions
from app.services.ai.feedback import submit_feedback, get_feedback_stats, list_recent_feedback
from app.services.ai.proactive import get_recommendations


router = APIRouter()


def _ai_error(e: Exception):
    if isinstance(e, AiNotConfiguredError):
        raise HTTPException(status_code=503, detail=str(e))
    if isinstance(e, AiCallError):
        raise HTTPException(status_code=502, detail=str(e))
    raise HTTPException(status_code=500, detail="AI 服务异常")


class AlertSettingsIn(BaseModel):
    pending_audit: int | None = Field(default=None, ge=1, le=10000)
    yield_drop_delta: float | None = Field(default=None, ge=0.01, le=0.5)
    pending_tasks: int | None = Field(default=None, ge=1, le=10000)
    unassigned_sample_min: int | None = Field(default=None, ge=1, le=100)


@router.post("/chat", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_chat_api(payload: AiChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        if payload.scene != "boss_qa":
            raise HTTPException(status_code=400, detail="暂仅支持 scene=boss_qa")
        data = boss_qa(
            db,
            user.tenant_id,
            user.id,
            payload.message,
            payload.conversation_id,
            model_code=payload.model_code,
            context_id=payload.context_id,
        )
        db.commit()
        return ok(data)
    except (AiNotConfiguredError, AiCallError) as e:
        db.rollback()
        _ai_error(e)


@router.post("/chat/stream", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_chat_stream_api(payload: AiChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    import json

    if payload.scene != "boss_qa":
        raise HTTPException(status_code=400, detail="暂仅支持 scene=boss_qa")

    def event_gen():
        try:
            for kind, data in boss_qa_stream_chunks(
                db,
                user.tenant_id,
                user.id,
                payload.message,
                payload.conversation_id,
                model_code=payload.model_code,
                context_id=payload.context_id,
            ):
                if kind == "delta":
                    yield f"event: delta\ndata: {json.dumps({'text': data}, ensure_ascii=False)}\n\n"
                elif kind == "done":
                    db.commit()
                    yield f"event: done\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except (AiNotConfiguredError, AiCallError) as e:
            db.rollback()
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
        except Exception:
            db.rollback()
            yield f"event: error\ndata: {json.dumps({'message': 'AI 服务异常'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/help", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_help_api(payload: AiHelpIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        data = help_answer(db, tenant_id=user.tenant_id, question=payload.question)
        return ok(data)
    except (AiNotConfiguredError, AiCallError) as e:
        _ai_error(e)


@router.get("/help/search", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_help_search_api(q: str = Query(min_length=1, max_length=200), user: User = Depends(get_current_user)):
    return ok({"items": search_docs(q)})


@router.post("/help/reindex", dependencies=[Depends(require_permissions(["ai.use", "setting.manage"]))])
def ai_help_reindex_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.ai.rag_indexer import force_reindex
    result = force_reindex(db)
    return ok(result)


@router.get("/gateway-settings", dependencies=[Depends(require_permissions(["ai.use", "setting.manage"]))])
def get_gateway_settings_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_gateway_settings_admin(db, user.tenant_id))


@router.put("/gateway-settings", dependencies=[Depends(require_permissions(["ai.use", "setting.manage"]))])
def save_gateway_settings_api(
    payload: AiGatewaySettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = save_gateway_settings(db, user.tenant_id, payload.model_dump(exclude_none=True))
    db.commit()
    return ok(data)


@router.post("/plan/{plan_id}/analyze", dependencies=[Depends(require_permissions(["ai.use", "plan.manage"]))])
def plan_analyze_api(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        data = plan_risk(db, user.tenant_id, user.id, plan_id)
        db.commit()
        return ok(data)
    except (AiNotConfiguredError, AiCallError) as e:
        db.rollback()
        _ai_error(e)


@router.post("/plan/{plan_id}/schedule-suggest", dependencies=[Depends(require_permissions(["ai.use", "plan.manage"]))])
def plan_schedule_suggest_api(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        data = plan_schedule(db, user.tenant_id, user.id, plan_id)
        db.commit()
        return ok(data)
    except (AiNotConfiguredError, AiCallError) as e:
        db.rollback()
        _ai_error(e)


@router.post("/plan/{plan_id}/schedule-optimize", dependencies=[Depends(require_permissions(["ai.use", "plan.manage"]))])
def plan_schedule_optimize_api(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = optimize_plan_schedule(db, user.tenant_id, plan_id)
    return ok(data)


@router.post("/plan/{plan_id}/schedule-apply", dependencies=[Depends(require_permissions(["ai.use", "plan.manage"]))])
def plan_schedule_apply_api(
    plan_id: int,
    payload: ScheduleApplyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """采纳建议：按交期排产 → 自动下发（可选）→ 自动派工。"""
    from datetime import date as date_cls

    from app.api.admin.production import plans as plans_module
    from app.crud.production_plan import get_plan_by_id, update_plan
    from app.services.production_automation_settings import get_automation_settings

    auto_release = payload.auto_release
    allow_shortage = payload.allow_shortage
    automation = get_automation_settings(db, user.tenant_id)
    if automation.get("enabled"):
        opts = automation.get("on_plan_saved") or {}
        if opts.get("auto_release"):
            auto_release = True
        if opts.get("allow_shortage"):
            allow_shortage = True

    mode = payload.mode if payload.mode in ("backward", "forward") else "backward"
    if payload.start_date and payload.end_date:
        plan = get_plan_by_id(db, tenant_id=user.tenant_id, plan_id=plan_id)
        if not plan:
            raise HTTPException(status_code=400, detail="生产计划不存在")
        try:
            sd = date_cls.fromisoformat(payload.start_date[:10])
            ed = date_cls.fromisoformat(payload.end_date[:10])
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")
        wd = payload.work_days
        update_plan(db, plan=plan, start_date=sd, end_date=ed, work_days=wd)
        db.commit()
        sched = {"start_date": sd.isoformat(), "end_date": ed.isoformat(), "source": "optimizer"}
    else:
        try:
            sched = plans_module.auto_schedule_api(plan_id=plan_id, mode=mode, db=db, user=user)
        except HTTPException:
            raise

    dispatch_payload = AutoDispatchIn(
        user_ids=payload.user_ids,
        unassigned_only=payload.unassigned_only,
        auto_release=auto_release,
        allow_shortage=allow_shortage,
    )
    try:
        disp = plans_module.auto_dispatch_api(plan_id=plan_id, payload=dispatch_payload, db=db, user=user)
    except HTTPException:
        raise

    return ok({"schedule": sched, "dispatch": disp})


@router.get("/alerts", dependencies=[Depends(require_permissions(["ai.alert.view"]))])
def list_alerts_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok({"items": list_recent_alerts(db, user.tenant_id)})


@router.post("/alerts/run", dependencies=[Depends(require_permissions(["ai.use"]))])
def run_alerts_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.production_automation_settings import get_automation_settings

    events = scan_tenant_alerts(db, user.tenant_id)
    alert_prefs = get_automation_settings(db, user.tenant_id).get("alerts") or {}
    n = notify_pending_alerts(db, user.tenant_id, alert_prefs=alert_prefs)
    db.commit()
    return ok({"events": len(events), "notified": n})


@router.get("/alert-settings", dependencies=[Depends(require_permissions(["ai.use", "setting.manage"]))])
def get_alert_settings_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_alert_thresholds(db, user.tenant_id))


@router.put("/alert-settings", dependencies=[Depends(require_permissions(["ai.use", "setting.manage"]))])
def save_alert_settings_api(
    payload: AlertSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = save_alert_thresholds(db, user.tenant_id, payload.model_dump(exclude_none=True))
    db.commit()
    return ok(data)


@router.post("/audit/summary", dependencies=[Depends(require_permissions(["ai.use", "report.audit"]))])
def audit_summary_api(
    status: str = Query(default="submitted"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        data = audit_batch_summary(db, user.tenant_id, user.id, status=status)
        db.commit()
        return ok(data)
    except (AiNotConfiguredError, AiCallError) as e:
        db.rollback()
        _ai_error(e)


@router.post("/report-units/{unit_id}/vision", dependencies=[Depends(require_permissions(["ai.use", "report.audit"]))])
def report_vision_api(unit_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        data = report_vision_audit(db, user.tenant_id, user.id, unit_id)
        return ok(data)
    except (AiNotConfiguredError, AiCallError) as e:
        _ai_error(e)


@router.get("/deep/overview", dependencies=[Depends(require_permissions(["ai.use"]))])
def deep_overview_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(
        {
            "causal": analyze_yield_causes(db, user.tenant_id),
            "quality_genes": list_quality_genes(db, user.tenant_id, limit=20),
            "pricing": suggest_price_adjustments(db, user.tenant_id),
            "digital_twin": workshop_twin_snapshot(db, user.tenant_id),
            "equipment_health": equipment_health_scores(db, user.tenant_id),
        }
    )


@router.get("/deep/causal", dependencies=[Depends(require_permissions(["ai.use"]))])
def deep_causal_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(analyze_yield_causes(db, user.tenant_id))


@router.get("/deep/quality-genes", dependencies=[Depends(require_permissions(["ai.use"]))])
def deep_quality_genes_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(list_quality_genes(db, user.tenant_id))


@router.get("/deep/pricing", dependencies=[Depends(require_permissions(["ai.use"]))])
def deep_pricing_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(suggest_price_adjustments(db, user.tenant_id))


@router.get("/deep/digital-twin", dependencies=[Depends(require_permissions(["ai.use"]))])
def deep_twin_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(workshop_twin_snapshot(db, user.tenant_id))


@router.get("/deep/equipment-health", dependencies=[Depends(require_permissions(["ai.use"]))])
def deep_equipment_health_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(equipment_health_scores(db, user.tenant_id))


@router.get("/stats", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_stats_api(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(ai_usage_stats(db, user.tenant_id, days=days))


@router.get("/models", dependencies=[Depends(require_permissions(["ai.use"]))])
def list_models_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = [m for m in list_ai_models(db) if m.is_active and not m.is_vision]
    return ok(
        {
            "items": [
                {"code": m.code, "display_name": m.display_name, "is_default": m.is_default, "model_id": m.model_id}
                for m in rows
            ]
        }
    )


@router.get("/prompt-settings", dependencies=[Depends(require_permissions(["ai.use", "setting.manage"]))])
def get_prompt_settings_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(get_prompt_settings_admin(db, user.tenant_id))


@router.put("/prompt-settings", dependencies=[Depends(require_permissions(["ai.use", "setting.manage"]))])
def save_prompt_settings_api(
    payload: AiPromptSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = save_prompt_settings(db, user.tenant_id, payload.prompt)
    db.commit()
    return ok(data)


@router.get("/conversations", dependencies=[Depends(require_permissions(["ai.use"]))])
def list_conversations_api(
    scene: str = Query(default="boss_qa"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = list_conversations(db, user.tenant_id, user.id, scene=scene, limit=limit)
    return ok(
        {
            "items": [
                {
                    "id": r.id,
                    "title": r.title,
                    "scene": r.scene,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]
        }
    )


@router.delete("/conversations/{conversation_id}", dependencies=[Depends(require_permissions(["ai.use"]))])
def delete_conversation_api(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not delete_conversation(db, user.tenant_id, conversation_id):
        raise HTTPException(status_code=404, detail="对话不存在")
    db.commit()
    return ok({"ok": True})


@router.get("/brief", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_brief_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.daily_brief import get_live_brief

    return ok(get_live_brief(db, user.tenant_id, user.id))


@router.get("/brief/latest", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_brief_latest_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.crud.notification import list_my_notifications

    rows = list_my_notifications(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        biz_type="daily_brief",
        limit=1,
    )
    if not rows:
        from app.services.daily_brief import get_live_brief

        return ok(get_live_brief(db, user.tenant_id, user.id))
    n = rows[0]
    return ok({"mode": "stored", "content": n.content, "title": n.title, "created_at": n.created_at})


@router.post("/deep/equipment/{equipment_id}/train", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_train_equipment_api(equipment_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    result = train_equipment_model(db, user.tenant_id, equipment_id)
    return ok(result)


@router.get("/deep/yield/anomalies", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_yield_anomalies_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return ok(detect_factory_anomalies(db, user.tenant_id))


@router.get("/deep/yield/predictions", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_yield_predictions_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return ok(list_all_yield_predictions(db, user.tenant_id))


@router.get("/deep/equipment-health-enhanced", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_equipment_health_enhanced_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from app.services.ai.predict.equipment_predictor import equipment_health_scores_enhanced as ehse
    return ok(ehse(db, user.tenant_id))


# === Phase 3: Feedback & Proactive Recommendations ===

@router.post("/feedback/submit", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_feedback_submit_api(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
    body: dict = {},
):
    """Submit user feedback on AI answer. Body: {query, answer, feedback_type ('thumb_up','thumb_down','corrected'), corrected_answer?}."""
    try:
        data = dict(body or {})
        return ok(submit_feedback(
            db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            query=data.get("query", "") or "",
            answer=data.get("answer"),
            feedback_type=data.get("feedback_type", "thumb_up"),
            corrected_answer=data.get("corrected_answer"),
            conversation_id=data.get("conversation_id"),
            message_id=data.get("message_id"),
        ))
    except Exception as e:
        return ok({"ok": False, "error": str(e)[:200]})


@router.get("/feedback/stats", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_feedback_stats_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return ok(get_feedback_stats(db, user.tenant_id))


@router.get("/feedback/recent", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_feedback_recent_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return ok(list_recent_feedback(db, user.tenant_id))


@router.get("/recommendations", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_recommendations_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return ok(get_recommendations(db, user.tenant_id))


# === Phase 4: Enhanced L3+ Modules ===

@router.get("/deep/twin-enhanced", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_twin_enhanced_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from app.services.ai.twin.enhanced_twin import workshop_twin_enhanced
    return ok(workshop_twin_enhanced(db, user.tenant_id))


@router.get("/deep/bottleneck", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_bottleneck_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from app.services.ai.twin.enhanced_twin import identify_bottleneck
    return ok(identify_bottleneck(db, user.tenant_id))


@router.get("/deep/causal-enhanced", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_causal_enhanced_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from app.services.ai.causal.enhanced_causal import analyze_yield_causes_enhanced
    return ok(analyze_yield_causes_enhanced(db, user.tenant_id))


@router.get("/deep/causal/correlation", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_causal_correlation_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from app.services.ai.causal.enhanced_causal import correlation_matrix
    return ok(correlation_matrix(db, user.tenant_id))


@router.get("/deep/quality-patterns", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_quality_patterns_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from app.services.ai.quality.enhanced_quality import extract_quality_patterns
    return ok(extract_quality_patterns(db, user.tenant_id))


@router.get("/deep/quality-dictionary", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_quality_dictionary_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from app.services.ai.quality.enhanced_quality import auto_defect_dictionary
    return ok(auto_defect_dictionary(db, user.tenant_id))


@router.get("/deep/pricing-enhanced", dependencies=[Depends(require_permissions(["ai.use"]))])
def ai_pricing_enhanced_api(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from app.services.ai.pricing.enhanced_pricing import suggest_prices_enhanced
    return ok(suggest_prices_enhanced(db, user.tenant_id))
