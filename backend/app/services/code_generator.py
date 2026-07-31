"""统一业务编号：前缀 + 日期(可选) + 按日递增序号。示例 ORD202605200001"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.code_sequence import CodeSequence




class BizType:
    ORDER = "order"
    PRODUCTION_PLAN = "production_plan"
    PURCHASE_ORDER = "purchase_order"
    SUPPLIER_STATEMENT = "supplier_statement"
    CUSTOMER_STATEMENT = "customer_statement"
    PRODUCT = "product"
    SKU = "sku"
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    MATERIAL = "material"
    PROCESS = "process"
    WAREHOUSE = "warehouse"
    EQUIPMENT = "equipment"
    SKILL = "skill"
    DEPARTMENT = "department"
    CRM_OPPORTUNITY = "crm_opportunity"
    SAAS_PACKAGE = "saas_package"
    SHIFT = "shift"
    MRP_RUN = "mrp_run"
    QUOTATION = "quotation"
    SUBCONTRACT = "subcontract"


@dataclass(frozen=True)
class _Rule:
    prefix: str
    seq_width: int = 4
    daily: bool = True


_RULES: dict[str, _Rule] = {
    BizType.ORDER: _Rule("ORD"),
    BizType.PRODUCTION_PLAN: _Rule("PLN"),
    BizType.PURCHASE_ORDER: _Rule("PO"),
    BizType.SUPPLIER_STATEMENT: _Rule("SS"),
    BizType.CUSTOMER_STATEMENT: _Rule("CS"),
    BizType.PRODUCT: _Rule("PRD"),
    BizType.SKU: _Rule("SKU"),
    BizType.CUSTOMER: _Rule("CUS"),
    BizType.SUPPLIER: _Rule("SUP"),
    BizType.MATERIAL: _Rule("MAT"),
    BizType.PROCESS: _Rule("PRC"),
    BizType.WAREHOUSE: _Rule("WH"),
    BizType.EQUIPMENT: _Rule("EQ"),
    BizType.SKILL: _Rule("SKL"),
    BizType.DEPARTMENT: _Rule("DEPT"),
    BizType.CRM_OPPORTUNITY: _Rule("OPP"),
    BizType.SAAS_PACKAGE: _Rule("PKG"),
    BizType.SHIFT: _Rule("SHF"),
    BizType.MRP_RUN: _Rule("MRP"),
    BizType.QUOTATION: _Rule("QT"),
    BizType.SUBCONTRACT: _Rule("SC"),
}


def list_biz_types() -> list[dict]:
    items = []
    for key, rule in _RULES.items():
        d = datetime.now().strftime("%Y%m%d")
        example = f"{rule.prefix}{d}{'1'.zfill(rule.seq_width)}" if rule.daily else f"{rule.prefix}{'1'.zfill(rule.seq_width)}"
        items.append({"biz_type": key, "prefix": rule.prefix, "daily_reset": rule.daily, "example": example})
    return items


def _format_code(rule: _Rule, period_key: str, seq: int) -> str:
    suffix = str(seq).zfill(rule.seq_width)
    return f"{rule.prefix}{period_key}{suffix}" if rule.daily else f"{rule.prefix}{suffix}"


def _sync_sequence_from_manual_code(db: Session, biz_type: str, code: str) -> None:
    rule = _RULES.get(biz_type)
    if not rule:
        return
    period_key = datetime.now().strftime("%Y%m%d") if rule.daily else ""
    if rule.daily:
        prefix_period = f"{rule.prefix}{period_key}"
        if not code.startswith(prefix_period):
            return
        seq_part = code[len(prefix_period) :]
    else:
        if not code.startswith(rule.prefix):
            return
        seq_part = code[len(rule.prefix) :]
    if not seq_part.isdigit():
        return
    seq = int(seq_part)
    row = db.scalar(
        select(CodeSequence).where(
            CodeSequence.biz_type == biz_type,
            CodeSequence.period_key == period_key,
        )
    )
    if not row:
        row = CodeSequence(biz_type=biz_type, period_key=period_key, last_value=seq)
        db.add(row)
    elif seq > row.last_value:
        row.last_value = seq
    db.flush()


def allocate_code(db: Session, biz_type: str) -> str:
    rule = _RULES.get(biz_type)
    if not rule:
        raise ValueError(f"未知编号类型: {biz_type}")
    period_key = datetime.now().strftime("%Y%m%d") if rule.daily else ""
    row = db.scalar(
        select(CodeSequence)
        .where(
            CodeSequence.biz_type == biz_type,
            CodeSequence.period_key == period_key,
        )
        .with_for_update()
    )
    if not row:
        row = CodeSequence(biz_type=biz_type, period_key=period_key, last_value=0)
        db.add(row)
        db.flush()
    row.last_value += 1
    db.flush()
    return _format_code(rule, period_key, row.last_value)


def resolve_code(
    db: Session,
    *,
    biz_type: str,
    code: str | None,
    exists: Callable[[str], bool],
    duplicate_msg: str = "编号已存在",
) -> str:
    manual = (code or "").strip()
    if manual:
        if exists(manual):
            raise HTTPException(status_code=400, detail=duplicate_msg)
        _sync_sequence_from_manual_code(db, biz_type, manual)
        return manual
    for _ in range(8):
        candidate = allocate_code(db, biz_type)
        if not exists(candidate):
            return candidate
    raise HTTPException(status_code=500, detail="编号生成失败，请稍后重试")


def preview_next_code(db: Session, biz_type: str) -> str:
    rule = _RULES.get(biz_type)
    if not rule:
        raise ValueError(f"未知编号类型: {biz_type}")
    period_key = datetime.now().strftime("%Y%m%d") if rule.daily else ""
    row = db.scalar(
        select(CodeSequence).where(
            CodeSequence.biz_type == biz_type,
            CodeSequence.period_key == period_key,
        )
    )
    return _format_code(rule, period_key, (row.last_value if row else 0) + 1)
