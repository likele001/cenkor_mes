# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""阿里云 OSS 驱动（oss2）。"""
from __future__ import annotations

import oss2

from app.storage.drivers.base_cloud import CloudStorage


class AliyunOSSStorage(CloudStorage):
    driver = "aliyun"

    def _validate(self) -> None:
        if not (self.endpoint and self.bucket and self.access_key and self.secret_key):
            raise ValueError("阿里 OSS 凭据不完整（需 endpoint/bucket/access_key/secret_key）")

    def _bucket(self) -> oss2.Bucket:
        auth = oss2.Auth(self.access_key, self.secret_key)
        return oss2.Bucket(auth, self.endpoint, self.bucket)

    def _upload(self, key: str, data: bytes, content_type: str) -> None:
        self._bucket().put_object(key, data, headers={"Content-Type": content_type})

    def _delete(self, key: str) -> None:
        self._bucket().delete_object(key)

    def _presign_get(self, key: str, expires: int, filename: str | None) -> str:
        params = None
        if filename:
            params = {"response-content-disposition": f'inline; filename="{filename}"'}
        return self._bucket().sign_url("GET", key, expires, params=params)

    def _health_probe(self) -> dict:
        self._bucket().list_objects(max_keys=1)
        return {"bucket": self.bucket, "endpoint": self.endpoint}
