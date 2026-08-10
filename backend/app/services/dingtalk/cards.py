"""钉钉 ActionCard 消息构建"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.services.dingtalk.card_action_tokens import create_card_action_token
from app.services.dingtalk.urls import get_card_action_base_url


def build_action_card(
    *,
    title: str,
    content: str,
    level: str = "info",
    event_code: str,
    biz_type: str | None = None,
    biz_id: int | None = None,
    tenant_id: int | None = None,
    h5_url: str | None = None,
    admin_url: str | None = None,
    include_audit_actions: bool = False,
    target_kind: str = "user",
    dingtalk_userid: str | None = None,
    cfg: dict | None = None,
) -> dict[str, Any]:
    link = h5_url or admin_url or ""
    btns: list[dict[str, str]] = []

    if link:
        btns.append({"title": "查看详情", "actionURL": link})

    base = get_card_action_base_url(cfg or {})
    if (
        include_audit_actions
        and target_kind == "user"
        and biz_type
        and biz_id
        and dingtalk_userid
        and base
        and event_code == "report.submitted"
    ):
        if biz_type == "report":
            for action, label in (("report_leader_approve", "初审通过"), ("report_reject", "驳回")):
                token = create_card_action_token(
                    dingtalk_userid=dingtalk_userid,
                    action=action,
                    biz_type=biz_type,
                    biz_id=biz_id,
                )
                btns.append({"title": label, "actionURL": f"{base}?token={quote(token)}"})
        elif biz_type == "report_unit":
            for action, label in (("unit_leader_approve", "初审通过"), ("unit_reject", "驳回")):
                token = create_card_action_token(
                    dingtalk_userid=dingtalk_userid,
                    action=action,
                    biz_type=biz_type,
                    biz_id=biz_id,
                )
                btns.append({"title": label, "actionURL": f"{base}?token={quote(token)}"})

    markdown = f"### {title}\n\n{content}"
    if link and not btns:
        markdown += f"\n\n[查看详情]({link})"

    if len(btns) == 1 and btns[0]["title"] == "查看详情":
        return {
            "title": title[:64],
            "markdown": markdown[:1000],
            "singleTitle": "查看详情",
            "singleURL": link,
        }

    return {
        "title": title[:64],
        "markdown": markdown[:1000],
        "btnOrientation": "0",
        "btns": btns[:4],
    }


def build_work_msg_action_card(card: dict[str, Any]) -> dict[str, Any]:
    return {"msgtype": "action_card", "action_card": card}


def build_work_msg_markdown(title: str, content: str, link: str | None = None) -> dict[str, Any]:
    md = f"### {title}\n\n{content}"
    if link:
        md += f"\n\n[查看详情]({link})"
    return {"msgtype": "markdown", "markdown": {"title": title[:64], "text": md[:4000]}}
