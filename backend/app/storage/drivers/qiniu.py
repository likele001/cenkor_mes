# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""七牛云 Kodo 驱动（qiniu）。

七牛下载签名依赖"空间绑定的已认证域名"（custom_domain），故 custom_domain 必填。
"""
from __future__ import annotations

import qiniu
from qiniu import Auth, BucketManager, put_data

from app.storage.drivers.base_cloud import CloudStorage


class QiniuStorage(CloudStorage):
    driver = "qiniu"

    def _validate(self) -> None:
        if not (self.bucket and self.access_key and self.secret_key and self.custom_domain):
            raise ValueError("七牛凭据不完整（需 bucket/access_key/secret_key/custom_domain）")

    def _auth(self) -> Auth:
        return Auth(self.access_key, self.secret_key)

    def _upload(self, key: str, data: bytes, content_type: str) -> None:
        token = self._auth().upload_token(self.bucket, key)
        _, err = put_data(token, key, data, mime_type=content_type)
        if err:
            raise RuntimeError(f"七牛上传失败: {err}")

    def _delete(self, key: str) -> None:
        BucketManager(self._auth()).delete(self.bucket, key)

    def _presign_get(self, key: str, expires: int, filename: str | None) -> str:
        base_url = f"{self.custom_domain.rstrip('/')}/{key}"
        return self._auth().private_download_url(base_url, expires=expires)

    def _health_probe(self) -> dict:
        # 列举空间内 1 个对象即可验证凭据与连通性
        BucketManager(self._auth()).list(self.bucket, limit=1)
        return {"bucket": self.bucket, "domain": self.custom_domain}
