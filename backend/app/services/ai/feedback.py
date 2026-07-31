# -*- coding: utf-8 -*-
"""AI feedback loop - user corrections improve RAG knowledge."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, desc, select, insert, update, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def submit_feedback(
    db: Session,
    tenant_id: int,
    user_id: int,
    query: str,
    answer: Optional[str] = None,
    feedback_type: str = "thumb_up",
    corrected_answer: Optional[str] = None,
    conversation_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> dict:
    """Record user feedback on an AI answer."""
    try:
        db.execute(
            text("""INSERT INTO ai_rag_feedbacks
               (tenant_id, user_id, query, answer, feedback_type, corrected_answer, conversation_id, message_id, processed, created_at)
               VALUES (:tenant_id, :user_id, :query, :answer, :feedback_type, :corrected_answer, :conversation_id, :message_id, 0, NOW())"""),
            {"tenant_id": tenant_id, "user_id": user_id, "query": query, "answer": answer, "feedback_type": feedback_type, "corrected_answer": corrected_answer, "conversation_id": conversation_id, "message_id": message_id},
        )
        db.commit()
    except Exception as e:
        logger.error("Feedback insert failed: %s", e)
        db.rollback()
        return {"ok": False, "error": str(e)[:100]}

    result = {"ok": True, "feedback_type": feedback_type, "processed": False}
    if feedback_type == "corrected" and corrected_answer and corrected_answer.strip():
        processed = _process_corrected_answer(db, tenant_id, query, corrected_answer)
        result.update(processed)
    return result


def _process_corrected_answer(db: Session, tenant_id: int, query: str, corrected: str) -> dict:
    """Process a user-corrected answer into ChromaDB as new knowledge."""
    try:
        from app.services.ai.rag_vector import _get_chroma_collection
        import hashlib

        collection = _get_chroma_collection()
        doc_id = f"user_correction_{tenant_id}_{hashlib.md5((query + corrected).encode()).hexdigest()[:12]}"
        meta = {
            "source": "user_corrected",
            "title": "用户纠正: " + query[:40],
            "query": query[:500],
            "chunk_index": 0,
        }
        content = f"User Question: {query}\nCorrect Answer: {corrected}"
        try:
            collection.upsert(ids=[doc_id], documents=[content], metadatas=[meta])
            return {"ok": True, "added_to_chroma": True, "doc_id": doc_id}
        except Exception as e:
            # Fallback: no embedding available, just store in DB
            logger.warning("ChromaDB upsert failed: %s", e)
            return {"ok": True, "added_to_chroma": False, "note": "Stored as fallback"}
    except Exception as e:
        logger.error("Correction processing failed: %s", e)
        return {"ok": True, "added_to_chroma": False, "note": str(e)[:100]}


def get_feedback_stats(db: Session, tenant_id: int, *, days: int = 30) -> dict:
    """Get feedback statistics."""
    rows = db.execute(
        text("""SELECT feedback_type, COUNT(*) as cnt
           FROM ai_rag_feedbacks
           WHERE tenant_id = :tenant_id AND created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
           GROUP BY feedback_type"""),
        {"tenant_id": tenant_id, "days": days},
    ).all()
    stats = {r[0]: r[1] for r in rows}
    total = sum(stats.values())
    total_corrected = stats.get("corrected", 0)
    return {
        "ok": True,
        "total": total,
        "by_type": stats,
        "correction_rate": round(total_corrected / total, 3) if total else 0,
    }


def list_recent_feedback(db: Session, tenant_id: int, *, limit: int = 20) -> dict:
    """List recent feedback entries."""
    rows = db.execute(
        text("""SELECT id, feedback_type, query, answer, corrected_answer, processed, created_at
           FROM ai_rag_feedbacks
           WHERE tenant_id = :tenant_id
           ORDER BY created_at DESC
           LIMIT :limit"""),
        {"tenant_id": tenant_id, "limit": limit},
    ).all()
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "feedback_type": r[1],
            "query": r[2][:200] if r[2] else "",
            "has_answer": bool(r[3]),
            "has_corrected": bool(r[4]),
            "processed": bool(r[5]) if r[5] is not None else False,
            "created_at": str(r[6]) if r[6] else None,
        })
    return {"ok": True, "items": items}
