# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""授权提供者钩子（ABAC 扩展的接入点，核心零业务依赖）。

核心只做三件事：
1. 维护一个「按扩展 key 分组」的提供者注册表；
2. 在管理端路由统一依赖 ``abac_guard`` 里征求每个提供者的意见；
3. 卸载/禁用扩展时由 ``hot_teardown_extension`` 调 ``unregister_all(key)`` 反注册。

没有扩展注册提供者时，``abac_guard`` 立即放行，行为与原来的纯 RBAC 完全一致；
有提供者时 **deny 优先**（任一提供者否决即拒绝），
提供者抛异常按 **fail-closed** 处理（拒绝并留痕），避免策略引擎坏掉就变成全放行。

提供者签名：``fn(user, request) -> list[dict]``，每项::

    {"allow": bool, "reason": str, "policy": str}

返回空列表表示「本提供者不表态」。提供者必须只读、秒回，不得发网络请求。
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request

from app.core.deps import get_current_user

logger = logging.getLogger("uvicorn.error")

Provider = Callable[[Any, Request], list[dict]]

_LOCK = threading.Lock()
_PROVIDERS: dict[str, Provider] = {}


def register_provider(key: str, fn: Provider) -> None:
    """注册（同 key 覆盖）一个授权提供者；由扩展 import 期调用，禁止 DB/网络 IO。"""
    if not callable(fn):
        raise TypeError("provider 必须可调用")
    with _LOCK:
        _PROVIDERS[key] = fn


def unregister_all(key: str) -> int:
    """摘除某扩展的全部提供者，返回移除数量（卸载/禁用/热更新用）。"""
    with _LOCK:
        return 1 if _PROVIDERS.pop(key, None) is not None else 0


def list_providers() -> list[str]:
    with _LOCK:
        return sorted(_PROVIDERS)


def _snapshot() -> dict[str, Provider]:
    with _LOCK:
        return dict(_PROVIDERS)


def evaluate(user: Any, request: Request) -> list[dict]:
    """征求全部提供者意见；异常折成一条 deny（fail-closed），并标注来源。"""
    out: list[dict] = []
    for key, fn in _snapshot().items():
        try:
            decisions = fn(user, request) or []
        except Exception as exc:  # fail-closed：策略坏了不能变成放行
            logger.error("[abac] 提供者 %s 执行异常，按拒绝处理: %s", key, exc)
            out.append({"allow": False, "reason": f"策略引擎异常（{type(exc).__name__}）",
                        "policy": "-", "ext_key": key})
            continue
        for d in decisions:
            if not isinstance(d, dict):
                continue
            out.append({
                "allow": bool(d.get("allow", True)),
                "reason": str(d.get("reason") or ""),
                "policy": str(d.get("policy") or "-"),
                "ext_key": key,
            })
    return out


def abac_guard(request: Request, user: Any = Depends(get_current_user)) -> None:
    """管理端统一依赖：无提供者时零成本放行；有否决则 403。"""
    if not _PROVIDERS:
        return
    decisions = evaluate(user, request)
    denials = [d for d in decisions if not d["allow"]]
    if denials:
        detail = "；".join(f"[{d['ext_key']}] {d['reason'] or '策略拒绝'}" for d in denials[:3])
        raise HTTPException(status_code=403, detail=f"数据权限校验未通过：{detail}")


def reset() -> None:
    """测试隔离：清空全部提供者。"""
    with _LOCK:
        _PROVIDERS.clear()
