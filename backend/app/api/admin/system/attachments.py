from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.attachment import create_attachment, delete_attachment, get_attachment_by_id, list_attachments
from app.models.user import User
from app.services.attachment_delete import attachment_is_referenced
from app.services.attachment_media import attachment_out, attachment_play_url
from app.storage import get_active_storage, get_storage_for
from app.storage.base import StorageSizeExceeded
from app.utils.upload_mime import mime_allowed, resolve_upload_content_type


router = APIRouter(dependencies=[Depends(require_permissions(["attachment.view"]))])


@router.get("")
def list_api(
    keyword: str | None = Query(default=None),
    uploader_id: int | None = Query(default=None, ge=1),
    storage_driver: str | None = Query(default=None, max_length=32),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_attachments(
        db,
        keyword=keyword,
        uploader_id=uploader_id,
        storage_driver=storage_driver,
        offset=offset,
        limit=limit,
    )
    return ok({"items": [attachment_out(x, db=db) for x in items]})


def _allowed_mime_set() -> set[str]:
    items = [x.strip() for x in (settings.FILE_ALLOWED_MIME or "").split(",")]
    return {x for x in items if x}


@router.post("/upload")
def upload_api(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    allowed = _allowed_mime_set()
    content_type = resolve_upload_content_type(file.filename, file.content_type, allowed)
    if allowed and not mime_allowed(content_type, allowed):
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    max_size = settings.FILE_MAX_UPLOAD_SIZE
    storage = get_active_storage(db)
    try:
        stored = storage.save(
            filename=file.filename,
            content_type=content_type,
            stream=file.file,
            max_size=max_size,
        )
    except StorageSizeExceeded:
        cap_mb = max(1, max_size // (1024 * 1024))
        raise HTTPException(status_code=400, detail=f"文件过大，单文件不超过 {cap_mb}MB")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")

    att = create_attachment(
        db,
        uploader_id=user.id,
        storage_driver=stored.driver,
        storage_key=stored.key,
        original_filename=file.filename,
        content_type=content_type,
        size=stored.size,
        sha256=stored.sha256,
    )
    db.commit()
    db.refresh(att)
    return ok(attachment_out(att, db=db))


@router.get("/{attachment_id}")
def detail_api(
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    att = get_attachment_by_id(db, attachment_id=attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="文件不存在")
    return ok(attachment_out(att, db=db))


@router.get("/{attachment_id}/url")
def signed_url_api(
    attachment_id: int,
    expires: int = Query(default=3600, ge=60, le=86400),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    att = get_attachment_by_id(db, attachment_id=attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="文件不存在")
    play_url = attachment_play_url(att, db=db, expires=expires)
    return ok({"url": play_url, "play_url": play_url, "expires": expires})


@router.delete("/{attachment_id}")
def delete_api(
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    att = get_attachment_by_id(db, attachment_id=attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="文件不存在")
    if attachment_is_referenced(db, attachment_id=att.id):
        raise HTTPException(status_code=400, detail="附件已被报工或业务记录引用，无法删除")

    storage = get_storage_for(att.storage_driver, db)
    try:
        storage.delete(key=att.storage_key)
    except Exception:
        pass
    delete_attachment(db, att)
    db.commit()
    return ok(True)
