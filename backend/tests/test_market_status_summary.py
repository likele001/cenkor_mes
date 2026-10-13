# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""市场概况（`GET /admin/market/status` 的已购数/可更新数/最近到期）行为锁定。

这些数字全部来自进程内授权快照（sync_entitlements 写入），所以两条性质必须钉住：

1. `/status` **不发网络请求**。市场页加载即调它，一旦被 hub 的 15s 超时拖住，
   页面在 hub 抽风时会整块卡住；可达性只能读「最近一次同步的结果」。
2. **缺值即不提示**。老 hub 的 my-purchases 没有 latest_version，若把它当「有新版」，
   每个客户都会看到一条永远装不上的更新提醒。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

# market/router.py 顶层 import httpx；缺 httpx 的环境会在这里报收集错误，
# 用 importorskip 降级为跳过（与 test_market_product_axis.py 同一口径）。
pytest.importorskip("httpx", reason="market 路由依赖 httpx，该环境未安装")

from app.api.admin.market import router as market_mod  # noqa: E402
from app.api.admin.market.router import (  # noqa: E402
    INSTANCE_TOKEN_KEY,
    _is_newer,
    _status_summary,
    _ver_tuple,
    market_status,
    sync_entitlements,
)
from app.extension_host.state import runtime  # noqa: E402


def _ent(app_key: str, *, state: str = "active", latest: str = "", expires: str | None = None) -> dict:
    return {
        "app_key": app_key,
        "state": state,
        "latest_version": latest,
        "expires_at": expires,
        "license_key": f"LIC-{app_key}",
    }


def _installed(key: str, version: str) -> dict:
    """伪造一条本地已装记录：宿主只读 manifest.version。"""
    return {key: {"manifest": SimpleNamespace(version=version), "path": None}}


@pytest.fixture(autouse=True)
def clean_runtime(monkeypatch):
    """快照/已装/同步态全部换成用例自备的内存值，并且绝不落盘（store=None）。"""
    monkeypatch.setattr(runtime, "entitlements", {})
    monkeypatch.setattr(runtime, "installed", {})
    monkeypatch.setattr(runtime, "synced_at", "")
    monkeypatch.setattr(runtime, "entitlement_enforced", False)
    monkeypatch.setattr(runtime, "store", None)
    monkeypatch.setattr(market_mod, "_LAST_SYNC_OK", None)
    yield


@pytest.fixture
def settings(monkeypatch):
    """配置读写桩：默认已绑定（有 instance_token）。"""
    values = {INSTANCE_TOKEN_KEY: "tok-1"}

    def _get(db, key):  # noqa: ARG001
        return values.get(key, "")

    monkeypatch.setattr(market_mod, "_get_setting", _get)
    return values


# ---------- 版本比较 ----------


@pytest.mark.parametrize(
    "text, expected",
    [("1.0.10", (1, 0, 10)), ("v1.2", (1, 2)), ("1.0.1-rc2", (1, 0, 1)), ("", ()), ("dev", ())],
)
def test_ver_tuple(text, expected):
    assert _ver_tuple(text) == expected


def test_is_newer_handles_longer_segment_and_prerelease():
    assert _is_newer("1.0.10", "1.0.9") is True
    assert _is_newer("1.0", "1.0.0") is False      # 补零后相等，不算新版
    assert _is_newer("1.0.1", "1.0.1") is False
    assert _is_newer("1.0.1-rc2", "1.0.1") is False  # 预发布不催升级


def test_is_newer_refuses_missing_values():
    """任一为空一律 False：老 hub 不返回 latest_version 时不许催用户升级。"""
    assert _is_newer("", "1.0.0") is False
    assert _is_newer("1.0.1", "") is False
    assert _is_newer("dev", "1.0.0") is False


# ---------- 概况统计 ----------


def test_summary_zero_when_no_snapshot(settings):
    assert _status_summary(None) == {
        "hub_reachable": None,
        "purchased_count": 0,
        "updatable_count": 0,
        "nearest_expiry": None,
        "snapshot_synced_at": "",
    }


def test_purchased_counts_only_active(settings):
    runtime.entitlements = {
        "a": _ent("a"),
        "b": _ent("b", state="expired"),
        "c": _ent("c", state="revoked"),
    }
    assert _status_summary(None)["purchased_count"] == 1


def test_updatable_needs_installed_and_strictly_newer(settings):
    runtime.entitlements = {
        "has_new": _ent("has_new", latest="1.0.1"),
        "already_latest": _ent("already_latest", latest="1.0.1"),
        "not_installed": _ent("not_installed", latest="2.0.0"),
        "hub_says_nothing": _ent("hub_says_nothing", latest=""),
    }
    runtime.installed = {
        **_installed("has_new", "1.0.0"),
        **_installed("already_latest", "1.0.1"),
        **_installed("hub_says_nothing", "1.0.0"),
    }
    assert _status_summary(None)["updatable_count"] == 1


def test_nearest_expiry_picks_earliest_and_skips_permanent(settings):
    runtime.entitlements = {
        "perm": _ent("perm"),                                   # 买断：expires_at=None
        "later": _ent("later", expires="2027-01-05T00:00:00+00:00"),
        "sooner": _ent("sooner", expires="2026-11-02T00:00:00+00:00"),
        "junk": _ent("junk", expires="not-a-date"),            # 解析失败不参与
    }
    assert _status_summary(None)["nearest_expiry"] == "2026-11-02T00:00:00+00:00"


def test_nearest_expiry_ignores_lapsed_grace_of_state(settings):
    """过期项已归入 expired，不进「最近到期」，免得页面提示一个已经停用的授权。"""
    runtime.entitlements = {"gone": _ent("gone", state="expired", expires="2026-01-01T00:00:00+00:00")}
    summary = _status_summary(None)
    assert summary["nearest_expiry"] is None and summary["purchased_count"] == 0


# ---------- /status 端点 ----------


def test_status_endpoint_carries_summary(settings, monkeypatch):
    runtime.entitlements = {"a": _ent("a", latest="1.0.1")}
    runtime.installed = _installed("a", "1.0.0")
    runtime.synced_at = "2026-10-12T08:00:00Z"
    monkeypatch.setattr(market_mod, "_LAST_SYNC_OK", True)

    body = market_status(db=None)["data"]  # ok() 统一包一层 data
    assert body["product"] == market_mod.PRODUCT
    assert body["bound"] is True
    assert body["hub_reachable"] is True
    assert body["purchased_count"] == 1
    assert body["updatable_count"] == 1
    assert body["snapshot_synced_at"] == "2026-10-12T08:00:00Z"
    # 原有字段一个都不能少（老前端只认这五个）
    for k in ("hub_url", "product", "bound", "account", "instance_uid"):
        assert k in body


def test_status_never_touches_the_network(settings, monkeypatch):
    """hub 挂了也必须秒回：/status 只读内存快照，任何 httpx 调用都是回归。"""

    class _Boom:
        def __init__(self, *a, **k):
            raise AssertionError("/status 不该发网络请求")

    monkeypatch.setattr(market_mod.httpx, "Client", _Boom)
    assert market_status(db=None)["data"]["purchased_count"] == 0


# ---------- hub 可达性记账（sync_entitlements 的副作用） ----------


def test_sync_records_reachable_true(settings, monkeypatch):
    monkeypatch.setattr(market_mod, "_fetch_purchases_checked", lambda db: (True, []))
    assert sync_entitlements(None) is True
    assert market_status(db=None)["data"]["hub_reachable"] is True


def test_sync_records_unreachable_false(settings, monkeypatch):
    monkeypatch.setattr(market_mod, "_fetch_purchases_checked", lambda db: (False, []))
    assert sync_entitlements(None) is False
    # 失败开放：快照不清空，但可达性要如实记 False
    assert market_status(db=None)["data"]["hub_reachable"] is False


def test_unbound_leaves_reachable_unknown(monkeypatch, settings):
    settings[INSTANCE_TOKEN_KEY] = ""
    assert sync_entitlements(None) is False
    assert market_status(db=None)["data"]["hub_reachable"] is None
