# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""登录验证码开关（独立版补齐）回归测试。

守住三个最容易回归的点：
1. 写接口真的把值写进 platform_settings，读取侧 is_login_captcha_enabled 能看见；
2. 路由确实挂在 /admin/system/login-captcha（漏挂载时后台按钮会 404）；
3. 开启后登录校验拒绝缺参，关闭后放行。
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.admin.system import login_captcha as lc
from app.api.admin.system.router import router as admin_system_router
from app.services.login_captcha import assert_login_captcha, is_login_captcha_enabled


def _request():
    return Request({
        "type": "http",
        "method": "PUT",
        "path": "/api/admin/system/login-captcha",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    })


def _save(session, monkeypatch, enabled: bool):
    # 操作日志是横切关注点，本用例只关心开关读写
    monkeypatch.setattr(lc, "write_op_log", lambda *a, **kw: None)
    user = SimpleNamespace(id=1, username="admin")
    return lc.save_login_captcha_settings_api(
        lc.LoginCaptchaSettingsIn(enabled=enabled),
        _request(),
        db=session,
        user=user,
    )


def test_route_is_mounted():
    paths = {getattr(r, "path", "") for r in admin_system_router.routes}
    assert "/login-captcha" in paths, f"登录验证码开关路由未挂载，现有前缀: {sorted(paths)[:8]}"


def test_default_is_disabled(session):
    assert is_login_captcha_enabled(session) is False


def test_put_true_then_readback(session, monkeypatch):
    resp = _save(session, monkeypatch, True)
    assert resp["code"] == 200
    assert resp["data"]["enabled"] is True
    assert is_login_captcha_enabled(session) is True
    assert lc.get_login_captcha_settings_api(db=session, user=SimpleNamespace(id=1, username="admin"))["data"]["enabled"] is True


def test_put_false_then_readback(session, monkeypatch):
    _save(session, monkeypatch, True)
    resp = _save(session, monkeypatch, False)
    assert resp["data"]["enabled"] is False
    assert is_login_captcha_enabled(session) is False


def test_enabled_rejects_missing_captcha(session, monkeypatch):
    _save(session, monkeypatch, True)
    with pytest.raises(HTTPException) as e:
        assert_login_captcha(session, None, None)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException):
        assert_login_captcha(session, "some-id", None)


def test_disabled_passes_through(session, monkeypatch):
    _save(session, monkeypatch, False)
    assert_login_captcha(session, None, None)
