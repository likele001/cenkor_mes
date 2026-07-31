import os
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.storage.base import Storage, StorageError, StoredObject
from app.core.config import settings


class LocalStorage(Storage):
    driver = "local"

    def __init__(self):
        self.root = Path(settings.STORAGE_LOCAL_ROOT)

    def _object_key(self, *, filename: str) -> str:
        dt = datetime.now()
        ext = os.path.splitext(filename)[1].lower()
        return f"{dt:%Y/%m/%d}/{uuid4().hex}{ext}"

    def save(self, *, filename: str, content_type: str, stream: BinaryIO, max_size: int) -> StoredObject:
        key = self._object_key(filename=filename)
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        data = stream.read(max_size + 1)
        if len(data) > max_size:
            raise StorageError("文件大小超过限制")
        path.write_bytes(data)
        import hashlib
        sha256 = hashlib.sha256(data).hexdigest()
        return StoredObject(driver=self.driver, key=key, size=len(data), sha256=sha256, abs_path=path)

    def delete(self, *, key: str) -> None:
        path = self.root / key
        if path.exists():
            path.unlink()

    def signed_url(self, *, key: str, content_type: str, expires: int = 3600, filename: str | None = None) -> str:
        return f"{settings.PUBLIC_BASE_URL}/storage/{key}"

    def resolve_path(self, *, key: str) -> Path:
        return self.root / key
