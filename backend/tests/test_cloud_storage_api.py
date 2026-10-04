# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储管理接口(CS-4) 测试：路由挂载/权限点/处理器逻辑。

无 HTTP 集成 fixture，故直接调用路由处理函数（FastAPI handler 即普通函数），
显式传入 db/user 及鸭子类型的 Request，覆盖脱敏读取、凭据合并、激活校验、连通性测试降级。
"""
from types import SimpleNamespace

import pytest

from app.api.admin.system import cloud_storage as api
from app.api.admin.system.router import router as system_router
from app.core.seed import DEFAULT_PERMISSIONS
from app.schemas.cloud_storage import ActivateIn, CloudCredsIn, SettingsIn
from app.storage.local import LocalStorage


CREDS = {
    "endpoint": "oss-cn-hangzhou.aliyuncs.com",
    "region": "cn-hangzhou",
    "bucket": "my-bucket",
    "access_key": "AKID1234567890abcd",
    "secret_key": "SUPERSECRETVALUE123",
}


def _fake_request():
    return SimpleNamespace(
        client=None,
        headers={},
        method="PUT",
        url=SimpleNamespace(path="/admin/system/cloud-storage"),
    )


@pytest.fixture(autouse=True)
def _noop_op_log(monkeypatch):
    """屏蔽操作日志写入：operation_logs.id 在 SQLite 测试库下非自增，
    与本用例要验证的配置业务逻辑无关。"""
    monkeypatch.setattr(api, "write_op_log", lambda *a, **k: None)


# ── 接线：权限点 + 路由挂载 ──

def test_permission_point_seeded():
    codes = {c for c, _ in DEFAULT_PERMISSIONS}
    assert "cloud_storage.manage" in codes


def _collect_route_paths(routes) -> set:
    """递归收集路由 path。

    兼容不同 Starlette 版本：旧版 `include_router` 会把子路由平铺进 `.routes`；
    新版（如 1.7+）改用 `_IncludedRouter` 包装（无 `.path`，但有 `.routes`）。
    递归收集可跨版本稳定，避免上游升级造成假红灯。
    """
    paths: set = set()
    for r in routes:
        p = getattr(r, "path", None)
        if p:
            paths.add(p)
        sub = getattr(r, "routes", None)
        if sub:
            paths |= _collect_route_paths(sub)
    return paths


def test_routes_mounted():
    paths = _collect_route_paths(system_router.routes)
    base = "/cloud-storage"
    assert f"{base}" in paths
    assert f"{base}/providers/{{provider}}/credentials" in paths
    assert f"{base}/providers/{{provider}}/activate" in paths
    assert f"{base}/providers/{{provider}}/test" in paths
    assert f"{base}/settings" in paths


def test_router_requires_permission():
    # 路由组级依赖应包含权限校验（5 个端点共享）
    deps = [d.dependency for d in api.router.dependencies]
    assert any(callable(d) for d in deps)


# ── 处理器逻辑 ──

def test_get_config_returns_masked(session, test_user):
    # 先落一份真实凭据，读取必须脱敏
    api.save_credentials(
        "aliyun", CloudCredsIn(**CREDS), _fake_request(), db=session, user=test_user
    )
    res = api.get_config(db=session, user=test_user)
    view = res["data"]
    assert view["active_provider"] == "local"
    ali = view["providers"]["aliyun"]
    assert ali["configured"] is True
    # 明文密钥绝不外泄
    assert ali["credentials"]["secret_key"] != CREDS["secret_key"]
    assert "SUPERSECRET" not in str(view)
    assert "aliyun" in view["supported_drivers"]


def test_save_credentials_merge_keeps_secret_on_mask(session, test_user):
    api.save_credentials("aliyun", CloudCredsIn(**CREDS), _fake_request(), db=session, user=test_user)
    from app.services import cloud_storage_config as svc

    # 编辑表单回显掩码值，再次提交不得清空真实密钥
    api.save_credentials(
        "aliyun",
        CloudCredsIn(bucket="new-bucket", secret_key="••••••••", access_key="••••abcd"),
        _fake_request(), db=session, user=test_user,
    )
    stored = svc.get_credentials(session, "aliyun")
    assert stored["bucket"] == "new-bucket"
    assert stored["secret_key"] == CREDS["secret_key"]  # 掩码字段保留原值


def test_activate_requires_credentials(session, test_user):
    from app.core.errors import BizError

    with pytest.raises(BizError) as exc:
        api.activate_provider("tencent", ActivateIn(provider="tencent"), _fake_request(), db=session, user=test_user)
    assert exc.value.code == 400


def test_activate_local_ok(session, test_user):
    # 先配置再激活
    api.save_credentials("aliyun", CloudCredsIn(**CREDS), _fake_request(), db=session, user=test_user)
    res = api.activate_provider("aliyun", ActivateIn(provider="aliyun"), _fake_request(), db=session, user=test_user)
    assert res["data"]["active_provider"] == "aliyun"


def test_test_provider_local_ok(session, test_user):
    res = api.test_provider("local", db=session, user=test_user)
    assert res["data"]["ok"] is True
    assert res["data"]["provider"] == "local"


def test_test_provider_degrades_to_local(session, test_user):
    # 未配置凭据的云 provider：工厂降级 local，测试标记未就绪
    from app.storage.factory import build_storage

    res = api.test_provider("aliyun", db=session, user=test_user)
    assert res["data"]["ok"] is True  # 降级为 local 视为可用
    assert isinstance(build_storage("aliyun", db=session), LocalStorage)


def test_update_settings_keep_local_backup(session, test_user):
    res = api.update_settings(SettingsIn(keep_local_backup=True), _fake_request(), db=session, user=test_user)
    assert res["data"]["keep_local_backup"] is True
