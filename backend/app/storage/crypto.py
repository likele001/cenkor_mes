# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储凭据 AES-256-GCM 加解密。

密钥派生自现有 JWT_SECRET（不引入独立密钥体系）：
    key = SHA256(JWT_SECRET).digest()
密文格式：base64(nonce[12] | ciphertext | tag[16])

支持密钥轮换：加密用当前 key，解密依次回退 JWT_SECRET_OLD 中的历史 key。
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_LEN = 12


def _keys() -> tuple[bytes, ...]:
    """所有有效密钥的派生结果，最新优先（索引 0 = 当前加密用）。"""
    secrets = [
        getattr(settings, "JWT_SECRET", ""),
        getattr(settings, "JWT_SECRET_OLD", ""),
    ]
    return tuple(hashlib.sha256(s.encode("utf-8")).digest() for s in secrets if s)


def encrypt(plaintext: str | None) -> str | None:
    """加密明文凭据；None 原样返回。使用随机 nonce，相同明文密文不同。"""
    if plaintext is None:
        return None
    keys = _keys()
    if not keys:
        raise ValueError("未配置 JWT_SECRET，无法加密凭据")
    aes = AESGCM(keys[0])
    nonce = os.urandom(_NONCE_LEN)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(token: str | None) -> str:
    """解密密文；空值返回空串。依次尝试当前与历史密钥。"""
    if not token:
        return ""
    raw = base64.b64decode(token.encode("ascii"))
    nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    last_exc: Exception | None = None
    for key in _keys():
        try:
            return AESGCM(key).decrypt(nonce, ct, associated_data=None).decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - 认证失败/密钥不匹配，尝试下一个
            last_exc = exc
            continue
    if last_exc is not None:
        raise last_exc
    raise ValueError("未配置 JWT_SECRET，无法解密凭据")


def mask(value: str, head: int = 3, tail: int = 4) -> str:
    """脱敏展示：保留首 head、尾 tail 个字符，中间以 • 填充。"""
    if not value:
        return ""
    if len(value) <= head + tail:
        return "•" * max(len(value), 6)
    return f"{value[:head]}{'•' * 4}{value[-tail:]}"
