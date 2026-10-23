# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""跨产品误装护栏：hub 下发之外，实例侧自己再认一次产品轴。

三道闸信的东西不同，缺一不可：
- `X-App-Product` 响应头：hub 按 `license.product` 发的权威轴。对不写 manifest.product
  的包同样生效——`mes-extensions/` 下 23 个包全都未声明，只靠包内字段等于没拦。
- `license.product`（已购列表里的字段）：下载之前就判，外产品授权不该被 activate 绑进来。
- `manifest.product`：开发者自述字段，只在包自己声明时校验，兜住不经 hub 的落盘场景。

三者都必须「缺值即放行」：老 hub 不回头像/不返回 product，写死 `!=` 会把存量安装全挡掉。
"""
from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException

# market/router.py 顶层 import httpx；缺 httpx 的环境（如只装了最小依赖的 venv）
# 会在这里报收集错误，红掉整个套件——用 importorskip 降级为跳过。
pytest.importorskip("httpx", reason="market 路由依赖 httpx，该环境未安装")

import httpx  # noqa: E402
from app.api.admin.market import router as market_mod  # noqa: E402
from app.api.admin.market.router import (  # noqa: E402
    PRODUCT,
    InstallIn,
    _download_package,
    _install_extension,
    install_app,
)
from app.extension_host.state import StateStore, runtime  # noqa: E402


def _pkg(manifest: dict, *, router_py: str = "router = None\n") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr("router.py", router_py)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def ext_dir(tmp_path, monkeypatch):
    """安装目录指向临时目录，绝不碰仓库里的 extensions/。"""
    d = tmp_path / "extensions"
    monkeypatch.setattr(market_mod, "extensions_base_dir", lambda: d)
    # 生命周期状态是进程内单例：每个用例都从干净的 runtime 起步，
    # 否则前一个用例装过的 key 会让后一个用例被判成「同版本不同包」。
    runtime.reset()
    runtime.extensions_dir = d
    runtime.store = StateStore(d / ".state")
    yield d
    runtime.reset()


# ---------- 第一道：X-App-Product 响应头 ----------


@pytest.fixture
def hub(monkeypatch):
    """把 install_app 的三个网络/副作用出口换成桩，记录走到了哪几步。"""
    state = SimpleNamespace(purchases=[], calls=[], package=(b"", ""), product_header=None)

    monkeypatch.setattr(market_mod, "_fetch_purchases", lambda db: list(state.purchases))
    monkeypatch.setattr(
        market_mod, "_activate_license", lambda db, lk, request: state.calls.append("activate")
    )
    monkeypatch.setattr(
        market_mod,
        "_download_package",
        lambda db, app_key, lk: (state.calls.append("download") or state.package),
    )
    def _fake_install(app, package_bytes, app_key, **kwargs):
        """走真实落盘（staging/product 闸），把挂载/迁移留给隔离环境。"""
        saved = _install_extension(package_bytes, app_key)
        state.calls.append("hot")
        return {
            "ok": True,
            "action": "install",
            "key": app_key,
            "from_version": "",
            "to_version": saved["version"],
            "sha256": saved["sha256"],
            "health": {"ok": True},
            **saved,
        }

    monkeypatch.setattr(market_mod, "install_or_update", _fake_install)
    return state


def _install(state):
    return install_app(InstallIn(app_key="demo"), SimpleNamespace(app=FastAPI()), db=None)


def test_header_from_foreign_product_blocks_even_without_manifest_field(hub, ext_dir):
    """核心用例：包内不声明 product（现存 23 个包都这样），但 hub 说是别的产品 → 必须拦。"""
    hub.purchases = [{"app_key": "demo", "license_key": "LIC-1", "status": "active"}]
    hub.package = (_pkg({"key": "demo", "version": "1.0.0"}), "cenkor-process")
    with pytest.raises(HTTPException) as exc:
        _install(hub)
    assert exc.value.status_code == 400
    assert hub.calls == ["activate", "download"], f"不该进入安装/热挂载：{hub.calls}"
    assert not (ext_dir / "demo").exists(), "被拦下的包不该落盘"


def test_header_matching_installs(hub, ext_dir):
    hub.purchases = [{"app_key": "demo", "license_key": "LIC-1", "status": "active"}]
    hub.package = (_pkg({"key": "demo", "version": "1.0.0"}), PRODUCT)
    _install(hub)
    assert hub.calls == ["activate", "download", "hot"]
    assert (ext_dir / "demo").is_dir()


def test_header_absent_falls_through_to_manifest_gate(hub, ext_dir):
    """老 hub 不返回该头（空串）：放行到下一道闸，不能因为 hub 版本低就装不了。"""
    hub.purchases = [{"app_key": "demo", "license_key": "LIC-1", "status": "active"}]
    hub.package = (_pkg({"key": "demo", "version": "1.0.0"}), "")
    _install(hub)
    assert hub.calls == ["activate", "download", "hot"], f"放行流程不完整：{hub.calls}"


# ---------- license.product（下载前）----------


def test_license_from_foreign_product_never_activates(hub):
    """授权属于别的产品：400，且不激活、不下载——外产品 license 不该绑进本实例。"""
    hub.purchases = [
        {"app_key": "demo", "license_key": "LIC-1", "status": "active", "product": "cenkor-process"}
    ]
    with pytest.raises(HTTPException) as exc:
        _install(hub)
    assert exc.value.status_code == 400
    assert hub.calls == [], f"不该发生任何副作用，实际：{hub.calls}"


def test_license_with_matching_product_passes(hub, ext_dir):
    hub.purchases = [
        {"app_key": "demo", "license_key": "LIC-1", "status": "active", "product": PRODUCT}
    ]
    hub.package = (_pkg({"key": "demo", "version": "1.0.0", "product": PRODUCT}), PRODUCT)
    _install(hub)
    assert hub.calls == ["activate", "download", "hot"]


# ---------- manifest.product（兜底闸）与真实响应头解析 ----------


def test_legacy_manifest_without_product_still_installs(ext_dir):
    """存量包没写 product：必须照常装上（防我把判断写死）。"""
    result = _install_extension(_pkg({"key": "mold_management", "version": "1.0.0"}), "mold_management")
    assert result["key"] == "mold_management"
    assert (ext_dir / "mold_management" / "manifest.json").is_file()


def test_matching_product_installs(ext_dir):
    result = _install_extension(_pkg({"key": "demo", "version": "1.0.0", "product": PRODUCT}), "demo")
    assert result["key"] == "demo"
    assert (ext_dir / "demo" / "router.py").is_file()


def test_foreign_product_rejected_and_nothing_written(ext_dir):
    """别的产品声明的包：400，且一个文件都不该落盘。"""
    with pytest.raises(HTTPException) as exc:
        _install_extension(
            _pkg({"key": "demo", "version": "1.0.0", "product": "cenkor-process"}), "demo"
        )
    assert exc.value.status_code == 400
    assert not (ext_dir / "demo").exists()


def test_foreign_product_does_not_wipe_existing_install(ext_dir):
    """最关键的一条：护栏必须排在 rmtree 之前。

    同 key 的包被跨产品误发时，若先删后判，客户库里已装好的扩展会被连锅端掉——
    新的装不上、原来的也没了，比误装本身更难向客户解释。
    """
    _install_extension(
        _pkg({"key": "demo", "version": "1.0.0", "product": PRODUCT}, router_py="GOOD = True\n"), "demo"
    )
    marker = ext_dir / "demo" / "router.py"
    assert "GOOD" in marker.read_text()

    with pytest.raises(HTTPException) as exc:
        _install_extension(
            _pkg({"key": "demo", "version": "2.0.0", "product": "cenkor-process"}, router_py="BAD\n"),
            "demo",
        )
    assert exc.value.status_code == 400
    assert "GOOD" in marker.read_text(), "跨产品包不该把已装扩展删掉或覆盖"
    kept = json.loads((marker.parent / "manifest.json").read_text())
    assert kept["version"] == "1.0.0"


@pytest.mark.parametrize(
    "headers,expected",
    [
        ({"X-App-Product": "cenkormes"}, "cenkormes"),
        ({"x-app-product": "cenkormes"}, "cenkormes"),  # HTTP 头大小写不敏感
        ({}, ""),  # 老 hub / 中转不透传 → 空串放行
        ({"X-App-Product": "  cenkormes  "}, "cenkormes"),
    ],
)
def test_download_package_parses_product_header(monkeypatch, headers, expected):
    """真解析一遍响应头，别只测桩。"""
    payload = b"PK-fake-zip"

    class _Resp:
        status_code = 200
        content = payload
        text = ""

        def __init__(self):
            # 用 httpx 自己的 Headers：真环境里响应头大小写不敏感，
            # 拿普通 dict 当替身会把「大小写」这条语义测漏。
            self.headers = httpx.Headers(headers)

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            return _Resp()

    monkeypatch.setattr(market_mod.httpx, "Client", _Client)
    monkeypatch.setattr(market_mod, "_store_url", lambda db, path: f"http://hub.invalid/{path}")
    content, product = _download_package(db=None, app_key="demo", license_key="LIC-1")
    assert content == payload
    assert product == expected
