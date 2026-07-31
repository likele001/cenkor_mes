from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.process import create_process, get_process_by_code, get_process_by_id, list_processes, update_process
from app.models.user import User
from app.schemas.process import ProcessCreateIn, ProcessUpdateIn
from app.services.code_generator import BizType, resolve_code
from app.crud.process_skill import list_process_skills, replace_process_skills
from pydantic import BaseModel, Field

from app.services.display_label import process_display_name
from app.tasks._sync_excel import make_excel_response


class ProcessSkillsIn(BaseModel):
    skill_ids: list[int] = Field(default_factory=list)


router = APIRouter(dependencies=[Depends(require_permissions(["process.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "name": x.name,
        "display_name": process_display_name(x.name, x.code),
        "workshop": x.workshop,
        "std_minutes": x.std_minutes,
        "is_active": x.is_active,
        "industry_code": x.industry_code,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    include_inactive: bool = Query(default=False),
    industry_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_processes(db, keyword=keyword, offset=offset, limit=limit, include_inactive=include_inactive, industry_code=industry_code)
    return ok({"items": [_out(x) for x in items]})


@router.get("/export")
def export_processes_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_processes(db, keyword=None, offset=0, limit=999999, include_inactive=True)
    headers = ["编码", "名称", "车间", "标准工时(分钟)", "状态"]
    rows = [[i.code, i.name, i.workshop or "", str(i.std_minutes or ""), "启用" if i.is_active else "停用"] for i in items]
    return make_excel_response(headers, rows, "processes.xlsx", "工序")


@router.post("")
def create_api(payload: ProcessCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    process_code = resolve_code(
        db,
        biz_type=BizType.PROCESS,
        code=payload.code,
        exists=lambda c: get_process_by_code(db, c) is not None,
        duplicate_msg="工序编码已存在",
    )
    item = create_process(
        db,
        code=process_code,
        name=payload.name,
        workshop=payload.workshop,
        std_minutes=payload.std_minutes,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{process_id}")
def get_api(process_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_process_by_id(db, process_id=process_id)
    if not item:
        raise HTTPException(status_code=404, detail="工序不存在")
    return ok(_out(item))


@router.put("/{process_id}")
def update_api(process_id: int, payload: ProcessUpdateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_process_by_id(db, process_id=process_id)
    if not item:
        raise HTTPException(status_code=404, detail="工序不存在")
    if payload.code is not None:
        exists = get_process_by_code(db, code=payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="工序编码已存在")
    update_process(
        db,
        item,
        code=payload.code,
        name=payload.name,
        workshop=payload.workshop,
        std_minutes=payload.std_minutes,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{process_id}")
def delete_api(process_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_process_by_id(db, process_id=process_id)
    if not item:
        raise HTTPException(status_code=404, detail="工序不存在")
    update_process(db, item, is_active=False)
    db.commit()
    return ok()


@router.get("/{process_id}/skills")
def get_skills_api(process_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_process_by_id(db, process_id=process_id)
    if not item:
        raise HTTPException(status_code=404, detail="工序不存在")
    skills = list_process_skills(db, process_id)
    return ok({"items": [{"id": s.id, "code": s.code, "name": s.name} for s in skills]})


@router.put("/{process_id}/skills")
def set_skills_api(
    process_id: int,
    payload: ProcessSkillsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_process_by_id(db, process_id=process_id)
    if not item:
        raise HTTPException(status_code=404, detail="工序不存在")
    try:
        ids = replace_process_skills(db, process_id, payload.skill_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    skills = list_process_skills(db, process_id)
    return ok({"skill_ids": ids, "items": [{"id": s.id, "code": s.code, "name": s.name} for s in skills]})
