from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.admin.system.common import write_op_log
from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.attachment import create_attachment
from app.crud.print_template import (
    create_print_template,
    html_to_pdf_bytes,
    get_print_template_by_code,
    get_print_template_by_id,
    list_print_templates,
    render_print_template,
    update_print_template,
)
from app.models.user import User
from app.schemas.print_template import PrintTemplateCreateIn, PrintTemplateRenderIn, PrintTemplateUpdateIn
from app.storage import get_active_storage


router = APIRouter(dependencies=[Depends(require_permissions(["print_template.manage"]))])


def _out(x) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "name": x.name,
        "template_type": x.template_type,
        "content": x.content,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    template_type: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_print_templates(
        db,
        keyword=keyword,
        template_type=template_type,
        include_inactive=include_inactive,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [_out(x) for x in items]})


@router.post("")
def create_api(
    payload: PrintTemplateCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exists = get_print_template_by_code(db, code=payload.code)
    if exists:
        raise HTTPException(status_code=400, detail="模板编码已存在")
    item = create_print_template(
        db,
        code=payload.code,
        name=payload.name,
        template_type=payload.template_type,
        content=payload.content,
        is_active=payload.is_active,
    )
    write_op_log(
        db,
        request,
        user,
        module="system.print_template",
        action="create",
        object_type="print_template",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.get("/{template_id}")
def get_api(template_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_print_template_by_id(db, template_id=template_id)
    if not item:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ok(_out(item))


@router.put("/{template_id}")
def update_api(
    template_id: int,
    payload: PrintTemplateUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_print_template_by_id(db, template_id=template_id)
    if not item:
        raise HTTPException(status_code=404, detail="模板不存在")
    if payload.code is not None:
        exists = get_print_template_by_code(db, code=payload.code)
        if exists and exists.id != item.id:
            raise HTTPException(status_code=400, detail="模板编码已存在")
    update_print_template(
        db,
        item,
        code=payload.code,
        name=payload.name,
        template_type=payload.template_type,
        content=payload.content,
        is_active=payload.is_active,
    )
    write_op_log(
        db,
        request,
        user,
        module="system.print_template",
        action="update",
        object_type="print_template",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    db.refresh(item)
    return ok(_out(item))


@router.delete("/{template_id}")
def delete_api(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_print_template_by_id(db, template_id=template_id)
    if not item:
        raise HTTPException(status_code=404, detail="模板不存在")
    update_print_template(db, item, is_active=False)
    write_op_log(
        db,
        request,
        user,
        module="system.print_template",
        action="disable",
        object_type="print_template",
        object_id=item.id,
        detail=f"{item.code}|{item.name}",
    )
    db.commit()
    return ok()


@router.post("/{template_id}/render")
def render_api(
    template_id: int,
    payload: PrintTemplateRenderIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_print_template_by_id(db, template_id=template_id)
    if not item:
        raise HTTPException(status_code=404, detail="模板不存在")
    html = render_print_template(item.content, payload.data or {})
    return ok({"html": html})


@router.post("/{template_id}/render-pdf")
def render_pdf_api(
    template_id: int,
    payload: PrintTemplateRenderIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_print_template_by_id(db, template_id=template_id)
    if not item:
        raise HTTPException(status_code=404, detail="模板不存在")
    html = render_print_template(item.content, payload.data or {})
    try:
        pdf_bytes = html_to_pdf_bytes(html)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = f"{item.code or 'template'}_{item.id}.pdf"
    storage = get_active_storage(db)
    bio = BytesIO(pdf_bytes)
    stored = storage.save(
        filename=filename,
        content_type="application/pdf",
        stream=bio,
        max_size=settings.FILE_MAX_UPLOAD_SIZE,
    )
    att = create_attachment(
        db,
        uploader_id=user.id,
        storage_driver=stored.driver,
        storage_key=stored.key,
        original_filename=filename,
        content_type="application/pdf",
        size=stored.size,
        sha256=stored.sha256,
    )
    db.commit()
    db.refresh(att)
    return ok({"attachment_id": att.id, "filename": att.original_filename, "url": f"/api/files/{att.id}?download=true&filename={quote(att.original_filename)}"})
