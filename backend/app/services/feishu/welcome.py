"""绑定后欢迎消息与单聊激活"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.feishu.client import FeishuApiError, get_tenant_access_token, send_text_message
from app.services.feishu.delivery import FEISHU_BOT_APPLINK
from app.services.feishu.settings import get_feishu_credentials

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "✅ LightMes 绑定成功！\n"
    "您将在此收到：派工、报工审核、工资条等个人通知。\n\n"
    "若消息列表未显示本对话，请从飞书【工作台】打开 lightmes，或回复任意消息完成激活。"
)

P2P_ENTER_TEXT = (
    "欢迎使用 LightMes 生产通知。\n"
    "派工、报工结果、工资提醒会推送到此对话。\n"
    "您也可回复「帮助」查看说明。"
)

REPLY_ACK_TEXT = (
    "已收到。LightMes 个人通知通道正常，派工/报工消息会推送到此对话。"
)


def send_bind_welcome(db: Session, open_id: str) -> str | None:
    app_id, secret = get_feishu_credentials(db)
    if not app_id or not secret or not open_id:
        return None
    try:
        token = get_tenant_access_token(app_id, secret)
        return send_text_message(
            access_token=token,
            receive_id=open_id,
            receive_id_type="open_id",
            text=WELCOME_TEXT,
        )
    except FeishuApiError as e:
        logger.warning("feishu bind welcome failed open_id=%s: %s", open_id, e)
        return None


def get_bot_open_link(db: Session) -> str:
    app_id, _ = get_feishu_credentials(db)
    if not app_id:
        return ""
    return FEISHU_BOT_APPLINK.format(app_id=app_id)
