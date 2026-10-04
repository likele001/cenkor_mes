# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""腾讯云 COS 驱动（cos-python-sdk-v5）。"""
from __future__ import annotations

from qcloud_cos import CosConfig, CosS3Client

from app.storage.drivers.base_cloud import CloudStorage


class TencentCOSStorage(CloudStorage):
    driver = "tencent"

    def _validate(self) -> None:
        if not (self.region and self.bucket and self.access_key and self.secret_key):
            raise ValueError("腾讯 COS 凭据不完整（需 region/bucket/access_key/secret_key）")

    def _client(self) -> CosS3Client:
        cfg = CosConfig(Region=self.region, SecretId=self.access_key, SecretKey=self.secret_key)
        return CosS3Client(cfg)

    def _upload(self, key: str, data: bytes, content_type: str) -> None:
        self._client().put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def _delete(self, key: str) -> None:
        self._client().delete_object(Bucket=self.bucket, Key=key)

    def _presign_get(self, key: str, expires: int, filename: str | None) -> str:
        return self._client().get_presigned_url("get", Bucket=self.bucket, Key=key, Expired=expires)

    def _health_probe(self) -> dict:
        self._client().list_objects(Bucket=self.bucket, MaxKeys=1)
        return {"bucket": self.bucket, "region": self.region}
