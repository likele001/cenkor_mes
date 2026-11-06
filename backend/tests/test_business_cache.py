# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""业务读缓存单测：命中/失效/降级/类型保真/Session 事件。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core import business_cache as bc


class FakeRedis:
    """最小 Redis 打桩，只实现缓存层用到的三个命令。"""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.fail = False

    def get(self, key: str):
        if self.fail:
            raise RuntimeError("redis down")
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        if self.fail:
            raise RuntimeError("redis down")
        self.store[key] = value
        self.ttls[key] = ttl

    def incr(self, key: str) -> int:
        if self.fail:
            raise RuntimeError("redis down")
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = str(value)
        return value


@pytest.fixture
def fake(monkeypatch):
    r = FakeRedis()
    monkeypatch.setattr(bc, "get_redis", lambda: r)
    return r


def test_miss_then_hit(fake):
    calls = []

    def loader():
        calls.append(1)
        return {"value": 42}

    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, loader) == {"value": 42}
    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, loader) == {"value": 42}
    assert len(calls) == 1, "第二次应命中缓存，不得回源"


def test_ttl_is_passed_through(fake):
    bc.cached(bc.NS_PUBLIC_CONFIG, ("cfg",), 300, lambda: {"a": 1})
    assert 300 in fake.ttls.values()


def test_key_uses_full_business_params(fake):
    """不同参数必须落在不同 key，避免 period/limit/tenant 串数据。"""
    bc.cached(bc.NS_DASHBOARD, ("summary", "month", 1), 60, lambda: "m")
    bc.cached(bc.NS_DASHBOARD, ("summary", "week", 1), 60, lambda: "w")
    bc.cached(bc.NS_DASHBOARD, ("summary", "month", 2), 60, lambda: "m2")
    assert sum(1 for k in fake.store if ":ver" not in k) == 3


def test_bump_invalidates_namespace(fake):
    calls = []

    def loader():
        calls.append(1)
        return len(calls)

    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, loader) == 1
    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, loader) == 1
    assert bc.bump(bc.NS_DICTIONARY) is True
    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, loader) == 2
    assert int(fake.store[bc._version_key(bc.NS_DICTIONARY)]) == 1


def test_bump_is_namespace_scoped(fake):
    """bump 一个 namespace 不得影响另一个。"""
    bc.cached(bc.NS_DICTIONARY, ("types",), 600, lambda: "dict")
    bc.cached(bc.NS_PUBLIC_CONFIG, ("cfg",), 300, lambda: "pc")
    bc.bump(bc.NS_DICTIONARY)
    assert bc.cached(bc.NS_PUBLIC_CONFIG, ("cfg",), 300, lambda: "SHOULD_NOT_RUN") == "pc"


def test_redis_unavailable_falls_back(monkeypatch):
    monkeypatch.setattr(bc, "get_redis", lambda: None)
    calls = []

    def loader():
        calls.append(1)
        return {"ok": True}

    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, loader) == {"ok": True}
    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, loader) == {"ok": True}
    assert len(calls) == 2
    assert bc.bump(bc.NS_DICTIONARY) is False


def test_redis_client_raising_falls_back(monkeypatch):
    def boom():
        raise RuntimeError("redis exploded")

    monkeypatch.setattr(bc, "get_redis", boom)
    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, lambda: {"ok": 1}) == {"ok": 1}
    assert bc.bump(bc.NS_DICTIONARY) is False


def test_command_failure_still_returns_fresh_data(fake):
    fake.fail = True
    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, lambda: {"ok": 1}) == {"ok": 1}
    assert bc.bump(bc.NS_DICTIONARY) is False


def test_corrupted_cached_value_falls_back(fake):
    key = f"{bc._PREFIX}{bc.NS_DICTIONARY}:v0:types"
    fake.store[key] = "{not json"
    assert bc.cached(bc.NS_DICTIONARY, ("types",), 600, lambda: {"ok": 1}) == {"ok": 1}


def test_non_json_native_payload_is_not_cached(fake):
    """Decimal/date 等一律放弃缓存，保证响应类型零变化。"""
    payload = {"amount": Decimal("12.34")}
    result = bc.cached(bc.NS_DASHBOARD, ("summary",), 60, lambda: payload)
    assert result is payload
    assert not any(":ver" not in k for k in fake.store), "不得写入无法保真的缓存"


def test_nan_payload_is_not_cached(fake):
    payload = {"ratio": float("nan")}
    assert bc.cached(bc.NS_DASHBOARD, ("summary",), 60, lambda: payload) is payload
    assert not any(":ver" not in k for k in fake.store)


class _FakeSession:
    """只提供缓存层事件用到的四个属性，避免依赖真实 engine。"""

    def __init__(self, new=(), dirty=(), deleted=()):
        self.info: dict = {}
        self.new = list(new)
        self.dirty = list(dirty)
        self.deleted = list(deleted)


# 类名必须与 business_cache._MODEL_TO_NS 里的真实模型名一致（按类名字符串匹配）
class DictType:
    pass


class Order:
    pass


class Unrelated:
    pass


def test_session_event_commit_bumps_only_dirty_ns(fake):
    s = _FakeSession(new=[DictType(), Unrelated()])
    bc._mark_dirty(s)
    assert s.info[bc._SESSION_KEY] == {bc.NS_DICTIONARY}

    bc._apply_dirty(s)
    assert int(fake.store[bc._version_key(bc.NS_DICTIONARY)]) == 1
    assert bc._version_key(bc.NS_DASHBOARD) not in fake.store
    assert bc._SESSION_KEY not in s.info, "应用后必须清空，避免重复 bump"


def test_session_event_rollback_discards(fake):
    s = _FakeSession(dirty=[Order()])
    bc._mark_dirty(s)
    assert bc.NS_DASHBOARD in s.info[bc._SESSION_KEY]
    bc._discard_dirty(s)
    bc._apply_dirty(s)
    assert bc._version_key(bc.NS_DASHBOARD) not in fake.store, "rollback 不得失效"


def test_session_event_covers_multiple_ns(fake):
    s = _FakeSession(new=[DictType()], deleted=[Order()])
    bc._mark_dirty(s)
    bc._apply_dirty(s)
    assert int(fake.store[bc._version_key(bc.NS_DICTIONARY)]) == 1
    assert int(fake.store[bc._version_key(bc.NS_DASHBOARD)]) == 1


def test_watched_models_cover_dashboard_dependencies():
    """看板读的关键表必须在 watcher 里，漏一张就靠 TTL 兜底但会滞后。"""
    expected = {
        "Order", "OrderItem", "WorkOrder", "StatementPayment", "Customer", "Sku",
        "Report", "ReportUnit", "Task", "TaskAssignment", "SalaryItem",
    }
    assert expected <= {m for m, ns in bc._MODEL_TO_NS.items() if ns == bc.NS_DASHBOARD}
    assert bc._MODEL_TO_NS["TenantSetting"] == bc.NS_PUBLIC_CONFIG
    assert bc._MODEL_TO_NS["PlatformSetting"] == bc.NS_PUBLIC_CONFIG
    assert bc._MODEL_TO_NS["DictItem"] == bc.NS_DICTIONARY
