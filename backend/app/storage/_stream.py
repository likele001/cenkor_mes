from __future__ import annotations

import hashlib
from io import BytesIO
from typing import BinaryIO

from app.storage.base import StorageSizeExceeded


def read_limited_stream(stream: BinaryIO, *, max_size: int) -> tuple[bytes, int, str]:
    sha256 = hashlib.sha256()
    size = 0
    chunks: list[bytes] = []
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_size:
            raise StorageSizeExceeded("文件过大")
        sha256.update(chunk)
        chunks.append(chunk)
    data = b"".join(chunks)
    return data, size, sha256.hexdigest()


def buffer_stream(stream: BinaryIO, *, max_size: int) -> tuple[BytesIO, int, str]:
    data, size, digest = read_limited_stream(stream, max_size=max_size)
    bio = BytesIO(data)
    bio.seek(0)
    return bio, size, digest
