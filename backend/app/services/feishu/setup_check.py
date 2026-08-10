"""飞书个人推送必配项检查"""

from __future__ import annotations

import httpx

from app.services.feishu.client import FEISHU_API_BASE, FeishuApiError, get_tenant_access_token
from app.services.feishu.delivery import FEISHU_BOT_APPLINK

REQUIRED_EVENTS = {
    "im.message.receive_v1": "接收用户发给机器人的消息（个人单聊必配）",
    "im.chat.access_event.bot_p2p_chat_entered_v1": "用户进入机器人单聊（建议保留）",
}

REQUIRED_SCOPES = {
    "im:message:send_as_bot": "以应用身份发消息",
    "im:message.p2p_msg:readonly": "读取用户发给机器人的单聊消息",
}


def _get_online_version_detail(access_token: str, app_id: str) -> tuple[list[str], set[str], str, bool, int]:
    """返回 (events, scopes, version_name, bot_enabled_in_version, app_status)
    app_status: 0=停用, 1=启用
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{FEISHU_API_BASE}/application/v6/applications/{app_id}",
            headers=headers,
            params={"lang": "zh_cn"},
        )
        resp.raise_for_status()
        app_data = resp.json()
    if int(app_data.get("code", -1)) != 0:
        raise FeishuApiError(int(app_data.get("code", -1)), str(app_data.get("msg") or "app info failed"))
    app = app_data.get("data", {}).get("app") or {}
    app_status = int(app.get("status") or 0)
    version_id = app.get("online_version_id") or ""
    if not version_id:
        return [], set(), "", False, app_status
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{FEISHU_API_BASE}/application/v6/applications/{app_id}/app_versions/{version_id}",
            headers=headers,
            params={"lang": "zh_cn"},
        )
        resp.raise_for_status()
        ver_data = resp.json()
    if int(ver_data.get("code", -1)) != 0:
        raise FeishuApiError(int(ver_data.get("code", -1)), str(ver_data.get("msg") or "version failed"))
    version = ver_data.get("data", {}).get("app_version") or {}
    events = [str(e.get("event_type") or "") for e in (version.get("event_infos") or []) if e.get("event_type")]
    scopes = {str(s.get("scope") or "") for s in (version.get("scopes") or []) if s.get("scope")}
    # 检查版本里机器人能力是否开启（abilities / ability 两种字段都兼容）
    abilities = version.get("abilities") or version.get("ability") or {}
    bot_ability = abilities.get("bot") or {}
    bot_in_version = bool(bot_ability.get("enable") or bot_ability.get("enable_bot") or True)
    return events, scopes, str(version.get("version") or ""), bot_in_version, app_status


def _get_bot_activate_status(access_token: str) -> int:
    """返回机器人激活状态：0=停用, 1=启用, 2=未开通"""
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{FEISHU_API_BASE}/bot/v3/info",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", -1)) != 0:
        return -1
    return int(((data.get("bot") or {}).get("activate_status") or 2))


BOT_STATUS_LABELS = {0: "已停用", 1: "已启用", 2: "已激活", -1: "获取失败"}


def build_personal_push_setup_check(*, app_id: str, app_secret: str, callback_url: str) -> dict:
    token = get_tenant_access_token(app_id, app_secret)
    events, scopes, version_name, bot_in_version, app_status = _get_online_version_detail(token, app_id)
    event_set = set(events)

    bot_status = _get_bot_activate_status(token)
    bot_ok = bot_status in (1, 2) and bot_in_version and app_status == 1

    missing_events = [
        {"code": code, "name": name}
        for code, name in REQUIRED_EVENTS.items()
        if code not in event_set
    ]
    missing_scopes = [
        {"code": code, "name": name}
        for code, name in REQUIRED_SCOPES.items()
        if code not in scopes
    ]

    ready = not missing_events and not missing_scopes and bot_ok

    bot_detail_parts = [f"机器人：{BOT_STATUS_LABELS.get(bot_status, '未知')}"]
    if not bot_in_version:
        bot_detail_parts.append("版本中机器人能力未开启（开放平台 → 应用功能 → 机器人 → 打开 → 保存 → 发布新版本）")
    if app_status != 1:
        bot_detail_parts.append(f"应用状态异常（status={app_status}，应为 1-启用）")

    steps = [
        {
            "title": "机器人能力已激活",
            "detail": "；".join(bot_detail_parts) + ("。正常" if bot_ok else ""),
            "done": bot_ok,
        },
        {
            "title": "开放平台订阅 im.message.receive_v1",
            "detail": "事件与回调 → 事件配置 → 添加「接收消息 im.message.receive_v1」，回调 URL：" + (callback_url or "见本页回调地址"),
            "done": "im.message.receive_v1" in event_set,
        },
        {
            "title": "开通单聊权限并发布新版本",
            "detail": "权限管理确认 im:message:send_as_bot、im:message.p2p_msg:readonly；版本管理 → 可用范围「全部成员」→ 发布",
            "done": not missing_scopes,
        },
        {
            "title": "飞书管理后台启用应用展示",
            "detail": "管理后台 → 工作台 → 应用管理 → lightmes → 全部成员 + 勾选「在客户端展示」",
            "done": None,
        },
        {
            "title": "员工 OAuth 绑定并打开机器人",
            "detail": "绑定后从工作台打开 lightmes，向机器人发送任意消息，激活个人通知通道",
            "done": None,
        },
    ]

    return {
        "ready": ready,
        "online_version": version_name,
        "bot_status": bot_status,
        "bot_status_label": BOT_STATUS_LABELS.get(bot_status, "未知"),
        "bot_in_version": bot_in_version,
        "app_status": app_status,
        "subscribed_events": events,
        "missing_events": missing_events,
        "missing_scopes": missing_scopes,
        "bot_open_link": FEISHU_BOT_APPLINK.format(app_id=app_id),
        "steps": steps,
    }
