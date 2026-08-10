"""飞书消息投递诊断（个人 open_id / 机器人单聊）"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.feishu.client import FEISHU_API_BASE, FeishuApiError, get_tenant_access_token

FEISHU_CHAT_APPLINK = "https://applink.feishu.cn/client/chat/open?openChatId={chat_id}"
FEISHU_BOT_APPLINK = "https://applink.feishu.cn/client/bot/open?appId={app_id}"


def get_message_detail(access_token: str, message_id: str) -> dict[str, Any] | None:
    if not message_id:
        return None
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(f"{FEISHU_API_BASE}/im/v1/messages/{message_id}", headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", -1)) != 0:
        raise FeishuApiError(int(data.get("code", -1)), str(data.get("msg") or "get message failed"))
    items = (data.get("data") or {}).get("items") or []
    return items[0] if items else None


def get_bot_info(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(f"{FEISHU_API_BASE}/bot/v3/info", headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", -1)) != 0:
        raise FeishuApiError(int(data.get("code", -1)), str(data.get("msg") or "bot info failed"))
    return data.get("bot") or {}


def get_tenant_name(access_token: str) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(f"{FEISHU_API_BASE}/tenant/v2/tenant/query", headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", -1)) != 0:
        return ""
    return str(((data.get("data") or {}).get("tenant") or {}).get("name") or "")


def get_feishu_user_profile(access_token: str, open_id: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{FEISHU_API_BASE}/contact/v3/users/{open_id}",
            headers=headers,
            params={"user_id_type": "open_id"},
        )
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", -1)) != 0:
        raise FeishuApiError(int(data.get("code", -1)), str(data.get("msg") or "user profile failed"))
    return (data.get("data") or {}).get("user") or {}


def count_p2p_messages(access_token: str, chat_id: str) -> int:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{FEISHU_API_BASE}/im/v1/messages",
            headers=headers,
            params={"container_id_type": "chat", "container_id": chat_id, "page_size": 50},
        )
        resp.raise_for_status()
        data = resp.json()
    if int(data.get("code", -1)) != 0:
        return 0
    return len((data.get("data") or {}).get("items") or [])


def build_delivery_diagnostics(
    *,
    app_id: str,
    app_secret: str,
    feishu_open_id: str,
    latest_message_id: str | None = None,
) -> dict[str, Any]:
    token = get_tenant_access_token(app_id, app_secret)
    tenant_name = get_tenant_name(token)
    bot = get_bot_info(token)
    profile = get_feishu_user_profile(token, feishu_open_id) if feishu_open_id else {}

    chat_id = ""
    if latest_message_id:
        detail = get_message_detail(token, latest_message_id)
        if detail:
            chat_id = str(detail.get("chat_id") or "")

    msg_count = count_p2p_messages(token, chat_id) if chat_id else 0

    return {
        "feishu_tenant_name": tenant_name,
        "bot_name": bot.get("app_name") or "",
        "bot_app_id": app_id,
        "bot_open_link": FEISHU_BOT_APPLINK.format(app_id=app_id),
        "bound_feishu_name": profile.get("name") or "",
        "bound_feishu_email": profile.get("email") or "",
        "bound_open_id": feishu_open_id,
        "p2p_chat_id": chat_id,
        "chat_open_link": FEISHU_CHAT_APPLINK.format(chat_id=chat_id) if chat_id else "",
        "p2p_message_count": msg_count,
        "hints": [
            "个人推送不会出现在「应用消息」，请在消息列表找与机器人「{}」的单聊".format(bot.get("app_name") or "lightmes"),
            "请确认飞书左上角企业名为「{}」".format(tenant_name or "与开发者后台一致"),
            "若搜不到机器人：开放平台 → 版本管理 → 可用范围设为「全部成员」并发布；管理后台 → 应用管理 → 勾选「在应用中心展示」",
            "可用 chat_open_link 在手机/电脑浏览器打开，会唤起飞书进入该单聊",
        ],
    }
