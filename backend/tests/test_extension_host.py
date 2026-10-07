# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主闭环测试：扫描 → 迁移 → 挂载 → 门控 → 授权切换 → 样例包。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.extension_host.loader import mount_extensions, run_extension_migrations, scan_extensions
from app.extension_host.manifest import ManifestError, load_manifest
from app.extension_host.state import runtime

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "extensions_samples" / "quotation_demo"


@pytest.fixture(autouse=True)
def _isolate_runtime():
    """每个测试前后重置宿主运行时（模块级单例隔离）。"""
    runtime.reset()
    yield
    runtime.reset()


def _write_ext(base: Path, key: str = "demo_ext", version: str = "1.0.0", sql: str = "") -> Path:
    """在 base 下生成一个最小扩展。"""
    ext = base / key
    (ext / "frontend").mkdir(parents=True, exist_ok=True)
    (ext / "manifest.json").write_text(
        json.dumps(
            {
                "key": key,
                "name": f"演示扩展 {key}",
                "version": version,
                "permissions": [{"code": f"ext.{key}.view", "name": f"查看 {key}"}],
                "menus": [{"title": "演示", "path": f"/ext/{key}", "icon": "Document"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (ext / "router.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.get('/ping')\n"
        "def ping():\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )
    if sql:
        (ext / "migrations.sql").write_text(sql, encoding="utf-8")
    (ext / "frontend" / "plugin.js").write_text(
        f"window.__registerExtension && window.__registerExtension({{key:'{key}'}});",
        encoding="utf-8",
    )
    return ext


def test_scan_and_manifest_validation(tmp_path: Path):
    """扫描：合法扩展收录；无 manifest 跳过；key 与目录名不一致报错。"""
    _write_ext(tmp_path, key="good_ext")
    (tmp_path / "no_manifest").mkdir()
    bad = tmp_path / "bad_key"
    bad.mkdir()
    (bad / "manifest.json").write_text(
        json.dumps({"key": "other", "name": "x", "version": "1.0.0"}), encoding="utf-8"
    )

    found = scan_extensions(tmp_path)
    assert set(found) == {"good_ext"}

    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_mount_and_gate_local_mode(tmp_path: Path):
    """本地模式（未配置中心）：默认启用，本地覆盖可禁用。"""
    _write_ext(tmp_path)
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])
    client = TestClient(app)

    resp = client.get("/api/extensions/demo_ext/ping")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    runtime.set_override("demo_ext", "disabled")
    assert client.get("/api/extensions/demo_ext/ping").status_code == 403

    runtime.set_override("demo_ext", None)
    assert client.get("/api/extensions/demo_ext/ping").status_code == 200


def test_local_mode_default_enabled(tmp_path: Path):
    """本地模式（退役中心后唯一模式）：装了即启用；本地覆盖可禁用。"""
    _write_ext(tmp_path)
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])
    client = TestClient(app)

    assert client.get("/api/extensions/demo_ext/ping").status_code == 200
    runtime.set_override("demo_ext", "disabled")
    assert client.get("/api/extensions/demo_ext/ping").status_code == 403
    runtime.set_override("demo_ext", None)
    assert client.get("/api/extensions/demo_ext/ping").status_code == 200


def test_entitlement_expiry_disables(tmp_path: Path):
    """到期门控：未同步时本地放行；成功快照命中 active 放行，expired/未命中则停用。"""
    _write_ext(tmp_path)
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])
    client = TestClient(app)

    # 默认未启用门控：装了即用（失败开放）
    assert runtime.entitlement_state("demo_ext") == "local"
    assert client.get("/api/extensions/demo_ext/ping").status_code == 200

    # 成功同步且命中 active → 仍放行
    runtime.set_entitlement_snapshot(
        {"demo_ext": {"app_key": "demo_ext", "state": "active"}},
        "2026-01-01T00:00:00Z",
        enforced=True,
    )
    assert client.get("/api/extensions/demo_ext/ping").status_code == 200

    # 到期 → 自动停用
    runtime.set_entitlement_snapshot(
        {"demo_ext": {"app_key": "demo_ext", "state": "expired"}},
        "2026-01-02T00:00:00Z",
        enforced=True,
    )
    assert client.get("/api/extensions/demo_ext/ping").status_code == 403

    # 已装但不在授权快照（未命中） → 停用
    runtime.set_entitlement_snapshot({}, "2026-01-03T00:00:00Z", enforced=True)
    assert runtime.entitlement_state("demo_ext") == "none"
    assert client.get("/api/extensions/demo_ext/ping").status_code == 403

    # 解除门控（解绑） → 回到本地放行
    runtime.clear_entitlement_enforcement()
    assert client.get("/api/extensions/demo_ext/ping").status_code == 200


def test_migrations_idempotent(tmp_path: Path):
    """迁移：执行建表；指纹一致时跳过重复执行。"""
    sql = "CREATE TABLE IF NOT EXISTS ext_demo_ext (\n  id INTEGER PRIMARY KEY,\n  name VARCHAR(64) NOT NULL\n);\n"
    _write_ext(tmp_path, sql=sql)
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    with Session() as db:
        run_extension_migrations(tmp_path, db=db)
        run_extension_migrations(tmp_path, db=db)  # 第二遍：指纹一致，跳过
        rows = db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='ext_demo_ext'")
        ).fetchall()
        assert rows

    applied = runtime.store.load("migrations", {})
    assert "demo_ext" in applied


def test_plugin_js_and_status_api(tmp_path: Path):
    """宿主固定 API：状态列表（ok 包装）+ plugin.js 获取与门控。"""
    _write_ext(tmp_path)
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])

    from app.api.admin.extensions.router import router as ext_admin_router

    app.include_router(ext_admin_router, prefix="/api/admin/extensions")
    client = TestClient(app)

    resp = client.get("/api/admin/extensions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    items = body["data"]["items"]
    assert len(items) == 1
    assert items[0]["key"] == "demo_ext"
    assert items[0]["enabled"] is True
    assert items[0]["has_frontend"] is True

    resp = client.get("/api/admin/extensions/demo_ext/plugin.js")
    assert resp.status_code == 200
    assert "__registerExtension" in resp.text

    runtime.set_override("demo_ext", "disabled")
    assert client.get("/api/admin/extensions/demo_ext/plugin.js").status_code == 403


def test_entitlements_cache_roundtrip(tmp_path: Path):
    """本地状态缓存落盘后可从磁盘恢复（模拟重启）。"""
    _write_ext(tmp_path)
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])

    runtime.apply_entitlements(
        {"entitlements": [{"app_key": "demo_ext", "state": "active"}]}, "2026-01-01T00:00:00Z"
    )

    runtime.entitlements = {}
    runtime.synced_at = ""
    runtime.load_from_disk()
    assert runtime.entitlements["demo_ext"]["state"] == "active"
    assert runtime.synced_at == "2026-01-01T00:00:00Z"


def test_sample_extension_package(tmp_path: Path):
    """仓库样例（extensions_samples/quotation_demo）可扫描/挂载/门控。"""
    shutil.copytree(SAMPLE_DIR, tmp_path / "quotation_demo")
    app = FastAPI()
    mount_extensions(app, tmp_path, auth_dependencies=[])
    client = TestClient(app)

    assert "quotation_demo" in runtime.installed
    resp = client.get("/api/extensions/quotation_demo/ping")
    assert resp.status_code == 200
    assert resp.json()["data"]["ok"] is True

    item = runtime.status_list()[0]
    assert item["permissions"][0]["code"] == "ext.quotation.view"
    assert item["menus"][0]["path"] == "/ext/quotation-demo"


def _load_cli():
    """按文件路径加载扩展管理 CLI 模块。"""
    cli_path = Path(__file__).resolve().parents[1] / "scripts" / "extension.py"
    spec = importlib.util.spec_from_file_location("ext_cli_for_test", cli_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_install_list_disable_remove(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """CLI 闭环：install → list → disable → enable → remove。"""
    monkeypatch.setattr(settings, "EXTENSIONS_DIR", str(tmp_path))
    cli = _load_cli()

    # 打包 zip（manifest.json 位于包根）
    ext_dir = _write_ext(tmp_path / "src", key="cli_ext")
    zip_path = tmp_path / "cli_ext.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in sorted(ext_dir.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(ext_dir))

    assert cli.cmd_install(argparse.Namespace(zip=str(zip_path))) == 0
    assert (tmp_path / "cli_ext" / "manifest.json").is_file()

    assert cli.cmd_list(argparse.Namespace()) == 0
    assert "cli_ext" in capsys.readouterr().out

    assert cli.cmd_disable(argparse.Namespace(key="cli_ext")) == 0
    overrides = json.loads((tmp_path / ".state" / "overrides.json").read_text(encoding="utf-8"))
    assert overrides["cli_ext"] == "disabled"

    assert cli.cmd_enable(argparse.Namespace(key="cli_ext")) == 0
    overrides = json.loads((tmp_path / ".state" / "overrides.json").read_text(encoding="utf-8"))
    assert "cli_ext" not in overrides

    assert cli.cmd_remove(argparse.Namespace(key="cli_ext")) == 0
    assert not (tmp_path / "cli_ext").exists()
