"""绑定后欢迎消息"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.dingtalk.cards import build_work_msg_markdown
from app.services.dingtalk.client import DingtalkApiError, get_access_token, send_work_notification
from app.services.dingtalk.settings import get_dingtalk_credentials

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "✅ LightMes 绑定成功！\n"
    "您将在此收到：派工、报工审核、工资条等个人通知。\n\n"
    "请从钉钉【工作台】打开本应用查看工作通知。"
)


def send_bind_welcome(db: Session, userid: str) -> str | None:
    _, app_key, app_secret, agent_id = get_dingtalk_credentials(db)
    if not app_key or not app_secret or not userid or not agent_id:
        return None
    try:
        token = get_access_token(app_key, app_secret)
        msg = build_work_msg_markdown("LightMes 绑定成功", WELCOME_TEXT)
        return send_work_notification(token, agent_id=agent_id, userid=userid, msg=msg)
    except DingtalkApiError as e:
        logger.warning("dingtalk bind welcome failed userid=%s: %s", userid, e)
        return None
