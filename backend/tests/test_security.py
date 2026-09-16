# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""安全与合规加固的单元测试

覆盖：密码强度策略、生产环境 JWT 密钥 fail-fast、安全响应头中间件。
均为纯函数/中间件级测试，不依赖 MySQL 与 bcrypt 真实哈希，通过手动驱动 ASGI 直测。
"""
import asyncio

import pytest

from app.core.middleware import SECURITY_HEADERS, SecurityHeadersMiddleware
from app.core.security import ensure_secure_jwt_secret, validate_password_strength


# ── 密码强度策略 ──

def test_validate_password_accepts_normal():
    validate_password_strength("admin123")       # 8 位、多字符
    validate_password_strength("Cenkor@2026")    # 混合字符


def test_validate_password_rejects_short():
    with pytest.raises(ValueError, match=".*长度.*"):
        validate_password_strength("a")
    with pytest.raises(ValueError, match=".*长度.*"):
        validate_password_strength("12345")  # 5 位 < 默认 6
    with pytest.raises(ValueError, match=".*长度.*"):
        validate_password_strength("")


def test_validate_password_rejects_single_char_repeat():
    # 全为同一字符：不同字符数 < 3
    with pytest.raises(ValueError, match=".*过于简单.*"):
        validate_password_strength("121212")  # 长度足够但仅 2 种字符 -> 拒绝
    with pytest.raises(ValueError, match=".*过于简单.*"):
        validate_password_strength("aaaaaa")


# ── 生产环境 JWT 密钥 fail-fast ──

def _setenv(monkeypatch, app_env: str, secret: str):
    from app.core.config import settings
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "JWT_SECRET", secret)


def test_prod_weak_secret_fails(monkeypatch):
    _setenv(monkeypatch, "prod", "change_me")              # 默认/示例密钥
    with pytest.raises(RuntimeError):
        ensure_secure_jwt_secret()


def test_prod_short_secret_fails(monkeypatch):
    _setenv(monkeypatch, "prod", "s" * 16)                 # 长度不足 32
    with pytest.raises(RuntimeError):
        ensure_secure_jwt_secret()


def test_prod_strong_secret_ok(monkeypatch):
    _setenv(monkeypatch, "prod", "s" * 40)                 # 长度达标
    ensure_secure_jwt_secret()


def test_dev_weak_secret_not_blocked(monkeypatch):
    _setenv(monkeypatch, "dev", "change_me")               # 开发环境允许弱密钥
    ensure_secure_jwt_secret()


# ── 安全响应头中间件 ──

def _drive(middleware, headers: dict | None = None) -> tuple[int, dict]:
    """手动驱动 ASGI 中间件，返回 (status, headers_dict)，避免依赖 TestClient/httpx。"""
    async def inner_asgi(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]})
        await send({"type": "http.response.body", "body": b"{}"})

    return _run(middleware(inner_asgi))


def _run(app) -> tuple[int, dict]:
    scope = {"type": "http", "method": "GET", "path": "/api/health",
             "headers": [], "query_string": b"", "scheme": "http", "server": None,
             "client": None, "root_path": "", "http_version": "1.1", "app": app}
    out = {}

    async def _receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(message):
        if message["type"] == "http.response.start":
            out["status"] = message["status"]
            out["headers"] = {k.decode().lower(): v.decode() for k, v in message["headers"]}
        elif message["type"] == "http.response.body":
            out.setdefault("body", b"")
            out["body"] += message.get("body", b"")

    asyncio.run(app(scope, _receive, _send))
    return out.get("status"), out.get("headers", {})


def test_security_headers_applied():
    status, headers = _drive(SecurityHeadersMiddleware, {})
    assert status == 200
    for header, value in SECURITY_HEADERS.items():
        assert headers.get(header.lower()) == value


def test_security_headers_do_not_override_existing():
    # 若应用已设置 X-Frame-Options，中间件应保留原值（setdefault 语义）
    _, headers = _drive(SecurityHeadersMiddleware, {"X-Frame-Options": "SAMEORIGIN"})
    assert headers.get("x-frame-options") == "SAMEORIGIN"