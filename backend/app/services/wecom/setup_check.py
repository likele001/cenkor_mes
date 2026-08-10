"""企业微信配置检查"""

from __future__ import annotations

from app.services.wecom.client import WecomApiError, get_access_token, get_agent
from app.services.wecom.settings import get_wecom_credentials


def build_setup_check(*, corp_id: str, corp_secret: str, agent_id: str, callback_url: str) -> dict:
    steps = []
    ready = True

    # 检查 access_token
    token_ok = False
    try:
        token = get_access_token(corp_id, corp_secret)
        token_ok = bool(token)
    except WecomApiError:
        pass

    steps.append({
        "title": "CorpID / CorpSecret 验证",
        "detail": "正常" if token_ok else "请检查 CorpID 和 CorpSecret 是否正确",
        "done": token_ok,
    })
    if not token_ok:
        ready = False

    # 检查应用 AgentID
    agent_ok = False
    agent_name = ""
    agent_detail = "请检查 AgentID 是否正确，应用是否已创建"
    if token_ok and agent_id:
        try:
            info = get_agent(token, int(agent_id))
            agent_name = info.get("name") or ""
            agent_ok = True
            agent_detail = f"应用名称：{agent_name}"
        except WecomApiError as e:
            if int(e.code) == 60020:
                agent_detail = (
                    f"AgentID {agent_id} 可能正确，但当前服务器 IP 未加入企业微信「企业可信 IP」白名单（errcode 60020）。"
                    "请到企业微信管理后台 → 应用管理 → 你的应用 → 开发者接口 → 企业可信IP，"
                    "添加本服务器公网 IP 后重试。"
                )
            else:
                agent_detail = f"AgentID 校验失败：{e.msg}（errcode {e.code}）"
        except ValueError:
            agent_detail = f"AgentID 格式无效：{agent_id}"
    elif token_ok and not agent_id:
        agent_detail = "请填写 Agent ID"

    steps.append({
        "title": "应用 AgentID 验证",
        "detail": agent_detail,
        "done": agent_ok if agent_id else False,
    })
    if not agent_ok:
        ready = False

    steps.append({
        "title": "设置可信域名与回调 URL",
        "detail": "企业微信后台 → 应用管理 → 设置可信域名；回调 URL：" + (callback_url or "见本页回调地址"),
        "done": None,
    })

    steps.append({
        "title": "设置应用可见范围",
        "detail": "企业微信后台 → 应用管理 → 可用范围 → 选择全部成员或指定部门",
        "done": None,
    })

    return {
        "ready": ready,
        "agent_name": agent_name,
        "steps": steps,
    }
