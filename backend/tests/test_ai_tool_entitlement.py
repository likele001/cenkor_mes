# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""AI 助手的工具级授权门控。

背景：ai_assistant 把 6 个付费扩展的分析能力聚合成了工具（biz_overview / analyze_anomalies /
ask_knowledge ...）。这些工具靠权限码 ``ext.<key>.view`` 归属到扩展，但权限码只管「这个用户
有没有该权限」，不管「这个扩展还在不在、授权有没有过期」。于是 license 到期后，模型仍会
看到一个调用必然 403 的工具，答非所问。这里把「扩展可用性」也纳入工具清单与执行判定。
"""
from __future__ import annotations

import pytest

from app.extension_host.state import runtime

# 本模块全部用例都直接操作 ai_assistant 扩展的内部函数（_REGISTRY / _tools_for_user ...）。
# backend/extensions/ 是运行期安装的商业扩展，被 .gitignore 忽略，源码在私有仓库 mes-extensions；
# 公开仓库的干净检出里没有这个包，模块级 import 会直接 ModuleNotFoundError 打断整个收集阶段。
# 用 importorskip 让「本地有扩展就跑、CI 无扩展就整模块跳过」，与 tests/test_h5_ai_contract.py
# 的 HAS_EXT 约定一致。
ai_router = pytest.importorskip(
    'extensions.ai_assistant.router',
    reason='商业扩展源码在私有仓库，公开仓库无 extensions/ 时跳过',
)
Tool = ai_router.Tool


class _User:
    """够用的用户替身：超级管理员，权限判定直接放行。"""

    is_superuser = True
    id = 1


def _tool(name: str, perms: list[str], *, readonly: bool = True, handler=None) -> Tool:
    return Tool(
        name=name,
        description="test",
        parameters={"type": "object", "properties": {}},
        handler=handler or (lambda: {"ok": True}),
        require_permissions=perms,
        is_readonly=readonly,
    )


@pytest.fixture
def isolated_registry(monkeypatch):
    """把工具注册表清空，避免与真实工具互相干扰；结束后恢复。"""
    original = dict(ai_router._REGISTRY)
    ai_router._REGISTRY.clear()
    yield ai_router._REGISTRY
    ai_router._REGISTRY.clear()
    ai_router._REGISTRY.update(original)


@pytest.fixture
def ext_runtime(monkeypatch):
    """控制宿主扩展状态：installed / 禁用项 / 授权状态。"""

    def _setup(installed=("ai_insight",), disabled=(), entitlements=None, enforced=True):
        monkeypatch.setattr(runtime, "installed", {k: {"manifest": None} for k in installed})
        monkeypatch.setattr(runtime, "overrides", {k: "disabled" for k in disabled})
        monkeypatch.setattr(runtime, "entitlements", entitlements or {})
        monkeypatch.setattr(runtime, "entitlement_enforced", enforced)
        return runtime

    return _setup


# ── 归属映射 ─────────────────────────────────────────────────────────


def test_tool_extension_from_permission_code():
    assert ai_router._tool_extension(_tool("biz_insight", ["ext.ai_insight.view"])) == "ai_insight"
    assert ai_router._tool_extension(_tool("ask_knowledge", ["ext.ai_knowledge.view"])) == "ai_knowledge"
    assert ai_router._tool_extension(_tool("overview_stats", ["ai.use"])) is None
    assert ai_router._tool_extension(_tool("open_tool", [])) is None


# ── 失败开放 ─────────────────────────────────────────────────────────


def test_fail_open_when_host_not_scanned(ext_runtime, isolated_registry, session):
    """runtime.installed 为空（单测 / CLI / 宿主未启动）时不能把工具全掐掉。"""
    ext_runtime(installed=())
    isolated_registry["biz_insight"] = _tool("biz_insight", ["ext.ai_insight.view"])

    names = [t.name for t in ai_router._tools_for_user(session, _User())]
    assert names == ["biz_insight"]


def test_fail_open_on_state_error(ext_runtime, isolated_registry, session, monkeypatch):
    """宿主状态读取异常（文件损坏等）时同样放行，不能让 AI 助手整体失能。"""
    ext_runtime()
    isolated_registry["biz_insight"] = _tool("biz_insight", ["ext.ai_insight.view"])
    monkeypatch.setattr(runtime, "is_enabled", lambda key: (_ for _ in ()).throw(RuntimeError("boom")))

    assert [t.name for t in ai_router._tools_for_user(session, _User())] == ["biz_insight"]


# ── 授权门控 ─────────────────────────────────────────────────────────


def test_unlicensed_extension_tool_is_hidden(ext_runtime, isolated_registry, session):
    """扩展已装但授权 expired：工具不进 schema，模型看不到也不该提。"""
    ext_runtime(installed=("ai_insight",), entitlements={"ai_insight": {"state": "expired"}})
    isolated_registry["biz_insight"] = _tool("biz_insight", ["ext.ai_insight.view"])
    isolated_registry["overview_stats"] = _tool("overview_stats", ["ai.use"])

    names = {t.name for t in ai_router._tools_for_user(session, _User())}
    assert names == {"overview_stats"}  # 核心表工具不受影响


def test_active_entitlement_keeps_tool(ext_runtime, isolated_registry, session):
    ext_runtime(installed=("ai_insight",), entitlements={"ai_insight": {"state": "active"}})
    isolated_registry["biz_insight"] = _tool("biz_insight", ["ext.ai_insight.view"])

    assert [t.name for t in ai_router._tools_for_user(session, _User())] == ["biz_insight"]


def test_disabled_extension_tool_is_hidden(ext_runtime, isolated_registry, session):
    """本地手动禁用（overrides=disabled）同样要摘掉工具。"""
    ext_runtime(installed=("ai_insight",), disabled=("ai_insight",), entitlements={"ai_insight": {"state": "active"}})
    isolated_registry["biz_insight"] = _tool("biz_insight", ["ext.ai_insight.view"])

    assert ai_router._tools_for_user(session, _User()) == []


def test_execute_tool_rejects_unlicensed_extension(ext_runtime, isolated_registry, session):
    """schema 之外的第二道闸：模型凭旧上下文调用失效扩展的工具，要返回可读原因。"""
    ext_runtime(installed=("ai_insight",), entitlements={"ai_insight": {"state": "revoked"}})
    isolated_registry["biz_insight"] = _tool("biz_insight", ["ext.ai_insight.view"])

    result = ai_router._execute_tool(session, _User(), "biz_insight", {}, None)
    assert result["error"] == "extension_unavailable"
    assert "ai_insight" in result["message"]


def test_execute_tool_still_runs_when_enabled(ext_runtime, isolated_registry, session):
    ext_runtime(installed=("ai_insight",), entitlements={"ai_insight": {"state": "active"}})
    isolated_registry["biz_insight"] = _tool("biz_insight", ["ext.ai_insight.view"])

    assert ai_router._execute_tool(session, _User(), "biz_insight", {}, None) == {"ok": True}


# ── 原因区分（前端据此提示「没权限」还是「未购买」）─────────────────


def test_block_reason_distinguishes_causes(ext_runtime, isolated_registry, session):
    ext_runtime(installed=(), entitlements={})
    t_ext = _tool("biz_insight", ["ext.ai_insight.view"])
    t_write = _tool("create_order", ["ai.use"], readonly=False)

    assert ai_router._tool_block_reason(session, _User(), t_ext, gateway_ready=True) is None
    # 写工具在网关未就绪时不暴露
    assert ai_router._tool_block_reason(session, _User(), t_write, gateway_ready=False) == "gateway_not_ready"

    ext_runtime(installed=("ai_insight",), entitlements={"ai_insight": {"state": "expired"}})
    assert ai_router._tool_block_reason(session, _User(), t_ext, gateway_ready=True) == "extension_unavailable"

    class _NoPerm(_User):
        is_superuser = False

    assert ai_router._tool_block_reason(session, _NoPerm(), t_ext, gateway_ready=True) == "no_permission"
