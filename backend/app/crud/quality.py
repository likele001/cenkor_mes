"""质量检测 CRUD"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.quality import (
    DefectCode,
    InspectionRecord,
    InspectionTemplate,
    InspectionTemplateItem,
)


# ========== 质检模板 ==========

def list_templates(db: Session, *, process_id: int | None = None,
                   offset: int = 0, limit: int = 100) -> list[InspectionTemplate]:
    stmt = (select(InspectionTemplate)
            .where(InspectionTemplate.is_active.is_(True))
            .options(selectinload(InspectionTemplate.items))
            .order_by(InspectionTemplate.id.desc())
            .offset(offset).limit(limit))
    if process_id is not None:
        stmt = stmt.where(InspectionTemplate.process_id == process_id)
    return list(db.scalars(stmt).all())


def get_template(db: Session, template_id: int) -> InspectionTemplate | None:
    return db.scalar(
        select(InspectionTemplate)
        .where(InspectionTemplate.id == template_id)
        .options(selectinload(InspectionTemplate.items))
    )


def find_template_for_process(db: Session, process_id: int) -> InspectionTemplate | None:
    """查找匹配工序的质检模板（优先 product 精确匹配，再退到仅 process 匹配）"""
    return db.scalar(
        select(InspectionTemplate)
        .where(
            InspectionTemplate.process_id == process_id,
            InspectionTemplate.is_active.is_(True),
        )
        .order_by(InspectionTemplate.product_id.isnot(None).desc(), InspectionTemplate.id.desc())
        .limit(1)
    )


def create_template(db: Session, data: dict) -> InspectionTemplate:
    items_data = data.pop("items", [])
    tmpl = InspectionTemplate(**data)
    db.add(tmpl)
    db.flush()
    for i, item in enumerate(items_data):
        db.add(InspectionTemplateItem(template_id=tmpl.id, seq=i + 1, **item))
    db.flush()
    return tmpl


def update_template(db: Session, template_id: int, data: dict) -> InspectionTemplate | None:
    tmpl = get_template(db, template_id)
    if not tmpl:
        return None
    items_data = data.pop("items", None)
    for k, v in data.items():
        setattr(tmpl, k, v)
    if items_data is not None:
        # 删除旧明细
        from sqlalchemy import delete
        db.execute(
            delete(InspectionTemplateItem).where(InspectionTemplateItem.template_id == tmpl.id)
        )
        db.flush()
        for i, item in enumerate(items_data):
            db.add(InspectionTemplateItem(template_id=tmpl.id, seq=i + 1, **item))
    db.flush()
    return tmpl


def delete_template(db: Session, template_id: int) -> bool:
    tmpl = get_template(db, template_id)
    if not tmpl:
        return False
    tmpl.is_active = False
    db.flush()
    return True


# ========== 缺陷代码 ==========

def list_defect_codes(db: Session, *, offset: int = 0, limit: int = 200, industry_code: str | None = None) -> list[DefectCode]:
    stmt = select(DefectCode).where(DefectCode.is_active.is_(True))
    if industry_code:
        stmt = stmt.where(DefectCode.industry_code == industry_code)
    stmt = stmt.order_by(DefectCode.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def get_defect_code(db: Session, code_id: int) -> DefectCode | None:
    return db.get(DefectCode, code_id)


def create_defect_code(db: Session, data: dict) -> DefectCode:
    dc = DefectCode(**data)
    db.add(dc)
    db.flush()
    return dc


def update_defect_code(db: Session, code_id: int, data: dict) -> DefectCode | None:
    dc = get_defect_code(db, code_id)
    if not dc:
        return None
    for k, v in data.items():
        setattr(dc, k, v)
    db.flush()
    return dc


def delete_defect_code(db: Session, code_id: int) -> bool:
    dc = get_defect_code(db, code_id)
    if not dc:
        return False
    dc.is_active = False
    db.flush()
    return True


# ========== 检测记录 ==========

def create_inspection_records(db: Session, audit_id: int,
                               records: list[dict]) -> list[InspectionRecord]:
    """批量创建检测记录"""
    out = []
    for r in records:
        rec = InspectionRecord(
            report_unit_audit_id=audit_id,
            template_item_id=r["template_item_id"],
            result=r.get("result", "pass"),
            measured_value=r.get("measured_value"),
            defect_code_id=r.get("defect_code_id"),
            remark=r.get("remark"),
        )
        db.add(rec)
        out.append(rec)
    db.flush()
    return out


def get_inspection_records_for_audit(db: Session, audit_id: int) -> list[InspectionRecord]:
    return list(db.scalars(
        select(InspectionRecord)
        .where(InspectionRecord.report_unit_audit_id == audit_id)
        .options(selectinload(InspectionRecord.template_item), selectinload(InspectionRecord.defect_code))
        .order_by(InspectionRecord.id.asc())
    ).all())
