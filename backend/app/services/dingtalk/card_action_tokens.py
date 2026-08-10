"""钉钉 ActionCard 审核按钮签名 token"""

from __future__ import annotations

from app.core.security import create_access_token, decode_token


def create_card_action_token(
    *,
    dingtalk_userid: str,
    action: str,
    biz_type: str,
    biz_id: int,
    minutes: int = 1440,
) -> str:
    return create_access_token(
        {
            "purpose": "dingtalk_card_action",
            "tenant_id": 1,
            "dingtalk_userid": str(dingtalk_userid),
            "action": action,
            "biz_type": biz_type,
            "biz_id": int(biz_id),
        },
        expires_minutes=minutes,
    )


def parse_card_action_token(token: str) -> dict:
    data = decode_token(token)
    if data.get("purpose") != "dingtalk_card_action":
        raise ValueError("invalid card action token")
    return {
        "tenant_id": 1,
        "dingtalk_userid": str(data["dingtalk_userid"]),
        "action": str(data["action"]),
        "biz_type": str(data["biz_type"]),
        "biz_id": int(data["biz_id"]),
    }
