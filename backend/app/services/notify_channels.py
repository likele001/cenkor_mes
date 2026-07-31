"""消息通道枚举与公共数据模型"""

from __future__ import annotations

from enum import Enum
from typing import Any


class Channel(str, Enum):
    """推送通道"""

    FEISHU = "feishu"
    WECOM = "wecom"
    DINGTALK = "dingtalk"
    IN_APP = "in_app"  # 系统内通知


class TargetKind(str, Enum):
    """推送目标类型"""

    USER = "user"  # 个人（userid / open_id）
    CHAT = "chat"  # 飞书群（chat_id）
    WEBHOOK = "webhook"  # 企微/钉钉 webhook 群


class PushTarget(dict):
    """统一推送目标描述"""

    @classmethod
    def user(cls, channel: str, ref: str, user_id: int | None = None) -> "PushTarget":
        return cls(channel=channel, kind=TargetKind.USER.value, ref=ref, user_id=user_id)

    @classmethod
    def chat(cls, channel: str, ref: str, group_code: str = "") -> "PushTarget":
        return cls(channel=channel, kind=TargetKind.CHAT.value, ref=ref, group_code=group_code)

    @classmethod
    def webhook(cls, channel: str, ref: str, group_code: str = "", webhook_secret: str = "") -> "PushTarget":
        return cls(
            channel=channel,
            kind=TargetKind.WEBHOOK.value,
            ref=ref,
            group_code=group_code,
            webhook_secret=webhook_secret,
        )


# 事件分类：仅 personal（按用户绑定分流）
PERSONAL_EVENTS = frozenset({
    "dispatch.assigned",
    "report.leader_approved",
    "report.qc_approved",
    "report.rejected",
    "salary.slip_remind",
    "salary.slip_reset",
})

# 事件分类：仅群（不走个人）
GROUP_ONLY_EVENTS = frozenset({
    "alert",
    "brief.daily",
    "plan.automation_failed",
    "order.customer_submitted",
})

# 事件分类：个人 + 群（混合）
MIXED_EVENTS = frozenset({
    "salary.slip_rejected",  # 拒签同时通知老板个人 + 管理群
})

# 事件分类：按 rules.targets 解析（部门班组长/车间负责人等）
RULE_BASED_EVENTS = frozenset({
    "report.submitted",  # 推送给部门班组长 + 车间负责人
})

# 事件专属群组（事件触发时按群组 code 分发）
EVENT_GROUP_CODES: dict[str, list[str]] = {
    "alert": ["management", "factory"],
    "brief.daily": ["management", "factory"],
    "plan.automation_failed": ["management"],
    "order.customer_submitted": ["management"],
    "salary.slip_rejected": ["management"],
    "report.submitted": ["production"],
}


def is_personal_event(event_code: str) -> bool:
    return event_code in PERSONAL_EVENTS


def is_group_only_event(event_code: str) -> bool:
    return event_code in GROUP_ONLY_EVENTS


def is_mixed_event(event_code: str) -> bool:
    return event_code in MIXED_EVENTS


def is_rule_based_event(event_code: str) -> bool:
    return event_code in RULE_BASED_EVENTS
