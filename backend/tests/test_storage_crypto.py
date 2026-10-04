# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储凭据加解密 + 存储工厂驱动选择 单元测试"""
import base64

import pytest

from app.storage import crypto
from app.storage.factory import build_storage, get_active_storage, register_driver
from app.storage.local import LocalStorage


# ── crypto ──

def test_encrypt_decrypt_roundtrip():
    token = crypto.encrypt("my-secret-access-key")
    assert token and token != "my-secret-access-key"
    assert crypto.decrypt(token) == "my-secret-access-key"


def test_encrypt_none_and_empty():
    assert crypto.encrypt(None) is None
    assert crypto.decrypt("") == ""
    assert crypto.decrypt(None) == ""


def test_ciphertext_is_randomized():
    a = crypto.encrypt("same")
    b = crypto.encrypt("same")
    assert a != b  # 随机 nonce 保证相同明文密文不同
    assert crypto.decrypt(a) == crypto.decrypt(b) == "same"


def test_decrypt_tampered_raises():
    token = crypto.encrypt("hello")
    raw = bytearray(base64.b64decode(token.encode("ascii")))
    raw[-1] ^= 0xFF  # 破坏 GCM 认证标签
    bad = base64.b64encode(bytes(raw)).decode("ascii")
    with pytest.raises(Exception):
        crypto.decrypt(bad)


def test_mask():
    assert crypto.mask("AKID1234567890") == "AKI••••7890"
    assert crypto.mask("") == ""
    assert crypto.mask("short") == "••••••"


# ── factory ──

def test_build_storage_local_default():
    assert isinstance(build_storage("local"), LocalStorage)


def test_build_storage_unknown_falls_back_local():
    # 未注册的云驱动应降级为 local，不抛异常（向后兼容历史空壳配置）
    assert isinstance(build_storage("aliyun"), LocalStorage)
    assert isinstance(get_active_storage(), LocalStorage)


def test_register_driver_used_by_build():
    class DummyDriver(LocalStorage):
        driver = "dummy"

    register_driver("dummy", DummyDriver)
    assert isinstance(build_storage("dummy"), DummyDriver)
