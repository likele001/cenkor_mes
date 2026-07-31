from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from starlette.responses import FileResponse, RedirectResponse

from app.services.report_media_settings import get_report_media_settings
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.utils.upload_mime import mime_allowed, resolve_upload_content_type
from app.crud.attachment import create_attachment, get_attachment_by_id
from app.models.user import User
from app.services.attachment_media import attachment_out, attachment_play_url
from app.storage import get_active_storage, get_storage_for
from app.storage.local import LocalStorage
from app.crud.platform_setting import get_all_settings
from io import BytesIO
from app.storage.base import StorageSizeExceeded


router = APIRouter()


def _allowed_mime_set() -> set[str]:
    items = [x.strip() for x in (settings.FILE_ALLOWED_MIME or "").split(",")]
    return {x for x in items if x}


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    purpose: str | None = Query(default=None, description="report_media=报工/审核现场拍摄限额"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    allowed = _allowed_mime_set()
    content_type = resolve_upload_content_type(file.filename, file.content_type, allowed)
    if allowed and not mime_allowed(content_type, allowed):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型（{file.content_type or '未知'}），允许：图片、PDF、MP4/MOV 等视频",
        )

    max_size = settings.FILE_MAX_UPLOAD_SIZE
    if (purpose or "").strip() == "report_media":
        cfg = get_report_media_settings(db)
        is_video = content_type.startswith("video/")
        if is_video:
            max_size = min(max_size, int(cfg["max_video_bytes"]))
        if file.file:
            file.file.seek(0, 2)
            hinted = file.file.tell()
            file.file.seek(0)
            if hinted > max_size:
                cap_mb = max(1, max_size // (1024 * 1024))
                raise HTTPException(
                    status_code=400,
                    detail=f"文件过大，报工视频单段不超过 {cap_mb}MB（请缩短拍摄时长）",
                )

    # 先读取完整文件到内存（支持双备份）
    file.file.seek(0)
    file_bytes = file.file.read()
    file_stream = BytesIO(file_bytes)

    storage = get_active_storage(db)
    try:
        stored = storage.save(
            filename=file.filename,
            content_type=content_type,
            stream=file_stream,
            max_size=max_size,
        )
    except StorageSizeExceeded:
        cap_mb = max(1, max_size // (1024 * 1024))
        raise HTTPException(status_code=400, detail=f"文件过大，单文件不超过 {cap_mb}MB")
    except Exception:
        raise HTTPException(status_code=500, detail="上传失败")

    # 本地备份（如果开启且主存储不是本地）
    try:
        settings_raw = get_all_settings(db)
        local_backup_enabled = str(settings_raw.get("storage_local_backup_enabled", "false")).lower() in ("1", "true", "yes", "on")
        if local_backup_enabled and storage.driver != "local":
            local_root = settings_raw.get("storage_local_backup_root") or settings.STORAGE_LOCAL_ROOT
            local_storage = LocalStorage(root=local_root)
            local_storage.save(
                filename=file.filename,
                content_type=content_type,
                stream=BytesIO(file_bytes),
                max_size=max_size,
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"本地备份失败: {e}")

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
def get_file(
    attachment_id: int,
    download: bool = Query(False),
    url: bool = Query(False, alias="url"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    att = get_attachment_by_id(db, attachment_id=attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="文件不存在")

    storage = get_storage_for(att.storage_driver, db)
    play_url = attachment_play_url(att, db=db)

    if storage.driver != "local":
        if url or not download:
            return ok({"url": play_url, "play_url": play_url}) if url else RedirectResponse(play_url, status_code=302)
        return RedirectResponse(play_url, status_code=302)

    path = storage.resolve_path(key=att.storage_key)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if path.stat().st_size <= 0:
        raise HTTPException(status_code=404, detail="文件已损坏或为空")

    if url:
        return ok({"url": play_url, "play_url": play_url})

    disposition = "attachment" if download else "inline"
    headers = {"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(att.original_filename)}"}
    return FileResponse(path, media_type=att.content_type, headers=headers)
