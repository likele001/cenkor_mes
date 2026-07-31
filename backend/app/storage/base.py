from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol


class StorageError(Exception):
    pass


class StorageSizeExceeded(StorageError):
    pass


@dataclass(frozen=True)
class StoredObject:
    driver: str
    key: str
    size: int
    sha256: str
    abs_path: Path | None = None


class Storage(Protocol):
    driver: str

    def save(
        self,
        *,
        filename: str,
        content_type: str,
        stream: BinaryIO,
        max_size: int,
    ) -> StoredObject: ...

    def delete(self, *, key: str) -> None: ...

    def signed_url(
        self,
        *,
        key: str,
        content_type: str,
        expires: int = 3600,
        filename: str | None = None,
    ) -> str: ...

    def resolve_path(self, *, key: str) -> Path: ...
