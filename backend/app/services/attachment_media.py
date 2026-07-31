"""附件访问 URL 与响应辅助"""

from __future__ import annotations

from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.storage.factory import get_storage_for


def api_public_base() -> str:
    base = (settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if base:
        return base
    h5 = (settings.H5_PUBLIC_BASE_URL or "").strip().rstrip("/")
    return h5


def attachment_play_url(
    att: Attachment,
    *,
    db: Session | None = None,
    public_trace_code: str | None = None,
    expires: int = 3600,
) -> str:
    storage = get_storage_for(att.storage_driver, db)
    if storage.driver == "local":
        if public_trace_code:
            path = f"/api/h5/public/trace/media/{att.id}?code={quote(public_trace_code.strip(), safe='')}"
            base = api_public_base()
            return f"{base}{path}" if base else path
        return f"/api/files/{att.id}"

    return storage.signed_url(
        key=att.storage_key,
        content_type=att.content_type,
        expires=expires,
        filename=att.original_filename,
    )


def attachment_out(att: Attachment, *, db: Session | None = None, public_trace_code: str | None = None) -> dict:
    play_url = attachment_play_url(att, db=db, public_trace_code=public_trace_code)
    return {
        "id": att.id,
        "uploader_id": att.uploader_id,
        "storage_driver": att.storage_driver,
        "storage_key": att.storage_key,
        "original_filename": att.original_filename,
        "content_type": att.content_type,
        "size": att.size,
        "sha256": att.sha256,
        "created_at": att.created_at,
        "url": f"/api/files/{att.id}",
        "play_url": play_url,
    }
