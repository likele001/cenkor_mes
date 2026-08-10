"""绑定后欢迎消息"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.wecom.client import WecomApiError, get_access_token, send_text_message
from app.services.wecom.settings import get_wecom_credentials

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "✅ LightMes 绑定成功！\n"
    "您将在此收到：派工、报工审核、工资条等个人通知。\n\n"
    "若消息列表未显示本对话，请从企业微信【工作台】打开 lightmes，或回复任意消息完成激活。"
)

REPLY_ACK_TEXT = "已收到。LightMes 个人通知通道正常，派工/报工消息会推送到此对话。"


def send_bind_welcome(db: Session, tenant_id: int, userid: str) -> str | None:
    corp_id, secret, agent_id = get_wecom_credentials(db, tenant_id)
    if not corp_id or not secret or not userid:
        return None
    try:
        token = get_access_token(corp_id, secret)
        return send_text_message(token, userid, WELCOME_TEXT, agent_id=agent_id)
    except WecomApiError as e:
        logger.warning("wecom bind welcome failed userid=%s: %s", userid, e)
        return None
