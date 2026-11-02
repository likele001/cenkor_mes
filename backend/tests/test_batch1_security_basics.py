# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""飞书回调来源校验、健康检查数据库探测、默认管理员口令。"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.api.feishu import router as feishu_router
from app.core.config import settings
from app.services.feishu.callbacks import parse_event_body
from app.models.user import User


# ── 飞书回调 ─────────────────────────────────────────────────────────


def _encrypt(encrypt_key: str, payload: dict) -> str:
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    iv = os.urandom(16)
    padder = PKCS7(128).padder()
    data = padder.update(json.dumps(payload).encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(data) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode("ascii")


def test_accepts_plaintext_when_no_security_configured():
    body = {"header": {"event_type": "x"}, "event": {}}
    assert parse_event_body(body) == body


def test_rejects_plaintext_when_encrypt_key_configured():
    with pytest.raises(ValueError, match="未加密"):
        parse_event_body({"header": {"event_type": "x"}}, encrypt_key="secret")


def test_decrypts_and_checks_v2_header_token():
    payload = {"header": {"event_type": "x", "token": "tok-1"}, "event": {"a": 1}}
    body = {"encrypt": _encrypt("secret", payload)}
    assert parse_event_body(body, encrypt_key="secret", verification_token="tok-1") == payload


def test_checks_v1_top_level_token():
    payload = {"token": "tok-1", "type": "url_verification", "challenge": "abc"}
    assert parse_event_body(payload, verification_token="tok-1")["challenge"] == "abc"


def test_rejects_token_mismatch():
    payload = {"header": {"event_type": "x", "token": "wrong"}}
    with pytest.raises(ValueError, match="Verification Token"):
        parse_event_body(payload, verification_token="tok-1")


def test_rejects_missing_token_when_required():
    with pytest.raises(ValueError, match="Verification Token"):
        parse_event_body({"header": {"event_type": "x"}}, verification_token="tok-1")


def test_events_endpoint_turns_security_failure_into_403(monkeypatch):
    class _Request:
        async def json(self):
            return {"header": {"event_type": "x"}}

    monkeypatch.setattr(feishu_router, "_resolve_feishu_security", lambda db: ("secret", ""))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(feishu_router.feishu_events_api(_Request(), db=None))
    assert exc.value.status_code == 403


# ── 健康检查 ─────────────────────────────────────────────────────────


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args, **kwargs):
        return None


class _Engine:
    def __init__(self, fail: bool = False):
        self.fail = fail

    def connect(self):
        if self.fail:
            raise RuntimeError("db down")
        return _Conn()


def test_health_ok_when_db_reachable(monkeypatch):
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "engine", _Engine())
    result = main_mod.health()
    assert isinstance(result, dict)
    assert result["data"]["db"] == "up"
    assert result["data"]["status"] == "ok"


def test_health_503_when_db_unreachable(monkeypatch):
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "engine", _Engine(fail=True))
    result = main_mod.health()
    assert isinstance(result, JSONResponse)
    assert result.status_code == 503
    payload = json.loads(result.body)
    assert payload["data"]["db"] == "down"
    assert payload["data"]["status"] == "degraded"


# ── 默认管理员 ───────────────────────────────────────────────────────


def _ensure_admin(session, monkeypatch, *, app_env: str, password: str):
    from app import main as main_mod

    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "ADMIN_INIT_PASSWORD", password)
    main_mod._ensure_default_admin(session)
    session.flush()
    return session.query(User).filter(User.username == "admin").one_or_none()


def test_dev_creates_default_admin(session, admin_role, monkeypatch):
    admin = _ensure_admin(session, monkeypatch, app_env="dev", password="")
    assert admin is not None
    assert admin.is_superuser is True
    assert any(r.code == "admin" for r in admin.roles)


def test_non_dev_without_password_skips_admin(session, admin_role, monkeypatch):
    admin = _ensure_admin(session, monkeypatch, app_env="prod", password="")
    assert admin is None


def test_non_dev_with_short_password_skips_admin(session, admin_role, monkeypatch):
    admin = _ensure_admin(session, monkeypatch, app_env="prod", password="123")
    assert admin is None


def test_non_dev_with_configured_password_creates_admin(session, admin_role, monkeypatch):
    admin = _ensure_admin(session, monkeypatch, app_env="prod", password="Cenkor#2026")
    assert admin is not None
    assert admin.is_superuser is True


def test_existing_admin_is_not_recreated(session, admin_role, monkeypatch):
    first = _ensure_admin(session, monkeypatch, app_env="dev", password="")
    session.commit()
    second = _ensure_admin(session, monkeypatch, app_env="prod", password="")
    assert second is not None
    assert second.id == first.id
