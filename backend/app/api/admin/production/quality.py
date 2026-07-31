"""质量检测 API：质检模板 + 缺陷代码管理"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok, fail
from app.crud.quality import (
    create_defect_code,
    create_template,
    delete_defect_code,
    delete_template,
    get_defect_code,
    get_template,
    list_defect_codes,
    list_templates,
    update_defect_code,
    update_template,
)
from app.models.user import User
from app.schemas.quality import (
    DefectCodeCreateIn,
    DefectCodeUpdateIn,
    TemplateIn,
    TemplateUpdateIn,
)
from app.tasks._sync_excel import make_excel_response

router = APIRouter(dependencies=[Depends(require_permissions(["report.audit"]))])


# ── 质检模板 ──


@router.get("/inspection-templates")
def list_templates_api(
    process_id: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_templates(db, process_id=process_id, offset=offset, limit=limit)
    return ok({
        "items": [_tmpl_out(t) for t in items],
    })


@router.get("/inspection-templates/{template_id}")
def get_template_api(template_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = get_template(db, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ok(_tmpl_out(t))


@router.post("/inspection-templates")
def create_template_api(payload: TemplateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = create_template(db, payload.model_dump())
    return ok(_tmpl_out(t))


@router.put("/inspection-templates/{template_id}")
def update_template_api(template_id: int, payload: TemplateIn,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = update_template(db, template_id, payload.model_dump())
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ok(_tmpl_out(t))


@router.delete("/inspection-templates/{template_id}")
def delete_template_api(template_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ok_ = delete_template(db, template_id)
    if not ok_:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ok({"deleted": True})


def _tmpl_out(t) -> dict:
    return {
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "description": t.description,
        "process_id": t.process_id,
        "product_id": t.product_id,
        "is_active": t.is_active,
        "items": [
            {
                "id": i.id,
                "seq": i.seq,
                "item_name": i.item_name,
                "item_type": i.item_type,
                "standard_value": i.standard_value,
                "upper_limit": i.upper_limit,
                "lower_limit": i.lower_limit,
                "unit": i.unit,
                "is_required": i.is_required,
                "remark": i.remark,
            }
            for i in (t.items or [])
        ],
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


# ── 缺陷代码 ──


@router.get("/defect-codes")
def list_defect_codes_api(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    industry_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_defect_codes(db, offset=offset, limit=limit, industry_code=industry_code)
    return ok({
        "items": [
            {
                "id": d.id,
                "code": d.code,
                "name": d.name,
                "severity": d.severity,
                "description": d.description,
                "is_active": d.is_active,
            }
            for d in items
        ]
    })


@router.get("/defect-codes/export")
def export_defect_codes_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_defect_codes(db, offset=0, limit=999999)
    rows = []
    for d in items:
        rows.append([d.code, d.name, d.severity, d.description or "", "是" if d.is_active else "否"])
    return make_excel_response(
        headers=["缺陷代码", "名称", "严重级别", "描述", "启用"],
        rows=rows,
        filename="defect_codes.xlsx",
        sheet_name="缺陷代码",
    )


@router.post("/defect-codes")
def create_defect_code_api(payload: DefectCodeCreateIn, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    d = create_defect_code(db, payload.model_dump())
    return ok({"id": d.id})


@router.put("/defect-codes/{code_id}")
def update_defect_code_api(code_id: int, payload: DefectCodeUpdateIn,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = update_defect_code(db, code_id, payload.model_dump())
    if not d:
        raise HTTPException(status_code=404, detail="缺陷代码不存在")
    return ok({"id": d.id})


@router.delete("/defect-codes/{code_id}")
def delete_defect_code_api(code_id: int, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    ok_ = delete_defect_code(db, code_id)
    if not ok_:
        raise HTTPException(status_code=404, detail="缺陷代码不存在")
    return ok({"deleted": True})
