# -*- coding: utf-8 -*-
"""CenkorMES RAG auto index manager."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_META_KEY = "rag:index_meta"


def _resolve_docs_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs"
        if candidate.is_dir() and any(candidate.glob("*.md")):
            return candidate
    return here.parents[4] / "docs"


def _docs_signature(docs_dir: Path) -> dict:
    sig = []
    if docs_dir.is_dir():
        for path in sorted(docs_dir.glob("*.md")):
            try:
                sig.append({"name": path.name, "mtime": path.stat().st_mtime_ns})
            except OSError:
                continue
    return {"files": sig, "count": len(sig)}


def _get_meta(redis_client) -> dict:
    try:
        raw = redis_client.get(_META_KEY)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return {}


def _set_meta(redis_client, meta: dict) -> None:
    try:
        redis_client.set(_META_KEY, json.dumps(meta, ensure_ascii=False), ex=86400 * 7)
    except Exception as e:
        logger.warning("Redis write index meta failed: %s", e)


def scheduled_reindex(db: Session) -> dict:
    import redis
    from app.core.config import settings
    from app.services.ai.rag_vector import build_vector_index

    docs_dir = _resolve_docs_dir()
    sig = _docs_signature(docs_dir)

    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    meta = _get_meta(redis_client)

    old_sig = meta.get("signature", {})
    old_files = {f["name"]: f["mtime"] for f in old_sig.get("files", [])}
    new_files = {f["name"]: f["mtime"] for f in sig["files"]}

    changed = False
    if old_files.keys() != new_files.keys():
        changed = True
    else:
        for name, mtime in new_files.items():
            if old_files.get(name) != mtime:
                changed = True
                break

    if not changed:
        return {"status": "up_to_date", "files": sig["count"], "message": "no changes"}

    try:
        total = build_vector_index(db, force=False)
        new_meta = {
            "signature": sig,
            "last_indexed": datetime.now().isoformat(),
            "total_chunks": total,
        }
        _set_meta(redis_client, new_meta)
        return {"status": "reindexed", "files": sig["count"], "total_chunks": total}
    except Exception as e:
        logger.error("Scheduled reindex failed: %s", e)
        return {"status": "error", "message": str(e)[:200]}


def force_reindex(db: Session) -> dict:
    import redis
    from app.core.config import settings
    from app.services.ai.rag_vector import build_vector_index

    docs_dir = _resolve_docs_dir()
    sig = _docs_signature(docs_dir)

    try:
        total = build_vector_index(db, force=True)
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        new_meta = {
            "signature": sig,
            "last_indexed": datetime.now().isoformat(),
            "total_chunks": total,
        }
        _set_meta(redis_client, new_meta)
        return {"status": "force_reindexed", "files": sig["count"], "total_chunks": total}
    except Exception as e:
        logger.error("Force reindex failed: %s", e)
        return {"status": "error", "message": str(e)[:200]}
