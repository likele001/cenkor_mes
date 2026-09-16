# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""阶段四安全测试：登录失败限流 + 上传活动内容防护。"""
import pytest

from app.core.config import settings
from app.services.login_ratelimit import (
    is_login_blocked,
    record_login_failure,
    reset_login_failures,
)
from app.utils.upload_mime import looks_like_web_content


# ── 登录失败限流（内存路径）──

@pytest.fixture(autouse=True)
def _monkey_rates(monkeypatch):
    """强制使用内存路径并设定宽松阈值，避免污染真实 Redis / 从外部影响其他测试。"""
    monkeypatch.setattr("app.services.login_ratelimit.get_redis", lambda: None)
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES", 5)
    monkeypatch.setattr(settings, "LOGIN_FAIL_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "LOGIN_LOCKOUT_SECONDS", 60)
    import app.services.login_ratelimit as lr
    monkeypatch.setattr(lr, "MAX_FAILURES", 5)
    monkeypatch.setattr(lr, "WINDOW_SECONDS", 60)
    monkeypatch.setattr(lr, "LOCKOUT_SECONDS", 60)


def test_rate_limit_blocks_after_threshold():
    ip = "203.0.113.9"
    reset_login_failures(ip)
    try:
        assert is_login_blocked(ip) is False
        for _ in range(5):
            record_login_failure(ip)
        assert is_login_blocked(ip) is True
    finally:
        reset_login_failures(ip)


def test_rate_limit_wind_up_under_threshold(monkeypatch):
    ip = "203.0.113.10"
    reset_login_failures(ip)
    try:
        for _ in range(4):  # 阈值=5，不应锁定
            record_login_failure(ip)
        assert is_login_blocked(ip) is False
    finally:
        reset_login_failures(ip)


def test_rate_limit_reset_on_success():
    ip = "203.0.113.11"
    reset_login_failures(ip)
    try:
        for _ in range(4):
            record_login_failure(ip)
        assert is_login_blocked(ip) is False
        reset_login_failures(ip)
        for _ in range(4):
            record_login_failure(ip)
        assert is_login_blocked(ip) is False  # 重置后重新计数
    finally:
        reset_login_failures(ip)


# ── 上传活动内容防护 ──

def test_looks_like_web_content_detects_html():
    assert looks_like_web_content(b"<html><body>hello</body></html>") is True
    assert looks_like_web_content(b"<!DOCTYPE html><script>alert(1)</script>") is True
    assert looks_like_web_content(b"<?xml version='1.0'?><svg onload=alert(1)>") is True
    assert looks_like_web_content(b"<script>fetch('/api')</script>") is True


def test_looks_like_web_content_allows_media():
    assert looks_like_web_content(b"\xff\xd8\xff\xe0 JFIF fake jpeg bytes") is False
    assert looks_like_web_content(b"\x89PNG\r\n\x1a\n binary png payload") is False
    # PDF 头不含活动标记
    pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>"
    assert looks_like_web_content(pdf + b" </obj>") is False