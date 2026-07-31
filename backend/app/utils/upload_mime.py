"""上传文件 MIME 校验与按扩展名纠偏（手机视频常为 quicktime / octet-stream）"""

from __future__ import annotations

from pathlib import Path

# 扩展名 → 标准 MIME
EXT_TO_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".3gp": "video/3gpp",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
}

DEFAULT_ALLOWED_MIME = (
    "image/jpeg,image/png,image/webp,application/pdf,"
    "video/mp4,video/quicktime,video/webm,video/3gpp,video/x-msvideo"
)


def guess_mime_by_filename(filename: str) -> str | None:
    ext = Path(filename or "").suffix.lower()
    return EXT_TO_MIME.get(ext)


def resolve_upload_content_type(filename: str, content_type: str | None, allowed: set[str]) -> str:
    """浏览器上报类型不在白名单时，按扩展名尝试匹配（常见于 iPhone .mov）。"""
    raw = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    guessed = guess_mime_by_filename(filename)
    if raw in allowed:
        return raw
    if guessed and guessed in allowed:
        return guessed
    if raw in ("application/octet-stream", "binary/octet-stream") and guessed:
        return guessed
    return raw


def mime_allowed(content_type: str, allowed: set[str]) -> bool:
    return not allowed or content_type in allowed
