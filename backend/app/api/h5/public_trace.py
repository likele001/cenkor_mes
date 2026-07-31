"""客户公开溯源（无需登录）"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.responses import FileResponse, RedirectResponse

from app.core.deps import get_db
from app.core.response import ok
from app.crud.attachment import get_attachment_by_id
from app.crud.process_flow import get_piece_by_product_code
from app.crud.trace import get_trace_by_code
from app.models.report_unit import ReportUnit
from app.services.attachment_media import attachment_play_url
from app.services.trace_public import (
    build_public_trace_detail,
    build_trace_public_url)
from app.storage import get_storage_for
from sqlalchemy import select

router = APIRouter()


@router.get("/trace/{code}")
def public_trace_api(
    code: str,
    db: Session = Depends(get_db)):

    detail = build_public_trace_detail(db, code)
    if not detail:
        raise HTTPException(status_code=404, detail="未找到该产品的追溯信息")

    product_code = detail.get("product_code") or code
    detail["trace_url"] = build_trace_public_url(product_code)
    return ok(detail)


@router.get("/trace/media/{attachment_id}")
def public_trace_media_api(
    attachment_id: int,
    code: str = Query(min_length=1, max_length=64),
    url: bool = Query(False, alias="url"),
    db: Session = Depends(get_db)):
    normalized = code.strip().upper()
    piece = get_piece_by_product_code(db, normalized)
    trace = get_trace_by_code(db, normalized)
    piece_id = piece.id if piece else (trace.piece_id if trace else None)
    if not piece_id:
        raise HTTPException(status_code=404, detail="文件不存在")

    att = get_attachment_by_id(db, attachment_id=attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="文件不存在")

    units = db.scalars(
        select(ReportUnit).where(ReportUnit.piece_id == piece_id,
            ReportUnit.status == "qc_approved")
    ).all()
    allowed: set[int] = set()
    for unit in units:
        for raw in (unit.employee_attachment_ids, unit.qc_attachment_ids):
            if not raw:
                continue
            for part in str(raw).split(","):
                part = part.strip()
                if part.isdigit():
                    allowed.add(int(part))
    if attachment_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该文件")

    storage = get_storage_for(att.storage_driver, db)
    play_url = attachment_play_url(att, db=db, public_trace_code=code)

    if storage.driver != "local":
        if url:
            return ok({"url": play_url, "play_url": play_url})
        return RedirectResponse(play_url, status_code=302)

    path = storage.resolve_path(key=att.storage_key)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if url:
        return ok({"url": play_url, "play_url": play_url})
    return FileResponse(path, media_type=att.content_type)
