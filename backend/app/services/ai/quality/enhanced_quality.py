# -*- coding: utf-8 -*-
"""Enhanced quality gene library - LLM semantic defect pattern extraction + trends."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


_KEYWORDS = [
    "划痕", "磕碰", "色差", "毛刺", "尺寸超差", "装配不良", "变形", "表面脏污",
    "裂纹", "气泡", "砂眼", "变形", "划伤", "尺寸偏差", "漏装", "错装",
    "焊接不良", "粗糙度", "平整度", "断差", "外观不良",
]


def extract_quality_patterns(db: Session, tenant_id: int, *, limit: int = 500) -> dict:
    """Extract defect patterns from bad item remarks using keyword + LLM semantic grouping."""
    from app.models.report_unit import ReportUnit
    from app.models.task import Task

    rows = db.scalars(
        select(ReportUnit)
        .where(
            ReportUnit.tenant_id == tenant_id,
            ReportUnit.status == "qc_approved",
            ReportUnit.result_type == "bad",
            ReportUnit.remark.isnot(None),
        )
        .order_by(desc(ReportUnit.id))
        .limit(limit)
    ).all()

    patterns: dict = {}
    total_scanned = len(rows)
    matched_items = 0

    for ru in rows:
        remark = (ru.remark or "").strip()
        if not remark:
            continue
        matched = False
        for kw in _KEYWORDS:
            if kw in remark:
                if kw not in patterns:
                    patterns[kw] = {"count": 0, "samples": [], "process_ids": set()}
                patterns[kw]["count"] += 1
                if len(patterns[kw]["samples"]) < 5:
                    patterns[kw]["samples"].append(remark[:200])
                if hasattr(ru, "task_id") and ru.task_id:
                    patterns[kw]["process_ids"].add(ru.task_id)
                matched = True
        matched_items += matched or 0

    # Try LLM enhancement for unclassified remarks
    unclassified = []
    classified_count = sum(p["count"] for p in patterns.values())
    if total_scanned > classified_count and total_scanned - classified_count > 10:
        # Collect unclassified remarks for LLM analysis
        for ru in rows:
            remark = (ru.remark or "").strip()
            if not remark:
                continue
            is_classified = any(kw in remark for kw in _KEYWORDS)
            if not is_classified and len(unclassified) < 20:
                unclassified.append(remark[:200])

        if unclassified:
            try:
                llm_patterns = _analyze_with_llm(db, tenant_id, unclassified)
                for pattern, info in llm_patterns.items():
                    if pattern not in patterns:
                        patterns[pattern] = {"count": 0, "samples": [], "process_ids": set()}
                    patterns[pattern]["count"] += info.get("count", 0)
                    patterns[pattern]["samples"].extend(info.get("samples", []))
            except Exception as e:
                logger.warning("LLM pattern extraction skipped: %s", e)

    # Build final result
    result_patterns = []
    for tag, info in sorted(patterns.items(), key=lambda x: x[1]["count"], reverse=True):
        result_patterns.append({
            "tag": tag,
            "count": info["count"],
            "samples": info["samples"][:5],
            "related_process_count": len(info.get("process_ids", set())),
        })

    return {
        "ok": True,
        "scanned_items": total_scanned,
        "matched_items": matched_items,
        "patterns_count": len(result_patterns),
        "patterns": result_patterns[:30],
    }


def _analyze_with_llm(db: Session, tenant_id: int, remarks: list) -> dict:
    """Use LLM to extract defect patterns from unclassified remarks."""
    from app.services.ai.client import chat_completion, resolve_runtime

    cfg = resolve_runtime(db, tenant_id=tenant_id)
    if not cfg or not cfg.api_key:
        return {}

    prompt = (
        "以下是生产不良件的备注列表，请从中提取缺陷模式。"
        "对每条备注提取1-2个关键缺陷标签，返回 JSON 格式: {patterns: [{tag, count, sample_remarks}]}\n\n"
        "备注：\n" + "\n".join(f"- {r}" for r in remarks[:30])
    )

    try:
        content, _, _ = chat_completion(
            db, tenant_id=tenant_id, messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=1000, response_format="json_object",
        )
        import json
        data = json.loads(content or "{}")
        extracted = {}
        for item in data.get("patterns", []):
            tag = item.get("tag", "")
            if tag:
                extracted[tag] = {
                    "count": int(item.get("count", 1)),
                    "samples": [s[:200] for s in item.get("sample_remarks", [])[:3]] or [tag],
                }
        return extracted
    except Exception as e:
        logger.warning("LLM defect pattern analysis failed: %s", e)
        return {}


def quality_pattern_trend(db: Session, tenant_id: int, pattern_tag: str, *, days: int = 30) -> dict:
    """Analyze trend for a specific quality pattern over time."""
    from app.models.report_unit import ReportUnit

    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(func.date(ReportUnit.created_at), func.count(ReportUnit.id))
        .where(
            ReportUnit.tenant_id == tenant_id,
            ReportUnit.status == "qc_approved",
            ReportUnit.result_type == "bad",
            ReportUnit.remark.contains(pattern_tag),
            func.date(ReportUnit.created_at) >= since,
        )
        .group_by(func.date(ReportUnit.created_at))
    ).all()

    daily = [{"date": str(r[0]), "count": int(r[1] or 0)} for r in rows]
    total = sum(d["count"] for d in daily)
    return {"ok": True, "pattern": pattern_tag, "days": days, "total_count": total, "daily": daily}


def auto_defect_dictionary(db: Session, tenant_id: int, *, limit: int = 100) -> dict:
    """Auto-generate defect code dictionary from recent remarks."""
    patterns = extract_quality_patterns(db, tenant_id, limit=limit)
    dict_items = []
    for p in patterns.get("patterns", []):
        dict_items.append({
            "code": "DEF_" + p["tag"][:3].upper().replace(" ", "_"),
            "label": p["tag"],
            "sample_count": p["count"],
            "description": "系统自动提取: " + (p["samples"][0] if p["samples"] else p["tag"]),
        })
    return {"ok": True, "dictionary": dict_items, "total_patterns": len(dict_items)}
