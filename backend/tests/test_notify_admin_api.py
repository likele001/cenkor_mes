# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""通知管理端接口（飞书 18 端点 + 消息中心 11 端点）测试。

与 test_cloud_storage_api.py 同样的原因：仓库没有 HTTP 集成 fixture，
FastAPI handler 本身就是普通函数，直接传 db/user 调用即可覆盖处理器逻辑；
需要联网的端点只验证「无凭据时 400」这一层守卫，不真打飞书。
"""
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.api.admin.system import feishu as feishu_api
from app.api.admin.system import message_center as mc_api
from app.api.admin.system.router import router as system_router
from app.api.admin.system.settings import get_api as setting_get
from app.api.admin.system.settings import upsert_api as setting_upsert
from app.crud.tenant_setting import get_setting, upsert_setting
from app.models.feishu_push_log import FeishuPushLog
from app.schemas.tenant_setting import TenantSettingUpsertIn
from app.services.feishu.settings import get_group_chat_id
from app.services.feishu.targets import resolve_targets
from app.services.notify_migration import run_migration


# ── 工具 ──

# 直接调用 handler 时 FastAPI 不会把 Query(...) 默认值还原成 None/False，
# 未筛选的查询参数必须显式给值，否则 LIKE '%Query(None)%' 会把结果清空。
FEISHU_LOGS = {"event_code": None, "status": None, "offset": 0, "limit": 50}
FEISHU_BINDINGS = {"keyword": None, "unbound_only": False}
MC_LOGS = {"channel": None, "event_code": None, "status": None, "offset": 0, "limit": 50}
MC_BINDINGS = {"keyword": None, "unbound_only": False, "offset": 0, "limit": 100}

def _request():
    return SimpleNamespace(
        client=None,
        headers={},
        method="PUT",
        url=SimpleNamespace(path="/admin/system/settings/test.key"),
    )


def _collect(routes) -> dict:
    """path -> 该 path 上所有 method 的并集。

    新版 Starlette 的 include_router 用 _IncludedRouter 包装子路由（无 .path），
    必须递归；同一 path 挂多个 method 时要合并而不是覆盖。
    """
    out: dict[str, set] = {}
    for r in routes:
        path = getattr(r, "path", None)
        if path:
            out.setdefault(path, set()).update(getattr(r, "methods", None) or ())
        children = getattr(r, "routes", None)
        if children:
            for p, ms in _collect(children).items():
                out.setdefault(p, set()).update(ms)
    return out


def _data(resp: dict):
    assert resp["code"] == 200
    return resp["data"]


@pytest.fixture(autouse=True)
def _no_env_credentials(monkeypatch):
    """屏蔽 .env 里的飞书凭据 fallback，否则「无凭据应 400」的用例会随环境漂移。"""
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)


@pytest.fixture(autouse=True)
def _noop_op_log(monkeypatch):
    """operation_logs.id 在 SQLite 测试库下非自增，且与本文件要验证的配置逻辑无关。"""
    monkeypatch.setattr("app.api.admin.system.settings.write_op_log", lambda *a, **k: None)


@pytest.fixture
def bound_user(session: Session, test_user):
    """给管理员绑一个 open_id，让 resolve_targets 有可解析的目标。"""
    test_user.feishu_open_id = "ou_admin_001"
    session.flush()
    return test_user


# ── tenant_setting KV 三种调用签名 ──

def test_setting_crud_single_user_positional(session: Session):
    upsert_setting(session, "some.key", "v1")
    assert get_setting(session, "some.key").value == "v1"


def test_setting_crud_keyword_style(session: Session):
    """settings.py / plans.py / notify_guard.py 用关键字调用，曾因签名不兼容直接 TypeError。"""
    upsert_setting(session, key="kw.key", value="v2")
    assert get_setting(session, key="kw.key").value == "v2"


def test_setting_crud_saas_positional_style(session: Session):
    """lightmes 侧的多租户签名 (db, tenant_id, key, value)，单租户下 tenant_id 应被忽略。"""
    upsert_setting(session, 1, "saas.key", "v3")
    assert get_setting(session, 1, "saas.key").value == "v3"


def test_setting_upsert_overwrites_existing(session: Session):
    upsert_setting(session, "k", "a")
    upsert_setting(session, "k", "b")
    assert get_setting(session, "k").value == "b"


def test_settings_api_roundtrip_with_value_none(session: Session, test_user):
    """PUT /admin/system/settings/{key} 曾整条链路 500。"""
    created = _data(setting_upsert(
        "test.key",
        TenantSettingUpsertIn(value="hello"),
        _request(),
        db=session,
        user=test_user,
    ))
    assert created["key"] == "test.key" and created["value"] == "hello"

    none_out = _data(setting_upsert(
        "test.null",
        TenantSettingUpsertIn(value=None),
        _request(),
        db=session,
        user=test_user,
    ))
    assert none_out["value"] is None

    assert _data(setting_get("test.key", db=session, user=test_user))["value"] == "hello"
    assert _data(setting_get("missing.key", db=session, user=test_user)) is None


# ── 路由挂载 ──

FEISHU_PATHS = {
    "/feishu",
    "/feishu/test-connection",
    "/feishu/test-send",
    "/feishu/delivery-diagnostics",
    "/feishu/setup-checklist",
    "/feishu/chats",
    "/feishu/feishu-departments",
    "/feishu/push-logs",
    "/feishu/push-logs/{log_id}/retry",
    "/feishu/user-bindings",
    "/feishu/user-bindings/{target_user_id}",
    "/feishu/user-bindings/batch-match-mobile",
    "/feishu/department-bindings",
    "/feishu/department-bindings/{department_id}",
    "/feishu/simulate",
    "/feishu/bind-url",
    "/feishu/preview-card",
}

MESSAGE_CENTER_PATHS = {
    "/message-center/overview",
    "/message-center/groups",
    "/message-center/rules",
    "/message-center/user-bindings",
    "/message-center/push-logs",
    "/message-center/alert-recipients",
    "/message-center/all-bindable-users",
    "/message-center/run-migration",
}


def test_feishu_routes_mounted():
    routes = _collect(system_router.routes)
    missing = FEISHU_PATHS - set(routes)
    assert not missing, f"飞书路由未挂载：{missing}"


def test_message_center_routes_mounted():
    routes = _collect(system_router.routes)
    missing = MESSAGE_CENTER_PATHS - set(routes)
    assert not missing, f"消息中心路由未挂载：{missing}"


def test_feishu_endpoint_count_matches_handler():
    """stub 时期的特征是「路由在但全返回 ok({})」；这里钉住端点数量防止再次被掏空。"""
    assert len(feishu_api.router.routes) == 18
    assert len(mc_api.router.routes) == 10


def test_routers_require_setting_manage_permission():
    for router in (feishu_api.router, mc_api.router):
        assert len(router.dependencies) == 1, "路由级依赖被改动"
        dep = router.dependencies[0].dependency
        # require_permissions() 返回闭包 _dep，其唯一 freevar 即权限码列表
        assert dep.__name__ == "_dep"
        assert dep.__closure__[0].cell_contents == ["setting.manage"]


# ── 飞书配置读写与脱敏 ──

def test_read_settings_masks_secret(session: Session, test_user):
    feishu_api.write_settings(
        _Payload_model(app_id="cli_abc", app_secret="topsecret", enabled=True),
        db=session,
        user=test_user,
    )
    data = _data(feishu_api.read_settings(db=session, user=test_user))
    assert data["app_id"] == "cli_abc"
    assert data["app_secret_configured"] is True
    assert data["app_secret_masked"] == "********"
    assert "topsecret" not in str(data)


def test_write_settings_mask_does_not_wipe_secret(session: Session, test_user):
    out = _data(feishu_api.write_settings(
        _Payload_model(app_id="cli_abc", app_secret="topsecret"), db=session, user=test_user
    ))
    out = _data(feishu_api.write_settings(
        _Payload_model(app_id="cli_abc", app_secret="********"), db=session, user=test_user
    ))
    assert out["app_secret_configured"] is True

    cleared = _data(feishu_api.write_settings(
        _Payload_model(app_secret=""), db=session, user=test_user
    ))
    assert cleared["app_secret_configured"] is False


def _Payload_model(**kw):
    return feishu_api.SettingsIn(**kw)


# ── 联网端点的凭据守卫 ──

@pytest.mark.parametrize("name", [
    "test_connection",
    "bot_chats",
    "feishu_departments",
    "setup_checklist",
    "batch_match_mobile",
])
def test_network_endpoints_reject_without_credentials(name, session: Session, test_user):
    from fastapi import HTTPException

    handler = getattr(feishu_api, name)
    kwargs = {"db": session, "user": test_user}
    if name == "batch_match_mobile":
        kwargs["refresh_all"] = False
    with pytest.raises(HTTPException) as ei:
        handler(**kwargs)
    assert ei.value.status_code == 400
    assert "App ID" in ei.value.detail


def test_delivery_diagnostics_rejects_unbound_user(session: Session, test_user):
    from fastapi import HTTPException

    feishu_api.write_settings(_Payload_model(app_id="cli_a", app_secret="s"), db=session, user=test_user)
    with pytest.raises(HTTPException) as ei:
        feishu_api.delivery_diagnostics(user_id=test_user.id, db=session, user=test_user)
    assert ei.value.status_code == 400
    assert "open_id" in ei.value.detail


def test_bind_url_without_base_url_is_400(session: Session, test_user, monkeypatch):
    """有 App ID 但没配 API 外网地址时，oauth 抛 ValueError，接口须转 400 而非 500。"""
    from fastapi import HTTPException

    from app.core.config import settings as app_cfg
    monkeypatch.setattr(app_cfg, "PUBLIC_BASE_URL", "", raising=False)
    feishu_api.write_settings(
        _Payload_model(app_id="cli_a", app_secret="s", api_public_base_url=""), db=session, user=test_user
    )
    with pytest.raises(HTTPException) as ei:
        feishu_api.bind_url(feishu_api.BindUrlIn(user_id=test_user.id), db=session, user=test_user)
    assert ei.value.status_code == 400


def test_bind_url_builds_authorize_link(session: Session, test_user):
    feishu_api.write_settings(
        _Payload_model(app_id="cli_a", app_secret="s", api_public_base_url="https://ck.example.com"),
        db=session,
        user=test_user,
    )
    data = _data(feishu_api.bind_url(feishu_api.BindUrlIn(), db=session, user=test_user))
    assert data["user_id"] == test_user.id
    assert data["authorize_url"].startswith("https://open.feishu.cn/")
    assert "cli_a" in data["authorize_url"]


# ── 卡片预览 / 模拟（纯本地逻辑） ──

def test_preview_card_builds_card(session: Session, test_user):
    data = _data(feishu_api.preview_card(
        feishu_api.PreviewCardIn(title="标题", content="内容", level="danger"),
        db=session,
        user=test_user,
    ))
    card = data["card"]
    assert card["header"]["title"]["content"] == "标题"
    assert "内容" in str(card["elements"])


def test_preview_card_defaults_localize(session: Session, test_user):
    data = _data(feishu_api.preview_card(feishu_api.PreviewCardIn(), db=session, user=test_user))
    assert data["card"]["header"]["title"]["content"] == "示例通知标题"


def test_simulate_unknown_event_is_404(session: Session, test_user):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        feishu_api.simulate(feishu_api.SimulateIn(event_code="nope.happened"), db=session, user=test_user)
    assert ei.value.status_code == 404


def test_simulate_resolves_user_and_chat_targets(session: Session, bound_user):
    feishu_api.write_settings(_Payload_model(
        app_id="cli_a",
        app_secret="s",
        groups=[{
            "code": "management",
            "name": "管理群",
            "enabled": True,
            "channels": {"feishu": {"chat_id": "oc_mgmt", "enabled": True}},
        }],
        rules={"salary.slip_rejected": {"enabled": True, "targets": [f"user:{bound_user.id}", "group:management"]}},
    ), db=session, user=bound_user)

    data = _data(feishu_api.simulate(
        feishu_api.SimulateIn(event_code="salary.slip_rejected"), db=session, user=bound_user
    ))
    pairs = {(t["kind"], t["ref"]) for t in data["targets"]}
    assert ("user", "ou_admin_001") in pairs
    assert ("chat", "oc_mgmt") in pairs


def test_simulate_alert_escalation_per_level(session: Session, bound_user):
    feishu_api.write_settings(_Payload_model(
        app_id="cli_a",
        app_secret="s",
        groups=[{
            "code": "factory",
            "name": "全厂群",
            "enabled": True,
            "channels": {"feishu": {"chat_id": "oc_factory", "enabled": True}},
        }],
    ), db=session, user=bound_user)
    data = _data(feishu_api.simulate(feishu_api.SimulateIn(event_code="alert"), db=session, user=bound_user))
    esc = data["escalation"]
    assert set(esc) == {"info", "warning", "danger", "critical"}
    refs = {t["ref"] for t in esc["critical"]}
    assert "oc_factory" in refs
    # info 级别不含 boss/群，范围比 critical 小
    assert len(esc["info"]) <= len(esc["critical"])


def test_simulate_names_targets_and_flags_dead_codes(session: Session, bound_user):
    """模拟器要能指出「哪一条目标谁也没命中」——配规则的人靠这个排错。"""
    feishu_api.write_settings(_Payload_model(
        app_id="cli_a",
        app_secret="s",
        groups=[{
            "code": "management",
            "name": "管理群",
            "enabled": True,
            "channels": {"feishu": {"chat_id": "oc_mgmt", "enabled": True}},
        }],
        rules={"report.submitted": {
            "enabled": True,
            "targets": [f"user:{bound_user.id}", "group:management", "group:not_configured"],
        }},
    ), db=session, user=bound_user)

    data = _data(feishu_api.simulate(
        feishu_api.SimulateIn(event_code="report.submitted"), db=session, user=bound_user
    ))
    by_kind = {t["ref"]: t for t in data["targets"]}
    assert by_kind["ou_admin_001"]["name"] == "管理员"
    assert by_kind["oc_mgmt"]["name"] == "管理群"
    assert data["unresolved"] == ["group:not_configured"]
    assert data["by_code"]["group:management"]
    assert data["enabled"] is True


# ── 群地址：旧结构 vs v2 channels 结构 ──

def test_group_chat_id_reads_legacy_and_v2():
    legacy = {"groups": [{"code": "production", "chat_id": "oc_legacy", "enabled": True}]}
    v2 = {"groups": [{
        "code": "production",
        "enabled": True,
        "channels": {"feishu": {"chat_id": "oc_v2", "enabled": True}},
    }]}
    assert get_group_chat_id(legacy, "production") == "oc_legacy"
    assert get_group_chat_id(v2, "production") == "oc_v2"


def test_group_chat_id_respects_disable_flags():
    group_off = {"groups": [{
        "code": "production", "enabled": False,
        "channels": {"feishu": {"chat_id": "oc_x", "enabled": True}},
    }]}
    channel_off = {"groups": [{
        "code": "production", "enabled": True,
        "channels": {"feishu": {"chat_id": "oc_x", "enabled": False}},
    }]}
    assert get_group_chat_id(group_off, "production") == ""
    assert get_group_chat_id(channel_off, "production") == ""


def test_migrated_config_still_resolves_group(session: Session, bound_user):
    """迁移后配置只剩 channels 嵌套，历史 bug 是群推送静默丢失。"""
    upsert_setting(session, "feishu.notify", (
        '{"groups":[{"code":"management","name":"管理群","chat_id":"oc_mgmt","enabled":true}],'
        '"enabled":true,"app_id":"cli_a","app_secret":"s"}'
    ))
    run_migration(session)
    targets = resolve_targets(session, ["group:management"])
    assert targets == [{"kind": "chat", "ref": "oc_mgmt", "chat_code": "management"}]


# ── 绑定与日志 ──

def test_user_binding_update_roundtrip(session: Session, test_user):
    out = _data(feishu_api.update_user_binding(
        test_user.id,
        feishu_api.UserBindingIn(feishu_open_id="ou_x", feishu_user_id="on_y"),
        db=session,
        user=test_user,
    ))
    assert out["bound"] is True and out["feishu_open_id"] == "ou_x"
    assert out["feishu_bound_at"] is not None

    cleared = _data(feishu_api.update_user_binding(
        test_user.id, feishu_api.UserBindingIn(), db=session, user=test_user
    ))
    assert cleared["bound"] is False and cleared["feishu_bound_at"] is None


def test_user_bindings_unbound_filter(session: Session, test_user, bound_user):
    # 直接调用 handler 时 FastAPI 不会把 Query 默认值还原成 None，须显式传
    items = _data(feishu_api.user_bindings(**FEISHU_BINDINGS, db=session, user=test_user))["items"]
    assert len(items) == 1

    unbound = _data(feishu_api.user_bindings(
        **{**FEISHU_BINDINGS, "unbound_only": True}, db=session, user=test_user
    ))["items"]
    assert unbound == []

    by_kw = _data(feishu_api.user_bindings(
        **{**FEISHU_BINDINGS, "keyword": "不存在"}, db=session, user=test_user
    ))["items"]
    assert by_kw == []

    hit = _data(feishu_api.user_bindings(
        **{**FEISHU_BINDINGS, "keyword": "admin"}, db=session, user=test_user
    ))["items"]
    assert [u["id"] for u in hit] == [test_user.id]


def test_department_binding_update(session: Session, department, test_user):
    out = _data(feishu_api.update_department_binding(
        department.id,
        feishu_api.DeptBindingIn(feishu_open_department_id="od_1", feishu_chat_group_code="production"),
        db=session,
        user=test_user,
    ))
    assert out["feishu_chat_group_code"] == "production"

    rows = _data(feishu_api.department_bindings(db=session, user=test_user))["items"]
    assert [r["id"] for r in rows] == [department.id]


@pytest.fixture
def push_log(session: Session, bound_user) -> FeishuPushLog:
    log = FeishuPushLog(
        event_code="alert",
        target_kind="user",
        target_ref="ou_admin_001",
        title="库存预警",
        content="缺料",
        level="warning",
        status="failed",
        error_msg="rate limit",
        feishu_message_id="om_123",
    )
    session.add(log)
    session.flush()
    return log


def test_push_logs_filters(session: Session, test_user, push_log):
    all_rows = _data(feishu_api.push_logs(**FEISHU_LOGS, db=session, user=test_user))["items"]
    assert [r["id"] for r in all_rows] == [push_log.id]
    assert all_rows[0]["feishu_message_id"] == "om_123"

    assert _data(feishu_api.push_logs(
        **{**FEISHU_LOGS, "event_code": "brief.daily"}, db=session, user=test_user
    ))["items"] == []
    assert len(_data(feishu_api.push_logs(
        **{**FEISHU_LOGS, "status": "failed"}, db=session, user=test_user
    ))["items"]) == 1


def test_retry_push_log_resets_state(session: Session, test_user, push_log, monkeypatch):
    enqueued = []
    monkeypatch.setattr(feishu_api, "enqueue_feishu_push", lambda db, log_id: enqueued.append(log_id))
    # 测试 session 一直在事务里，after_commit 不会触发，无需真实 celery
    out = _data(feishu_api.retry_push_log(push_log.id, db=session, user=test_user))
    assert out == {"id": push_log.id, "status": "pending"}
    assert enqueued == [push_log.id]
    session.refresh(push_log)
    assert push_log.retry_count == 1 and push_log.error_msg is None


def test_retry_missing_log_is_404(session: Session, test_user):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        feishu_api.retry_push_log(999999, db=session, user=test_user)
    assert ei.value.status_code == 404


def test_delivery_diagnostics_uses_latest_message(session: Session, test_user, push_log, monkeypatch):
    """网络部分打桩，只验证「最近一条 message_id 被带上」。"""
    seen = {}

    def _fake(app_id, app_secret, *, feishu_open_id, latest_message_id=None):
        seen.update(feishu_open_id=feishu_open_id, latest_message_id=latest_message_id)
        return {"ok": True}

    monkeypatch.setattr(feishu_api, "build_delivery_diagnostics", _fake)
    test_user.feishu_open_id = "ou_admin_001"
    session.flush()
    feishu_api.write_settings(_Payload_model(app_id="cli_a", app_secret="s"), db=session, user=test_user)

    data = _data(feishu_api.delivery_diagnostics(user_id=test_user.id, db=session, user=test_user))
    assert data == {"ok": True}
    assert seen == {"feishu_open_id": "ou_admin_001", "latest_message_id": "om_123"}


def test_guard_feishu_error_maps_api_error_to_400(session: Session, test_user, monkeypatch):
    from app.services.feishu.client import FeishuApiError
    from fastapi import HTTPException

    monkeypatch.setattr(
        feishu_api, "get_tenant_access_token",
        lambda *a, **k: (_ for _ in ()).throw(FeishuApiError(99991663, "app_access_token invalid")),
    )
    feishu_api.write_settings(_Payload_model(app_id="cli_a", app_secret="s"), db=session, user=test_user)
    with pytest.raises(HTTPException) as ei:
        feishu_api.test_connection(db=session, user=test_user)
    assert ei.value.status_code == 400
    assert "app_access_token invalid" in ei.value.detail


# ── 消息中心 ──

def test_overview_reports_feishu_and_stub_channels(session: Session, test_user):
    mc_api.save_groups(mc_api.GroupsIn(items=[{
        "code": "production", "name": "生产群", "chat_id": "oc_prod", "enabled": True,
    }]), db=session, user=test_user)
    feishu_api.write_settings(_Payload_model(
        app_id="cli_a", app_secret="s", enabled=True, api_public_base_url="https://ck.example.com"
    ), db=session, user=test_user)

    data = _data(mc_api.overview(db=session, user=test_user))["channels"]
    assert data["feishu"]["configured"] is True
    assert data["feishu"]["enabled"] is True
    assert data["feishu"]["agent_id"] == "cli_a"
    assert data["feishu"]["callback_url"] == "https://ck.example.com/api/feishu/events"
    assert data["feishu"]["oauth_redirect_url"] == "https://ck.example.com/api/feishu/oauth/callback"
    assert data["feishu"]["today_total"] == 0
    for stub in ("wecom", "dingtalk"):
        assert data[stub]["configured"] is False and data[stub]["enabled"] is False


def test_groups_normalizes_flat_to_channels(session: Session, test_user):
    out = _data(mc_api.save_groups(mc_api.GroupsIn(items=[
        {"code": "production", "name": "生产群", "chat_id": "oc_prod", "enabled": True},
        {"code": "wecom_only", "name": "企微群", "webhook_url": "https://qy/x", "enabled": True},
    ]), db=session, user=test_user))["items"]

    assert out[0]["channels"]["feishu"] == {"enabled": True, "chat_id": "oc_prod", "webhook_url": "", "webhook_secret": ""}
    assert out[0]["channels"]["wecom"]["enabled"] is False
    assert out[1]["channels"]["wecom"]["webhook_url"] == "https://qy/x"
    # 再读一次，确认落盘的是 v2 结构且可幂等归一
    again = _data(mc_api.list_groups(db=session, user=test_user))["items"]
    assert again == out


def test_groups_empty_address_is_not_enabled(session: Session, test_user):
    """开关开着但地址为空 = 死配置，直接按未启用存。"""
    out = _data(mc_api.save_groups(mc_api.GroupsIn(items=[{
        "code": "production", "name": "生产群", "chat_id": "   ", "enabled": True,
    }]), db=session, user=test_user))["items"]
    assert out[0]["channels"]["feishu"]["enabled"] is False


def test_groups_rejects_blank_or_duplicate_code(session: Session, test_user):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        mc_api.save_groups(mc_api.GroupsIn(items=[{"code": "  ", "name": "x"}]), db=session, user=test_user)
    assert ei.value.status_code == 400

    dup = lambda: mc_api.save_groups(mc_api.GroupsIn(items=[  # noqa: E731
        {"code": "p", "name": "A"}, {"code": "p", "name": "B"},
    ]), db=session, user=test_user)
    with pytest.raises(HTTPException) as ei:
        dup()
    assert "重复" in ei.value.detail


def test_rules_lists_catalog_and_extra_codes(session: Session, test_user):
    feishu_api.write_settings(_Payload_model(
        rules={"custom.event": {"enabled": True, "targets": ["boss"]}}
    ), db=session, user=test_user)
    data = _data(mc_api.list_rules(db=session, user=test_user))
    codes = [i["event_code"] for i in data["items"]]
    assert "alert" in codes and "custom.event" in codes
    assert len(codes) == len(set(codes))
    assert data["event_catalog"] and data["target_options"]
    by_code = {i["event_code"]: i for i in data["items"]}
    assert by_code["custom.event"]["feishu_rule"]["targets"] == ["boss"]
    assert by_code["custom.event"]["wecom_rule"] == {}


def test_alert_recipients_roundtrip_preserves_other_targets(session: Session, test_user, bound_user):
    feishu_api.write_settings(_Payload_model(rules={
        "alert": {"enabled": True, "targets": ["permission:ai.alert.view", "group:management"]}
    }), db=session, user=test_user)

    saved = _data(mc_api.save_alert_recipients(
        mc_api.AlertRecipientsIn(user_ids=[bound_user.id, bound_user.id]), db=session, user=test_user
    ))
    assert saved["user_ids"] == [bound_user.id]

    got = _data(mc_api.alert_recipients(db=session, user=test_user))
    assert got["user_ids"] == [bound_user.id]
    assert [u["id"] for u in got["users"]] == [bound_user.id]

    rule = (get_setting(session, "feishu.notify").value)
    import json as _json
    targets = _json.loads(rule)["rules"]["alert"]["targets"]
    assert "permission:ai.alert.view" in targets and "group:management" in targets
    assert f"user:{bound_user.id}" in targets

    emptied = _data(mc_api.save_alert_recipients(mc_api.AlertRecipientsIn(), db=session, user=test_user))
    assert emptied["user_ids"] == []
    assert _data(mc_api.alert_recipients(db=session, user=test_user))["user_ids"] == []


def test_push_logs_channel_filter(session: Session, test_user, push_log):
    assert len(_data(mc_api.push_logs(**MC_LOGS, db=session, user=test_user))["items"]) == 1
    assert _data(mc_api.push_logs(
        **{**MC_LOGS, "channel": "wecom"}, db=session, user=test_user
    ))["items"] == []
    assert _data(mc_api.push_logs(
        **{**MC_LOGS, "channel": "dingtalk"}, db=session, user=test_user
    ))["items"] == []
    feishu_rows = _data(mc_api.push_logs(
        **{**MC_LOGS, "channel": "feishu"}, db=session, user=test_user
    ))["items"]
    assert feishu_rows[0]["channel"] == "feishu"
    assert feishu_rows[0]["message_id"] == "om_123"


def test_user_bindings_pagination_and_bound_flag(session: Session, test_user, bound_user):
    items = _data(mc_api.user_bindings(**MC_BINDINGS, db=session, user=test_user))["items"]
    assert items[0]["bound"] is True
    assert items[0]["feishu_open_id"] == "ou_admin_001"
    assert _data(mc_api.user_bindings(
        **{**MC_BINDINGS, "unbound_only": True}, db=session, user=test_user
    ))["items"] == []
    assert _data(mc_api.user_bindings(
        **{**MC_BINDINGS, "keyword": "admin"}, db=session, user=test_user
    ))["items"] != []


def test_unbound_only_means_no_channel_at_all(session: Session, test_user):
    """只绑了飞书的人不该出现在「仅看未绑定」里，否则这个筛选永远清不完。"""
    test_user.feishu_open_id = "ou_only_feishu"
    session.flush()
    rows = _data(mc_api.user_bindings(
        **{**MC_BINDINGS, "unbound_only": True}, db=session, user=test_user
    ))["items"]
    assert rows == []
    assert [u["id"] for u in _data(mc_api.all_bindable_users(db=session, user=test_user))["items"]] == [test_user.id]


# ── 一次性迁移 ──

def test_run_migration_old_structure_to_v2(session: Session, test_user):
    import json

    legacy = {"groups": [{"code": "production", "name": "生产群", "chat_id": "oc_p", "enabled": True}]}
    upsert_setting(session, "feishu.notify", json.dumps(legacy, ensure_ascii=False))

    data = _data(mc_api.migrate(db=session, user=test_user))
    assert data["total_migrated"] == 1
    assert data["detail"]["feishu"] == "migrated"

    stored = json.loads(get_setting(session, "feishu.notify").value)
    chans = stored["groups"][0]["channels"]
    assert chans["feishu"] == {"chat_id": "oc_p", "enabled": True}
    assert chans["wecom"]["enabled"] is False
    assert "chat_id" not in stored["groups"][0]

    # 幂等：第二次没有旧结构可迁
    again = _data(mc_api.migrate(db=session, user=test_user))
    assert again["total_migrated"] == 0


def test_run_migration_empty_config(session: Session, test_user):
    data = _data(mc_api.migrate(db=session, user=test_user))
    assert data["total_migrated"] == 0
    assert set(data["detail"]) == {"feishu", "wecom"}
