from __future__ import annotations

"""飞书 interactive 消息卡片构建"""

import json
from typing import Any


def _level_color(level: str) -> str:
    if level == "danger" or level == "error":
        return "red"
    if level == "warning":
        return "orange"
    return "blue"


def _md_line(content: str) -> dict:
    return {"tag": "div", "text": {"tag": "lark_md", "content": content[:2000]}}


def _button(text: str, action: str, *, biz_type: str, biz_id: int, btn_type: str = "default") -> dict:
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text[:20]},
        "type": btn_type,
        "value": json.dumps(
            {
                "action": action,
                "biz_type": biz_type,
                "biz_id": int(biz_id),
            },
            ensure_ascii=False,
        ),
    }


def build_card(
    *,
    title: str,
    content: str,
    level: str = "info",
    event_code: str,
    biz_type: str | None = None,
    biz_id: int | None = None,
    h5_url: str | None = None,
    admin_url: str | None = None,
    include_audit_actions: bool = False,
    target_kind: str = "user",
) -> dict[str, Any]:
    elements: list[dict] = [_md_line(content.replace("\n", "\n"))]
    actions: list[dict] = []

    link = h5_url or admin_url
    # 按钮文案根据场景动态化，让卡片意图更清晰
    if event_code == "dispatch.assigned" and (h5_url or admin_url):
        btn_text = "立即报工"
    elif event_code.startswith("report") and admin_url:
        btn_text = "打开审核"
    else:
        btn_text = "查看详情"
    if link:
        actions.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": btn_text},
                "type": "primary",
                "multi_url": {"url": link, "pc_url": admin_url or link, "android_url": h5_url or link, "ios_url": h5_url or link},
            }
        )

    if (
        include_audit_actions
        and target_kind == "user"
        and biz_type
        and biz_id
        and event_code == "report.submitted"
    ):
        if biz_type == "report":
            actions.append(_button("初审通过", "report_leader_approve", biz_type=biz_type, biz_id=biz_id, btn_type="primary"))
            actions.append(_button("驳回", "report_reject", biz_type=biz_type, biz_id=biz_id, btn_type="danger"))
        elif biz_type == "report_unit":
            actions.append(_button("初审通过", "unit_leader_approve", biz_type=biz_type, biz_id=biz_id, btn_type="primary"))
            actions.append(_button("驳回", "unit_reject", biz_type=biz_type, biz_id=biz_id, btn_type="danger"))

    if actions:
        elements.append({"tag": "action", "actions": actions[:5]})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title[:100]},
            "template": _level_color(level),
        },
        "elements": elements,
    }


def card_content_json(card: dict) -> str:
    return json.dumps(card, ensure_ascii=False)
