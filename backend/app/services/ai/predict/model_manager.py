# -*- coding: utf-8 -*-
"""CenkorMES prediction model manager - serialize/deserialize ML models to disk."""

from __future__ import annotations

import logging
import os
import time
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_MAX = 20
_CACHE_TTL = 3600  # 1 hour

_cache: "OrderedDict[str, tuple]" = OrderedDict()


def _get_store_dir() -> Path:
    d = Path("./data/predict_models")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _model_path(model_type: str, key: str) -> Path:
    store = _get_store_dir()
    safe_key = str(key).replace("/", "_").replace("\\", "_")
    d = store / model_type
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe_key}.joblib"


def get_model(model_type: str, key: str):
    """Load model, with LRU memory cache.

    Returns None if model file does not exist or fails to load.
    """
    cache_key = f"{model_type}:{key}"
    now = time.time()

    if cache_key in _cache:
        cached_at, model = _cache[cache_key]
        if now - cached_at < _CACHE_TTL:
            _cache.move_to_end(cache_key)
            return model
        del _cache[cache_key]

    path = _model_path(model_type, key)
    if not path.exists():
        return None

    try:
        import joblib

        model = joblib.load(path)
        _cache[cache_key] = (now, model)
        if len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
        logger.info("Loaded model %s/%s from %s", model_type, key, path)
        return model
    except Exception as e:
        logger.warning("Failed to load model %s/%s: %s", model_type, key, e)
        try:
            path.unlink()
        except OSError:
            pass
        return None


def save_model(model_type: str, key: str, model) -> bool:
    """Serialize model to disk."""
    try:
        import joblib

        path = _model_path(model_type, key)
        joblib.dump(model, path, compress=3)
        cache_key = f"{model_type}:{key}"
        _cache[cache_key] = (time.time(), model)
        if len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
        logger.info("Saved model %s/%s to %s (%s bytes)", model_type, key, path, path.stat().st_size)
        return True
    except Exception as e:
        logger.warning("Failed to save model %s/%s: %s", model_type, key, e)
        return False


def list_trained_models(model_type: str) -> list:
    """List all trained model keys for a type."""
    store = _get_store_dir()
    d = store / model_type
    if not d.exists():
        return []
    return [p.stem for p in sorted(d.glob("*.joblib"))]


def cleanup_stale_models(max_age_days: int = 30) -> int:
    """Remove model files older than max_age_days. Returns removed count."""
    store = _get_store_dir()
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    for f in store.rglob("*.joblib"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info("Cleaned up %d stale model files", removed)
    return removed
