from __future__ import annotations

"""企业微信消息卡片构建（template_card）"""

from typing import Any


def _level_color(level: str) -> str:
    if level == "danger" or level == "error":
        return "red"
    if level == "warning":
        return "orange"
    return "blue"


def _resolve_btn_text(*, event_code: str, h5_url: str | None, admin_url: str | None) -> str:
    """根据事件类型 + URL 推断按钮文案"""
    if event_code == "dispatch.assigned" and (h5_url or admin_url):
        return "立即报工"
    if event_code and event_code.startswith("report") and admin_url:
        return "打开审核"
    return "查看详情"


def build_template_card(
    *,
    title: str,
    content: str,
    level: str = "info",
    event_code: str | None = None,
    biz_type: str | None = None,
    biz_id: int | None = None,
    h5_url: str | None = None,
    admin_url: str | None = None,
) -> dict[str, Any]:
    link = h5_url or admin_url or ""
    btn_text = _resolve_btn_text(event_code=event_code or "", h5_url=h5_url, admin_url=admin_url)
    card: dict[str, Any] = {
        "card_type": "text_notice",
        "source": {
            "icon_url": "",
            "desc": "LightMes",
            "desc_color": 0,
        },
        "main_title": {
            "title": title[:64],
            "desc": content[:512],
        },
        "emphasis_content": {
            "title": "",
            "desc": "",
        },
        "sub_title_text": content[:512],
        "horizontal_content_list": [],
        "jump_list": [],
        "card_action": {
            "type": 1,
            "url": link,
        },
    }

    if link:
        card["jump_list"].append({
            "type": 1,
            "title": btn_text,
            "url": link,
        })

    return card


def build_markdown_content(
    *,
    title: str,
    content: str,
    level: str = "info",
    event_code: str | None = None,
    h5_url: str | None = None,
    admin_url: str | None = None,
) -> str:
    link = h5_url or admin_url or ""
    btn_text = _resolve_btn_text(event_code=event_code or "", h5_url=h5_url, admin_url=admin_url)
    parts = [f"## {title}", content]
    if link:
        parts.append(f"[{btn_text}]({link})")
    return "\n\n".join(parts)


def build_text_content(
    title: str,
    content: str,
    h5_url: str | None = None,
    admin_url: str | None = None,
    event_code: str | None = None,
) -> str:
    link = h5_url or admin_url or ""
    btn_text = _resolve_btn_text(event_code=event_code or "", h5_url=h5_url, admin_url=admin_url)
    text = f"{title}\n\n{content}"
    if link:
        text += f"\n\n{btn_text}：{link}"
    return text
