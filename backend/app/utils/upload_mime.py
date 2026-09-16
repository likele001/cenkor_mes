# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
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


# 活动网页内容标记：若出现在图片/视频/PDF 文件头部，极可能是伪装成媒体的
# HTML/SVG/JS 恶意负载（存储型 XSS 常用手段）。PDF 正常头部不含这些标记。
_ACTIVE_MARKERS = (
    b"<script",
    b"<html",
    b"<!doctype html",
    b"<?xml",
    b"<svg",
)


def looks_like_web_content(data: bytes, peek: int = 4096) -> bool:
    """检查文件头部是否包含 HTML/SVG/脚本标记。

    仅用于非文本类媒体（图片/视频/PDF）上传的二次防护；若声明为图片/视频/PDF
    但头部嵌入网页内容，判定为潜在可执行负载，应拒绝。
    """
    head = (data or b"")[:peek].lower()
    return any(marker in head for marker in _ACTIVE_MARKERS)
