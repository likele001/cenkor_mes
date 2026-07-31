# -*- coding: utf-8 -*-
"""Equipment health prediction - Prophet time series + sklearn IsolationForest.

Data sources: EquipmentCheck entries (daily checks per equipment).
Prediction targets:
  - Check frequency trend (Prophet) -> predicted_score_7d
  - Anomaly detection (IsolationForest) -> anomaly_flag / anomaly_score
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.equipment import Equipment, EquipmentCheck
from app.services.ai.predict.model_manager import get_model, save_model

logger = logging.getLogger(__name__)

_MIN_DATA_POINTS = 7  # need at least a week of data to train

# Health score thresholds (0-100)
_SCORE_EXCELLENT = 90
_SCORE_GOOD = 75
_SCORE_WATCH = 55


def _fetch_check_series(db: Session, tenant_id: int, equipment_id: int, days: int = 90) -> list:
    """Return daily check counts for the last N days as [(date_str, count), ...]."""
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(EquipmentCheck.created_at).label("d"),
            func.count(EquipmentCheck.id).label("cnt"),
        )
        .where(
            EquipmentCheck.tenant_id == tenant_id,
            EquipmentCheck.equipment_id == equipment_id,
            func.date(EquipmentCheck.created_at) >= since,
        )
        .group_by(func.date(EquipmentCheck.created_at))
        .order_by("d")
    ).all()
    return [(r[0], int(r[1] or 0)) for r in rows]


def _train_prophet(series: list):
    """Train a Prophet model on check frequency series.

    Returns trained model or None if Prophet unavailable / insufficient data.
    """
    try:
        import pandas as pd
        from prophet import Prophet

        df = pd.DataFrame([{"ds": str(d), "y": c} for d, c in series])
        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.1,
        )
        model.fit(df)
        return model
    except ImportError:
        return None
    except Exception as e:
        logger.warning("Prophet training failed: %s", e)
        return None


def _train_isolation_forest(series: list):
    """Train IsolationForest on check frequency to detect unusual patterns.

    Returns (model, scaler) or (None, None) if sklearn unavailable.
    """
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest

        counts = np.array([c for _, c in series]).reshape(-1, 1).astype(float)
        if len(counts) < _MIN_DATA_POINTS:
            return None, None

        model = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            random_state=42,
        )
        model.fit(counts)
        return model, float(counts.mean())
    except ImportError:
        return None, None
    except Exception as e:
        logger.warning("IsolationForest training failed: %s", e)
        return None, None


def train_equipment_model(
    db: Session, tenant_id: int, equipment_id: int, *, days: int = 90
) -> dict:
    """Train (or retrain) prediction models for a single equipment."""
    series = _fetch_check_series(db, tenant_id, equipment_id, days=days)
    if len(series) < _MIN_DATA_POINTS:
        return {"ok": False, "reason": "insufficient_data", "data_points": len(series)}

    prophet_model = _train_prophet(series)
    if_model, mean_count = _train_isolation_forest(series)

    saved_pro = False
    if prophet_model is not None:
        saved_pro = save_model("equipment_prophet", f"{tenant_id}_{equipment_id}", prophet_model)
    saved_if = False
    if if_model is not None:
        saved_if = save_model(
            "equipment_if", f"{tenant_id}_{equipment_id}", (if_model, mean_count)
        )

    return {
        "ok": True,
        "data_points": len(series),
        "prophet_saved": saved_pro,
        "isolation_forest_saved": saved_if,
    }


def predict_health(db: Session, tenant_id: int, equipment_id: int, *, days: int = 90) -> dict:
    """Predict equipment health score for the next N days."""
    series = _fetch_check_series(db, tenant_id, equipment_id, days=days)
    total = sum(c for _, c in series)

    result = {
        "equipment_id": equipment_id,
        "data_points": len(series),
        "total_checks_90d": total,
        "model_version": "prophet_v1",
        "has_model": False,
        "predicted_score_7d": None,
        "trend": "stable",
        "anomaly_detected": False,
        "anomaly_score": 0.0,
    }

    # Try Prophet for trend prediction
    prophet_model = get_model("equipment_prophet", f"{tenant_id}_{equipment_id}")
    if prophet_model is not None and len(series) >= _MIN_DATA_POINTS:
        try:
            import pandas as pd

            future = prophet_model.make_future_dataframe(periods=7, include_history=False)
            forecast = prophet_model.predict(future)
            predicted_avg = float(forecast["yhat"].mean())
            # Map predicted check frequency to 0-100 score
            # 0 checks -> score 35, 12+ checks in 7 days -> score 92
            normalized = min(1.0, predicted_avg / 1.7)  # ~12 checks = 12/7 ≈ 1.7/day
            score = 35 + int(normalized * 57)
            result["predicted_score_7d"] = score

            # Determine trend (compare to recent actual average)
            recent = series[-14:] if len(series) >= 14 else series
            recent_avg = sum(c for _, c in recent) / len(recent)
            if predicted_avg > recent_avg * 1.15:
                result["trend"] = "improving"
            elif predicted_avg < recent_avg * 0.85:
                result["trend"] = "declining"
            else:
                result["trend"] = "stable"

            result["has_model"] = True
        except Exception as e:
            logger.warning("Prophet prediction failed: %s", e)

    # Try IsolationForest for anomaly detection
    if_model_data = get_model("equipment_if", f"{tenant_id}_{equipment_id}")
    if if_model_data is not None and len(series) >= _MIN_DATA_POINTS:
        try:
            import numpy as np

            if_model, _mean = if_model_data
            recent_counts = np.array([[c] for _, c in series[-7:]]).astype(float)
            preds = if_model.predict(recent_counts)
            anomaly_ratio = float(sum(1 for p in preds if p < 0)) / max(len(preds), 1)
            result["anomaly_detected"] = anomaly_ratio > 0.3
            result["anomaly_score"] = round(anomaly_ratio, 3)
        except Exception as e:
            logger.warning("IsolationForest anomaly detection failed: %s", e)

    return result


def equipment_health_scores_enhanced(
    db: Session, tenant_id: int, *, days: int = 90
) -> dict:
    """Enhanced version of equipment_health_scores: rule + ML prediction."""
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

        # Base rule score
        if checks >= 12:
            score, level = 92, "good"
        elif checks >= 4:
            score, level = 75, "watch"
        elif checks >= 1:
            score, level = 55, "watch"
        else:
            score, level = 35, "risk"

        # ML prediction overlay (if available)
        prediction = predict_health(db, tenant_id, eq.id, days=days)
        final_score = score
        if prediction["has_model"] and prediction["predicted_score_7d"] is not None:
            final_score = int(score * 0.5 + prediction["predicted_score_7d"] * 0.5)
            # Recompute level
            if final_score >= _SCORE_EXCELLENT:
                level = "good"
            elif final_score >= _SCORE_GOOD:
                level = "watch"
            else:
                level = "risk"

        suggestion = "维持当前保养节奏"
        if prediction["trend"] == "declining":
            suggestion = "点检频次下降，建议主动安排保养"
        elif prediction["anomaly_detected"]:
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
                "base_score": score,
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


def train_all_equipment(db: Session, tenant_id: int, *, days: int = 90) -> dict:
    """Train prediction models for all active equipment in a tenant."""
    eqs = db.scalars(
        select(Equipment).where(
            Equipment.tenant_id == tenant_id, Equipment.status == "active"
        )
    ).all()
    trained = 0
    skipped = 0
    for eq in eqs:
        result = train_equipment_model(db, tenant_id, eq.id, days=days)
        if result.get("ok"):
            trained += 1
        else:
            skipped += 1
    return {"ok": True, "total": len(eqs), "trained": trained, "skipped_insufficient_data": skipped}
