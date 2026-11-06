# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""业务读缓存：public-config / 字典 / 经营看板聚合。

设计要点（改动前必读）：

1. **版本化 key，失效靠 INCR 而不是 DEL/SCAN**。key 形如
   ``cm:biz:{ns}:v{version}:{业务参数}``；bump 一次版本号，旧 key 全部变成
   孤儿由 TTL 自然回收。既避免 KEYS/SCAN 全库扫描（生产大忌），也从根本上
   杜绝「漏删某个 key 导致改了配置不生效」。
2. **失效由 SQLAlchemy Session 类级事件自动完成，业务代码零钩子**。
   沿用 services/dashboard_events.py 的成熟做法：before_flush 记脏、
   after_commit 才 bump、after_rollback 丢弃。只认真正提交的事务；
   模型映射用类名字符串，不 import models，避免循环依赖。
3. **Redis 任何故障一律降级回源**（连接失败、命令异常、反序列化异常），
   绝不因为缓存故障让接口 500。
4. **只缓存响应里的 data 部分，且只接受 JSON 原生类型**。遇到
   Decimal / date / ORM 对象等非原生类型直接放弃缓存并回源，
   保证响应结构与未缓存时完全一致，不产生静默回归。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, TypeVar

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

T = TypeVar("T")

_PREFIX = "cm:biz:"
_SESSION_KEY = "biz_cache_dirty_ns"

NS_PUBLIC_CONFIG = "pc"
NS_DICTIONARY = "dict"
NS_DASHBOARD = "dash"

# 看板是最终一致：短 TTL 兜底，即使某张写入表没被 watcher 覆盖也最多滞后 60s。
# 配置与字典变更频率低，可以给长一些。
TTL_PUBLIC_CONFIG = 300
TTL_DICTIONARY = 600
TTL_DASHBOARD = 60

# 类名 -> namespace。用字符串而非类对象，与 dashboard_events._channel_for 同一套
# 思路（也避开 SQLAlchemy 子类/代理对象让 isinstance 失真的问题）。
_MODEL_TO_NS: dict[str, str] = {
    # public-config 读 tenant_settings(company.*) 与 platform_settings(login_captcha_enabled)
    "TenantSetting": NS_PUBLIC_CONFIG,
    "PlatformSetting": NS_PUBLIC_CONFIG,
    # 字典
    "DictType": NS_DICTIONARY,
    "DictItem": NS_DICTIONARY,
    # 经营看板依赖的业务表：在 dashboard_events._WATCHED 基础上补了
    # StatementPayment(回款)、Customer、Sku，这三张看板也读但原 watcher 没盯。
    "Order": NS_DASHBOARD,
    "OrderItem": NS_DASHBOARD,
    "WorkOrder": NS_DASHBOARD,
    "Report": NS_DASHBOARD,
    "ReportUnit": NS_DASHBOARD,
    "ReportUnitAudit": NS_DASHBOARD,
    "Task": NS_DASHBOARD,
    "TaskAssignment": NS_DASHBOARD,
    "SalaryItem": NS_DASHBOARD,
    "StatementPayment": NS_DASHBOARD,
    "Customer": NS_DASHBOARD,
    "Sku": NS_DASHBOARD,
}


def _version_key(ns: str) -> str:
    return f"{_PREFIX}{ns}:ver"


def _redis():
    """get_redis 自身也包一层，保证任何异常都返回 None。"""
    try:
        return get_redis()
    except Exception as e:  # pragma: no cover - 理论分支，防御用
        logger.warning("biz cache redis client failed: %s", e)
        return None


def _version(r, ns: str) -> int:
    try:
        return int(r.get(_version_key(ns)) or 0)
    except Exception as e:
        logger.warning("biz cache version read failed ns=%s: %s", ns, e)
        # 返回 -1 让调用方走回源：后续命令同样会失败并被各自吞掉
        return -1


def bump(ns: str) -> bool:
    """让该 namespace 下所有缓存 key 一次性失效。失败只记日志，不影响业务事务。"""
    r = _redis()
    if r is None:
        return False
    try:
        r.incr(_version_key(ns))
        return True
    except Exception as e:
        logger.warning("biz cache bump failed ns=%s: %s", ns, e)
        return False


def cached(ns: str, parts: tuple[Any, ...], ttl: int, loader: Callable[[], T]) -> T:
    """读缓存；未命中或任何缓存故障都回源。

    Args:
        ns: namespace（失效的最小单位）。
        parts: 业务参数，拼进 key；必须能唯一确定这次查询（含 tenant / period / limit）。
        ttl: 秒。
        loader: 回源函数，仅未命中时调用。
    """
    r = _redis()
    if r is None:
        return loader()

    ver = _version(r, ns)
    key = f"{_PREFIX}{ns}:v{ver}:" + ":".join(str(p) for p in parts)
    try:
        raw = r.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as e:
        logger.warning("biz cache read failed key=%s: %s", key, e)
        # 读失败继续回源，不中断请求

    data = loader()

    # 只接受 JSON 原生类型；Decimal/date/ORM 对象等一律放弃缓存，
    # 避免序列化改变响应类型（静默回归）。
    try:
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        logger.debug("biz cache skip non-json-native payload key=%s", key)
        return data

    try:
        r.setex(key, ttl, payload)
    except Exception as e:
        logger.warning("biz cache write failed key=%s: %s", key, e)
    return data


# ---- Session 级失效：只认真正 commit 的事务 ----

def _mark_dirty(session: Session) -> None:
    dirty: set[str] = session.info.setdefault(_SESSION_KEY, set())
    for group in (session.new, session.dirty, session.deleted):
        for obj in group:
            ns = _MODEL_TO_NS.get(type(obj).__name__)
            if ns:
                dirty.add(ns)


def _apply_dirty(session: Session) -> None:
    namespaces = session.info.pop(_SESSION_KEY, None)
    if not namespaces:
        return
    for ns in namespaces:
        bump(ns)


def _discard_dirty(session: Session) -> None:
    session.info.pop(_SESSION_KEY, None)


@event.listens_for(Session, "before_flush")
def _on_before_flush(session, flush_context, instances) -> None:
    _mark_dirty(session)


@event.listens_for(Session, "after_commit")
def _on_after_commit(session) -> None:
    # after_commit 是同步调用，bump 内部已吞掉所有异常；
    # get_redis() 带 _client=False 哨兵，Redis 挂掉后不会每次事务都重试连接。
    _apply_dirty(session)


@event.listens_for(Session, "after_rollback")
def _on_after_rollback(session) -> None:
    _discard_dirty(session)
