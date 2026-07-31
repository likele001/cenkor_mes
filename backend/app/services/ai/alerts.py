from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.dashboard import get_dashboard_summary
from app.crud.notification import notify_users_with_permission
from app.models.ai import AiAlertEvent
from app.models.order import Order
from app.models.report import Report
from app.models.tenant import Tenant
from app.models.task import Task
from app.models.work_order import WorkOrder
from app.crud.task_assignment import task_has_assignments
from app.services.ai.alert_settings import get_alert_thresholds
from app.services.ai.client import AiCallError, AiNotConfiguredError, chat_completion


def _already_notified(db: Session, tenant_id: int, dedupe_key: str, hours: int = 24) -> bool:
    since = datetime.utcnow() - timedelta(hours=hours)
    row = db.scalar(
        select(AiAlertEvent.id).where(
            AiAlertEvent.tenant_id == tenant_id,
            AiAlertEvent.dedupe_key == dedupe_key,
            AiAlertEvent.notified_at.isnot(None),
            AiAlertEvent.created_at >= since,
        )
    )
    return row is not None


def _narrative(db: Session, rule_code: str, facts: dict) -> str:
    try:
        reply, _, _ = chat_completion(
            db,
            messages=[
                {
                    "role": "system",
                    "content": "你是工厂预警助手。根据 JSON 事实写 2～4 句中文说明，不要编造数据。",
                },
                {"role": "user", "content": json.dumps({"rule": rule_code, "facts": facts}, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        return reply
    except (AiNotConfiguredError, AiCallError):
        return facts.get("fallback_summary") or str(facts)


def scan_tenant_alerts(db: Session, tenant_id: int, *, pending_threshold: int | None = None) -> list[dict]:
    thresholds = get_alert_thresholds(db, tenant_id)
    if pending_threshold is None:
        pending_threshold = int(thresholds.get("pending_audit") or 50)
    yield_drop_delta = float(thresholds.get("yield_drop_delta") or 0.05)
    pending_tasks_threshold = int(thresholds.get("pending_tasks") or 30)
    unassigned_sample_min = int(thresholds.get("unassigned_sample_min") or 3)
    created: list[dict] = []
    today = date.today()

    summary = get_dashboard_summary(db, tenant_id)
    pending = int(summary.get("reports", {}).get("pending_audit") or 0)
    if pending >= pending_threshold:
        dedupe = f"pending_audit:{today.isoformat()}"
        if not _already_notified(db, tenant_id, dedupe):
            facts = {"pending_audit": pending, "threshold": pending_threshold}
            title = f"待审报工积压 {pending} 条"
            narrative = _narrative(db, "pending_audit_high", {**facts, "fallback_summary": title})
            ev = AiAlertEvent(
                tenant_id=tenant_id,
                rule_code="pending_audit_high",
                level="warning",
                title=title,
                summary=narrative,
                facts_json=json.dumps(facts, ensure_ascii=False),
                dedupe_key=dedupe,
            )
            db.add(ev)
            db.flush()
            created.append({"id": ev.id, "rule_code": ev.rule_code, "title": title})

    overdue_orders = db.scalars(
        select(Order).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(("confirmed", "producing")),
            Order.due_date.isnot(None),
            Order.due_date < today,
        ).limit(20)
    ).all()
    if overdue_orders:
        dedupe = f"order_overdue:{today.isoformat()}"
        if not _already_notified(db, tenant_id, dedupe):
            codes = [o.code for o in overdue_orders[:5]]
            facts = {"count": len(overdue_orders), "sample_orders": codes}
            title = f"逾期订单 {len(overdue_orders)} 笔"
            narrative = _narrative(db, "order_overdue", {**facts, "fallback_summary": title})
            ev = AiAlertEvent(
                tenant_id=tenant_id,
                rule_code="order_overdue",
                level="danger",
                title=title,
                summary=narrative,
                facts_json=json.dumps(facts, ensure_ascii=False),
                dedupe_key=dedupe,
            )
            db.add(ev)
            db.flush()
            created.append({"id": ev.id, "rule_code": ev.rule_code, "title": title})

    # 良率周环比
    def _yield_for_days(days_back: int) -> float | None:
        d0 = today - timedelta(days=days_back)
        d1 = today - timedelta(days=days_back - 7)
        g = int(
            db.scalar(
                select(func.coalesce(func.sum(Report.good_qty), 0)).where(
                    Report.tenant_id == tenant_id,
                    Report.status == "qc_approved",
                    func.date(Report.created_at) >= d0,
                    func.date(Report.created_at) < d1,
                )
            )
            or 0
        )
        b = int(
            db.scalar(
                select(func.coalesce(func.sum(Report.bad_qty), 0)).where(
                    Report.tenant_id == tenant_id,
                    Report.status == "qc_approved",
                    func.date(Report.created_at) >= d0,
                    func.date(Report.created_at) < d1,
                )
            )
            or 0
        )
        t = g + b
        return round(g / t, 4) if t > 0 else None

    y_recent = _yield_for_days(7)
    y_prev = _yield_for_days(14)
    if y_recent is not None and y_prev is not None and y_prev - y_recent >= yield_drop_delta:
        dedupe = f"yield_drop:{today.isocalendar()[1]}"
        if not _already_notified(db, tenant_id, dedupe):
            facts = {"yield_recent_7d": y_recent, "yield_prev_7d": y_prev}
            title = "近7日良率较上周下降"
            narrative = _narrative(db, "yield_drop", {**facts, "fallback_summary": title})
            ev = AiAlertEvent(
                tenant_id=tenant_id,
                rule_code="yield_drop",
                level="warning",
                title=title,
                summary=narrative,
                facts_json=json.dumps(facts, ensure_ascii=False),
                dedupe_key=dedupe,
            )
            db.add(ev)
            db.flush()
            created.append({"id": ev.id, "rule_code": ev.rule_code, "title": title})

    unassigned = int(
        db.scalar(
            select(func.count(Task.id))
            .select_from(WorkOrder)
            .join(Task, Task.work_order_id == WorkOrder.id)
            .where(WorkOrder.tenant_id == tenant_id, Task.status.in_(("pending", "working")))
        )
        or 0
    )
    if unassigned >= pending_tasks_threshold:
        sample = db.scalars(
            select(Task.id)
            .select_from(WorkOrder)
            .join(Task, Task.work_order_id == WorkOrder.id)
            .where(WorkOrder.tenant_id == tenant_id, Task.status.in_(("pending", "working")))
            .limit(5)
        ).all()
        unassigned_not_dispatch = sum(1 for tid in sample if not task_has_assignments(db, tenant_id, tid))
        if unassigned_not_dispatch >= unassigned_sample_min:
            dedupe = f"plan_dispatch_backlog:{today.isoformat()}"
            if not _already_notified(db, tenant_id, dedupe):
                facts = {"pending_tasks": unassigned, "sample_unassigned": unassigned_not_dispatch}
                title = f"在制任务 {unassigned} 条，派工可能不足"
                narrative = _narrative(db, "plan_overload", {**facts, "fallback_summary": title})
                ev = AiAlertEvent(
                    tenant_id=tenant_id,
                    rule_code="plan_overload",
                    level="warning",
                    title=title,
                    summary=narrative,
                    facts_json=json.dumps(facts, ensure_ascii=False),
                    dedupe_key=dedupe,
                )
                db.add(ev)
                db.flush()
                created.append({"id": ev.id, "rule_code": ev.rule_code, "title": title})

    return created


def notify_pending_alerts(
    db: Session,
    tenant_id: int,
    *,
    alert_prefs: dict | None = None,
) -> int:
    """发送未通知的预警。alert_prefs 来自 production.automation.alerts。"""
    prefs = alert_prefs if isinstance(alert_prefs, dict) else {}
    notify_on_scan = bool(prefs.get("notify_on_scan", True))
    create_todo_on_critical = bool(prefs.get("create_todo_on_critical", False))

    rows = db.scalars(
        select(AiAlertEvent).where(
            AiAlertEvent.tenant_id == tenant_id,
            AiAlertEvent.notified_at.is_(None),
        )
    ).all()
    n = 0
    for ev in rows:
        sent = False
        if notify_on_scan:
            notify_users_with_permission(
                db,
                tenant_id=tenant_id,
                permission_code="ai.alert.view",
                title=f"[AI预警] {ev.title}",
                content=ev.summary or ev.title,
                level=ev.level,
                biz_type="ai_alert",
                biz_id=ev.id,
            )
            sent = True
        if create_todo_on_critical and ev.level == "danger":
            notify_users_with_permission(
                db,
                tenant_id=tenant_id,
                permission_code="plan.manage",
                title=f"[待办] {ev.title}",
                content=ev.summary or ev.title,
                level="danger",
                biz_type="todo",
                biz_id=ev.id,
            )
            sent = True
        if sent:
            ev.notified_at = datetime.utcnow()
            n += 1
            try:
                # 走统一 dispatcher，不带 restrict_channel，
                # 让飞书/企微/钉钉三通道按各自配置的群都收到 alert 事件
                from app.services.notify_dispatcher import dispatch as _dispatch

                _dispatch(
                    db,
                    tenant_id,
                    "alert",
                    title=f"[AI预警] {ev.title}",
                    content=ev.summary or ev.title,
                    level=ev.level,
                    biz_type="ai_alert",
                    biz_id=ev.id,
                )
            except Exception:
                pass
    return n


def scan_all_tenants(db: Session) -> dict:
    from app.services.production_automation_settings import get_automation_settings

    tenant_ids = [r[0] for r in db.execute(select(Tenant.id).where(Tenant.status == "active")).all()]
    total_events = 0
    total_notify = 0
    for tid in tenant_ids:
        try:
            events = scan_tenant_alerts(db, tid)
            total_events += len(events)
            alert_prefs = get_automation_settings(db, tid).get("alerts") or {}
            total_notify += notify_pending_alerts(db, tid, alert_prefs=alert_prefs)
            db.commit()
        except Exception:
            db.rollback()
    return {"tenants": len(tenant_ids), "events": total_events, "notified": total_notify}


def list_recent_alerts(db: Session, tenant_id: int, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(AiAlertEvent)
        .where(AiAlertEvent.tenant_id == tenant_id)
        .order_by(AiAlertEvent.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "rule_code": r.rule_code,
            "level": r.level,
            "title": r.title,
            "summary": r.summary,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
