"""Quality gene library - basic keyword matching + enhanced LLM pattern extraction."""

from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.report_unit import ReportUnit

_KEYWORDS = ["划痕", "磕碰", "色差", "毛刺", "尺寸超差", "装配不良", "变形", "表面脏污",
             "裂纹", "气泡", "砂眼", "划伤", "尺寸偏差", "漏装", "错装",
             "焊接不良", "粗糙度", "平整度", "断差", "外观不良"]


def list_quality_genes(db: Session, *, limit: int = 50) -> dict:
    """Basic keyword-based defect pattern extraction."""
    rows = db.scalars(
        select(ReportUnit)
        .where(
            ReportUnit.status == "qc_approved",
            ReportUnit.result_type == "bad",
            ReportUnit.remark.isnot(None),
        )
        .order_by(desc(ReportUnit.id))
        .limit(500)
    ).all()
    genes: dict = {}
    for r in rows:
        remark = r.remark or ""
        for kw in _KEYWORDS:
            if kw in remark:
                if kw not in genes:
                    genes[kw] = {"tag": kw, "count": 0, "sample": remark[:100]}
                genes[kw]["count"] += 1
    gene_list = sorted(genes.values(), key=lambda x: x["count"], reverse=True)[:limit]
    return {"ok": True, "genes": gene_list, "scanned": len(rows), "pattern_count": len(gene_list)}


def extract_quality_patterns(db: Session, *, limit: int = 500) -> dict:
    """Enhanced pattern extraction using LLM semantic grouping."""
    try:
        from app.services.ai.quality.enhanced_quality import extract_quality_patterns as _enhanced
        return _enhanced(db, limit=limit)
    except Exception as e:
        return list_quality_genes(db, limit=limit)


def auto_defect_dictionary(db: Session) -> dict:
    """Auto-generate defect code dictionary."""
    try:
        from app.services.ai.quality.enhanced_quality import auto_defect_dictionary as _enhanced
        return _enhanced(db)
    except Exception as e:
        basic = list_quality_genes(db)
        return {"ok": True, "dictionary": [{"code": "DEF_" + g["tag"][:3], "label": g["tag"], "sample_count": g["count"]} for g in basic.get("genes", [])]}