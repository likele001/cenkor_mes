# -*- coding: utf-8 -*-
"""Yield prediction - Prophet trend + sklearn IsolationForest anomaly detection.

Data sources: Report entries grouped by date and process (工序).
Prediction targets:
  - Per-process yield trend (Prophet) -> predicted_yield_7d
  - Factory-wide anomaly detection (IsolationForest)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.report import Report
from app.models.task import Task
from app.services.ai.predict.model_manager import get_model, save_model

logger = logging.getLogger(__name__)

_MIN_DATA_POINTS = 7


def _fetch_yield_series(db: Session, process_id: int, days: int = 90) -> list:
    """Return daily yield rate series: [(date_str, good_qty, bad_qty, yield_rate), ...]."""
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(Report.created_at).label("d"),
            func.sum(Report.good_qty).label("g"),
            func.sum(Report.bad_qty).label("b"),
        )
        .select_from(Report)
        .join(Task, Task.id == Report.task_id)
        .where(
            Task.process_id == process_id,
            func.date(Report.created_at) >= since,
        )
        .group_by(func.date(Report.created_at))
        .order_by("d")
    ).all()

    series = []
    for r in rows:
        g = int(r[1] or 0)
        b = int(r[2] or 0)
        total = g + b
        rate = g / total if total > 0 else 0.0
        series.append((r[0], g, b, rate))
    return series


def _fetch_factory_series(db: Session, days: int = 90) -> list:
    """Return factory-wide daily yield rate."""
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(Report.created_at).label("d"),
            func.sum(Report.good_qty).label("g"),
            func.sum(Report.bad_qty).label("b"),
        )
        .where(
            func.date(Report.created_at) >= since,
        )
        .group_by(func.date(Report.created_at))
        .order_by("d")
    ).all()

    series = []
    for r in rows:
        g = int(r[1] or 0)
        b = int(r[2] or 0)
        total = g + b
        rate = g / total if total > 0 else 0.0
        series.append((r[0], g, b, rate))
    return series


def _train_prophet_yield(series: list):
    """Train Prophet on yield rate series."""
    try:
        import pandas as pd
        from prophet import Prophet

        df = pd.DataFrame([{"ds": str(d), "y": rate} for d, _, _, rate in series])
        # Filter out zero-rate days (likely no production that day)
        df = df[df["y"] > 0]
        if len(df) < _MIN_DATA_POINTS:
            return None

        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
        )
        model.fit(df)
        return model
    except ImportError:
        return None
    except Exception as e:
        logger.warning("Prophet yield training failed: %s", e)
        return None


def _train_isolation_forest_yield(series: list):
    """Train IsolationForest on yield rates."""
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest

        rates = np.array([[r] for _, _, _, r in series]).astype(float)
        # Remove zeros (non-production days)
        rates = rates[rates > 0].reshape(-1, 1)
        if len(rates) < _MIN_DATA_POINTS:
            return None

        model = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            random_state=42,
        )
        model.fit(rates)
        return model
    except ImportError:
        return None
    except Exception as e:
        logger.warning("IsolationForest yield training failed: %s", e)
        return None


def train_yield_model(db: Session, process_id: int, *, days: int = 90) -> dict:
    """Train prediction model for a specific process."""
    series = _fetch_yield_series(db, process_id, days=days)
    if len(series) < _MIN_DATA_POINTS:
        return {"ok": False, "reason": "insufficient_data", "data_points": len(series)}

    prophet_model = _train_prophet_yield(series)
    if_model = _train_isolation_forest_yield(series)

    saved_pro = False
    if prophet_model is not None:
        saved_pro = save_model("yield_prophet", f"0_{process_id}", prophet_model)
    saved_if = False
    if if_model is not None:
        saved_if = save_model("yield_if", f"0_{process_id}", if_model)

    return {
        "ok": True,
        "process_id": process_id,
        "data_points": len(series),
        "prophet_saved": saved_pro,
        "isolation_forest_saved": saved_if,
    }


def predict_yield(db: Session, process_id: int, *, days: int = 7) -> dict:
    """Predict yield rate for a process."""
    model = get_model("yield_prophet", f"0_{process_id}")

    if model is None:
        return {"ok": False, "reason": "no_model", "process_id": process_id}

    try:
        import pandas as pd

        future = model.make_future_dataframe(periods=days, include_history=False)
        forecast = model.predict(future)
        predicted = [
            {"date": str(forecast["ds"].iloc[i].date()), "yhat": round(float(v), 4)}
            for i, v in enumerate(forecast["yhat"].tolist())
        ]
        avg_yield = round(float(forecast["yhat"].mean()), 4)

        # Historical comparison
        series = _fetch_yield_series(db, process_id, days=30)
        recent_rates = [r for _, _, _, r in series if r > 0]
        historical_avg = round(sum(recent_rates) / len(recent_rates), 4) if recent_rates else None

        return {
            "ok": True,
            "process_id": process_id,
            "predicted_days": days,
            "predicted_avg": avg_yield,
            "historical_avg_30d": historical_avg,
            "prediction_series": predicted,
            "trend": (
                "improving"
                if historical_avg is not None and avg_yield > historical_avg * 1.02
                else "declining" if historical_avg is not None and avg_yield < historical_avg * 0.98
                else "stable"
            ),
        }
    except Exception as e:
        logger.warning("Yield prediction failed: %s", e)
        return {"ok": False, "reason": "prediction_error", "error": str(e)[:100]}


def detect_factory_anomalies(db: Session, *, days: int = 90) -> dict:
    """Detect factory-wide anomalous production days using IsolationForest."""
    series = _fetch_factory_series(db, days=days)
    if len(series) < _MIN_DATA_POINTS:
        return {"ok": False, "reason": "insufficient_data", "data_points": len(series)}

    # Try IsolationForest for anomaly detection
    if_model = get_model("yield_if", "0_factory")
    if if_model is None:
        # Train on the fly
        if_model = _train_isolation_forest_yield(series)
        if if_model is not None:
            save_model("yield_if", "0_factory", if_model)

    if if_model is None:
        return {"ok": False, "reason": "model_unavailable"}

    try:
        import numpy as np

        rates = np.array([[r] for _, _, _, r in series]).astype(float)
        mask = rates.flatten() > 0
        valid_rates = rates[mask].reshape(-1, 1)
        if len(valid_rates) == 0:
            return {"ok": False, "reason": "no_positive_yield_data"}

        predictions = if_model.predict(valid_rates)
        scores = if_model.decision_function(valid_rates)

        anomalies = []
        valid_dates = [d for d, g, b, r in series if r > 0]
        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred < 0:  # anomaly
                date_idx = min(i, len(valid_dates) - 1)
                anomalies.append(
                    {
                        "date": valid_dates[date_idx] if date_idx < len(valid_dates) else None,
                        "yield_rate": float(valid_rates[i][0]),
                        "anomaly_score": round(float(score), 4),
                    }
                )

        # Sort by anomaly score (most negative = most anomalous)
        anomalies.sort(key=lambda x: x["anomaly_score"])
        return {
            "ok": True,
            "total_days": len(valid_rates),
            "anomaly_count": len(anomalies),
            "anomaly_rate": round(len(anomalies) / max(len(valid_rates), 1), 4),
            "top_anomalies": anomalies[:10],
        }
    except Exception as e:
        logger.warning("Factory anomaly detection failed: %s", e)
        return {"ok": False, "reason": "analysis_error", "error": str(e)[:100]}


def list_all_yield_predictions(db: Session, *, days: int = 7) -> dict:
    """Get yield predictions for all processes with trained models."""
    from app.services.ai.predict.model_manager import list_trained_models

    keys = list_trained_models("yield_prophet")
    results = []
    for key in keys:
        try:
            pid = int(key.split("_")[-1])
        except (ValueError, IndexError):
            continue
        pred = predict_yield(db, pid, days=days)
        if pred.get("ok"):
            results.append(pred)
    return {"ok": True, "predictions": results, "total_processes": len(results)}