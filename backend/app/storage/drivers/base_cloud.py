# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储驱动基类：把各家 SDK 适配到现有 sync Storage 协议。

子类只需实现 _validate / _upload / _delete / _presign_get 四个钩子；
key 生成、限流读取、sha256、StoredObject 组装统一在此完成。
resolve_path 对云端无意义，直接抛错（调用方在 driver!=local 时不会用到）。
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import BinaryIO
from uuid import uuid4

from app.storage._stream import buffer_stream
from app.storage.base import Storage, StoredObject


class CloudStorage(Storage, ABC):
    def __init__(self, creds: dict | None = None):
        creds = creds or {}
        self.endpoint = creds.get("endpoint", "")
        self.region = creds.get("region", "")
        self.bucket = creds.get("bucket", "")
        self.access_key = creds.get("access_key", "")
        self.secret_key = creds.get("secret_key", "")
        self.custom_domain = creds.get("custom_domain", "")
        self.prefix = creds.get("prefix", "")
        self._validate()

    # ── 子类需实现 ──
    @abstractmethod
    def _validate(self) -> None: ...

    @abstractmethod
    def _upload(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def _delete(self, key: str) -> None: ...

    @abstractmethod
    def _presign_get(self, key: str, expires: int, filename: str | None) -> str: ...

    @abstractmethod
    def _health_probe(self) -> dict: ...

    # ── 通用实现 ──
    def _object_key(self, filename: str) -> str:
        dt = datetime.now()
        ext = os.path.splitext(filename)[1].lower()
        key = f"{dt:%Y/%m/%d}/{uuid4().hex}{ext}"
        prefix = (self.prefix or "").strip("/")
        return f"{prefix}/{key}" if prefix else key

    def save(self, *, filename: str, content_type: str, stream: BinaryIO, max_size: int) -> StoredObject:
        bio, size, sha256 = buffer_stream(stream, max_size=max_size)
        key = self._object_key(filename)
        self._upload(key, bio.getvalue(), content_type)
        return StoredObject(driver=self.driver, key=key, size=size, sha256=sha256, abs_path=None)

    def delete(self, *, key: str) -> None:
        self._delete(key)

    def signed_url(self, *, key: str, content_type: str, expires: int = 3600, filename: str | None = None) -> str:
        return self._presign_get(key, int(expires), filename)

    def resolve_path(self, *, key: str):
        raise NotImplementedError(f"{self.driver} 云存储不支持 resolve_path")

    def health_check(self) -> dict:
        """连通性探测：调用 _health_probe，异常不外抛，统一返回 {ok, provider, ...}。"""
        try:
            detail = self._health_probe()
            return {"ok": True, "provider": self.driver, "detail": detail}
        except Exception as exc:  # noqa: BLE001 - 健康检查失败降级为 ok=False
            return {"ok": False, "provider": self.driver, "error": str(exc)[:300]}
