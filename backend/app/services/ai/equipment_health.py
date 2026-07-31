# -*- coding: utf-8 -*-
"""Equipment health - rule-based + Prophet + IsolationForest prediction."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.equipment import Equipment, EquipmentCheck


def equipment_health_scores(db: Session, tenant_id: int, *, days: int = 90) -> dict:
    """Original rule-based scores (kept for backward compatibility)."""
    since = date.today() - timedelta(days=days)
    eqs = db.scalars(
        select(Equipment).where(
            Equipment.tenant_id == tenant_id, Equipment.status == "active"
        )
    ).all()
    items = []
    for eq in eqs:
        checks = int(
            db.scalar(
                select(func.count(EquipmentCheck.id)).where(
                    EquipmentCheck.tenant_id == tenant_id,
                    EquipmentCheck.equipment_id == eq.id,
                    func.date(EquipmentCheck.created_at) >= since,
                )
            ) or 0
        )
        if checks >= 12:
            score, level = 92, "good"
        elif checks >= 4:
            score, level = 75, "watch"
        elif checks >= 1:
            score, level = 55, "watch"
        else:
            score, level = 35, "risk"
        items.append(
            {
                "equipment_id": eq.id,
                "code": eq.code,
                "name": eq.name,
                "check_count_90d": checks,
                "health_score": score,
                "level": level,
                "suggestion": "建议安排点检" if checks < 4 else "维持当前保养节奏",
            }
        )
    items.sort(key=lambda x: x["health_score"])
    return {"ok": True, "window_days": days, "items": items, "model": "rule_v1"}


def equipment_health_scores_enhanced(
    db: Session, tenant_id: int, *, days: int = 90
) -> dict:
    """Enhanced: rule base + ML prediction overlay."""
    try:
        from app.services.ai.predict.equipment_predictor import (
            predict_health,
            train_equipment_model,
        )
        ml_available = True
    except ImportError:
        ml_available = False

    since = date.today() - timedelta(days=days)
    eqs = db.scalars(
        select(Equipment).where(
            Equipment.tenant_id == tenant_id, Equipment.status == "active"
        )
    ).all()

    items = []
    for eq in eqs:
        checks = int(
            db.scalar(
                select(func.count(EquipmentCheck.id)).where(
                    EquipmentCheck.tenant_id == tenant_id,
                    EquipmentCheck.equipment_id == eq.id,
                    func.date(EquipmentCheck.created_at) >= since,
                )
            ) or 0
        )

        if checks >= 12:
            base_score, level = 92, "good"
        elif checks >= 4:
            base_score, level = 75, "watch"
        elif checks >= 1:
            base_score, level = 55, "watch"
        else:
            base_score, level = 35, "risk"

        final_score = base_score
        prediction = {"has_model": False, "trend": "stable", "anomaly_detected": False}

        if ml_available:
            try:
                prediction = predict_health(db, tenant_id, eq.id, days=days)
                if prediction.get("has_model") and prediction.get("predicted_score_7d"):
                    final_score = int(base_score * 0.5 + prediction["predicted_score_7d"] * 0.5)
                    if final_score >= 90:
                        level = "good"
                    elif final_score >= 75:
                        level = "watch"
                    else:
                        level = "risk"
            except Exception:
                pass

        suggestion = "维持当前保养节奏"
        if prediction.get("trend") == "declining":
            suggestion = "点检频次下降，建议主动安排保养"
        elif prediction.get("anomaly_detected"):
            suggestion = "检测到异常点检模式，建议人工复核"
        elif checks < 4:
            suggestion = "建议安排点检"

        items.append(
            {
                "equipment_id": eq.id,
                "code": eq.code,
                "name": eq.name,
                "check_count_90d": checks,
                "health_score": final_score,
                "base_score": base_score,
                "predicted_score_7d": prediction.get("predicted_score_7d"),
                "trend": prediction.get("trend", "stable"),
                "anomaly_detected": prediction.get("anomaly_detected", False),
                "anomaly_score": prediction.get("anomaly_score", 0.0),
                "level": level,
                "suggestion": suggestion,
                "has_ml_model": prediction.get("has_model", False),
            }
        )

    items.sort(key=lambda x: x["health_score"])
    return {
        "ok": True,
        "window_days": days,
        "items": items,
        "model": "rule_v1 + prophet_v1",
        "total_equipment": len(items),
        "with_ml_model": sum(1 for i in items if i["has_ml_model"]),
    }
