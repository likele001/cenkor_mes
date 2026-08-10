"""钉钉机器人消息回调处理"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def verify_robot_signature(timestamp: str, sign: str, app_secret: str) -> bool:
    """Verify DingTalk robot message callback signature.

    DingTalk signs with: base64(HMAC-SHA256(app_secret, timestamp + "\n" + app_secret))
    The timestamp is in milliseconds.
    """
    if not all([timestamp, sign, app_secret]):
        return False
    try:
        # Check timestamp is within 1 hour
        ts_ms = int(timestamp)
        now_ms = int(time.time() * 1000)
        if abs(now_ms - ts_ms) > 3600000:
            logger.warning("dingtalk signature timestamp expired: %s", timestamp)
            return False
        string_to_sign = f"{timestamp}\n{app_secret}"
        hmac_code = hmac.new(
            app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        expected_sign = base64.b64encode(hmac_code).decode("utf-8")
        return hmac.compare_digest(sign, expected_sign)
    except Exception as e:
        logger.warning("dingtalk signature verify error: %s", e)
        return False


def parse_robot_message(body: dict) -> dict[str, Any]:
    """Parse DingTalk robot message callback body.

    Returns dict with: sender_id, sender_nick, text, conversation_type, chatbot_user_id, msg_id
    """
    msg_type = (body.get("msgtype") or "").strip()
    text_content = ""
    if msg_type == "text":
        text_obj = body.get("text") or {}
        text_content = (text_obj.get("content") or "").strip()
    sender_id = (body.get("senderId") or body.get("senderStaffId") or "").strip()
    sender_nick = (body.get("senderNick") or "").strip()
    conversation_type = body.get("conversationType") or "1"  # 1=P2P, 2=group
    chatbot_user_id = (body.get("chatbotUserId") or "").strip()
    msg_id = (body.get("msgId") or "").strip()
    # DingTalk also sends senderCorpId and senderUnionId
    sender_corp_id = (body.get("senderCorpId") or "").strip()
    return {
        "sender_id": sender_id,
        "sender_nick": sender_nick,
        "text": text_content,
        "conversation_type": conversation_type,
        "chatbot_user_id": chatbot_user_id,
        "msg_id": msg_id,
        "sender_corp_id": sender_corp_id,
        "msg_type": msg_type,
    }
