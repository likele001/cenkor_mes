"""企业微信消息投递诊断"""

from __future__ import annotations

from typing import Any

from app.services.wecom.client import WecomApiError, get_access_token, get_user_info, get_agent


def build_delivery_diagnostics(
    *,
    corp_id: str,
    corp_secret: str,
    agent_id: str,
    wecom_userid: str,
) -> dict[str, Any]:
    token = get_access_token(corp_id, corp_secret)
    user_info: dict[str, Any] = {}
    agent_info: dict[str, Any] = {}

    try:
        user_info = get_user_info(token, wecom_userid)
    except WecomApiError:
        pass

    if agent_id:
        try:
            agent_info = get_agent(token, int(agent_id))
        except (WecomApiError, ValueError):
            pass

    return {
        "corp_id": corp_id,
        "agent_id": agent_id,
        "agent_name": agent_info.get("name") or "",
        "wecom_userid": wecom_userid,
        "user_name": user_info.get("name") or "",
        "user_mobile": user_info.get("mobile") or "",
        "user_status": user_info.get("status", -1),
        "hints": [
            "个人推送通过应用消息下发，员工需在企业微信「工作台」能看到应用",
            "若收不到消息：确认应用可见范围包含该员工，且应用已创建发布",
            "群通知通过 Webhook URL 下发，需在群设置里添加机器人",
        ],
    }
