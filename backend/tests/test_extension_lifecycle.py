# SPDX-License-Identifier: AGPL-3.0
"""扩展生命周期闭环：安装 → 更新 → 回滚 → 卸载(保留) → 重装 → 卸载(清除)。

全部跑在临时目录 + SQLite 上，绝不写生产 MySQL、不碰仓库里的 extensions/。
"""
from __future__ import annotations

import io
import json
import threading
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

import app.core.db as core_db
import app.extension_host.host as host_mod
import app.extension_host.lifecycle as lifecycle_mod
from app.extension_host import lifecycle
from app.extension_host.loader import scan_extensions
from app.extension_host.state import StateStore, runtime

pytestmark = pytest.mark.usefixtures("env")


# ── 隔离环境：临时扩展目录 + SQLite + 清空 runtime ─────────────────────────

@pytest.fixture
def env(tmp_path, monkeypatch):
    base = tmp_path / "extensions"
    base.mkdir()
    engine = create_engine(f"sqlite:///{tmp_path / 'life.db'}")
    Session = sessionmaker(bind=engine)

    from app.models.base import Base
    from app.models.permission import Permission
    from app.models.role import Role, role_permissions
    from app.models.user import User, user_roles

    Base.metadata.create_all(
        engine,
        tables=[Permission.__table__, Role.__table__, role_permissions, User.__table__, user_roles],
    )
    # 核心业务表：用于验证「彻底清除不碰核心表」
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS stocks (id INTEGER PRIMARY KEY, qty INT)"))

    monkeypatch.setattr(core_db, "SessionLocal", Session)
    # 扩展路由默认挂 get_current_user：测试里换成无参桩，免签 token
    import app.core.deps as deps_mod
    from types import SimpleNamespace

    monkeypatch.setattr(deps_mod, "get_current_user", lambda: SimpleNamespace(id=1, username="tester"))
    monkeypatch.setattr(host_mod, "SessionLocal", Session)
    monkeypatch.setattr(lifecycle_mod, "DRAIN_SECONDS", 0)
    monkeypatch.setattr(lifecycle_mod, "read_core_version", lambda: "2.1.0")

    runtime.reset()
    runtime.extensions_dir = base
    runtime.store = StateStore(base / ".state")
    runtime.app_version = "2.1.0"

    state = {"base": base, "Session": Session, "engine": engine}
    yield state
    runtime.reset()
    engine.dispose()


def _manifest(key: str, version: str, **extra) -> dict:
    data = {
        "key": key,
        "name": f"{key} 应用",
        "version": version,
        "manifest_version": 2,
        "schema_version": 1,
        "product": "cenkormes",
        "min_core_version": "2.0.0",
        "permissions": [{"code": f"ext.{key}.view", "name": "查看"}],
        "menus": [{"title": "页面", "path": f"/ext/{key}"}],
        "data": {"retention": "keep", "tables": [{"name": f"ext_{key}_items", "mode": "own"}]},
    }
    data.update(extra)
    return data


def _pkg(
    key: str,
    version: str,
    *,
    router_body: str | None = None,
    sql: str | None = None,
    migrations: dict[str, str] | None = None,
    **manifest_extra,
) -> bytes:
    manifest = _manifest(key, version, **manifest_extra)
    router_body = router_body if router_body is not None else (
        "from fastapi import APIRouter\n\n"
        "router = APIRouter()\n\n\n"
        "@router.get('/ping')\n"
        "def ping():\n"
        f"    return {{'ok': True, 'version': '{version}'}}\n"
    )
    sql = sql if sql is not None else (
        f"CREATE TABLE IF NOT EXISTS ext_{key}_items (\n"
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "  name VARCHAR(64) NOT NULL\n"
        ");\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr("router.py", router_body)
        if sql:
            zf.writestr("migrations.sql", sql)
        for name, body in (migrations or {}).items():
            zf.writestr(f"migrations/{name}", body)
    return buf.getvalue()


def _fresh_app() -> FastAPI:
    return FastAPI()


def _client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _install(app, pkg: bytes, key: str, **kwargs) -> dict:
    return lifecycle.install_or_update(app, pkg, key, **kwargs)


def _table_exists(env, table: str) -> bool:
    return table in inspect(env["engine"]).get_table_names()


# ── 1. 非法包：不落盘 ───────────────────────────────────────────────────────

def test_invalid_key_and_zip_member_rejected(env):
    bad_key = _pkg("Demo-App", "1.0.0")
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.preflight(bad_key, "Demo-App")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(_manifest("demo", "1.0.0")))
        zf.writestr("../evil.py", "print(1)")
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.preflight(buf.getvalue(), "demo")

    assert not (env["base"] / "demo").exists()


def test_missing_root_manifest_rejected(env):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("demo/manifest.json", json.dumps(_manifest("demo", "1.0.0")))
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.preflight(buf.getvalue(), "demo")


def test_permission_namespace_enforced_for_v2(env):
    pkg = _pkg("demo", "1.0.0", permissions=[{"code": "stock.view", "name": "错命名空间"}])
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.preflight(pkg, "demo")
    # v1 老包保持宽松（存量 8 个扩展权限前缀不合规）
    legacy = _pkg("legacy_app", "1.0.0")
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(legacy)).read("manifest.json"))
    manifest.pop("manifest_version")
    manifest.pop("schema_version", None)
    manifest["permissions"] = [{"code": "legacy.view", "name": "老前缀"}]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
    pre = lifecycle.preflight(buf.getvalue(), "legacy_app")
    assert pre.manifest.manifest_version == 1


def test_missing_dependency_and_core_version(env):
    dep_pkg = _pkg("demo", "1.0.0", dependencies=[{"key": "not_installed"}])
    with pytest.raises(lifecycle.LifecycleError) as exc:
        lifecycle.preflight(dep_pkg, "demo")
    assert exc.value.status_code == 409

    too_new = _pkg("demo", "1.0.0", min_core_version="9.9.9")
    with pytest.raises(lifecycle.LifecycleError) as exc:
        lifecycle.preflight(too_new, "demo")
    assert exc.value.status_code == 409


# ── 2. 安装成功：目录/路由/权限/表/健康全绿 ────────────────────────────────

def test_install_success_full_green(env):
    app = _fresh_app()
    result = _install(app, _pkg("demo", "1.0.0"), "demo")
    assert result["action"] == "install"
    assert result["health"]["ok"] is True, result["health"]
    assert (env["base"] / "demo" / "manifest.json").is_file()
    assert (env["base"] / ".staging").is_dir()
    assert _table_exists(env, "ext_demo_items")
    assert _client(app).get("/api/extensions/demo/ping").status_code == 200

    with env["Session"]() as db:
        codes = {r[0] for r in db.execute(text("SELECT code FROM permissions"))}
    assert "ext.demo.view" in codes
    record = json.loads((env["base"] / ".state" / "registry.json").read_text())
    assert record["demo"]["version"] == "1.0.0"
    assert record["demo"]["status"] == "installed_enabled"
    # 审计落盘
    audit = (env["base"] / ".state" / "lifecycle.jsonl").read_text().strip().splitlines()
    assert json.loads(audit[-1])["operation"] == "install"


def test_public_router_bypasses_login(env):
    router_body = (
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "public_router = APIRouter()\n\n"
        "@router.get('/private')\n"
        "def private():\n    return {'ok': True}\n\n"
        "@public_router.get('/public')\n"
        "def public():\n    return {'ok': True}\n"
    )
    app = _fresh_app()
    _install(app, _pkg("demo", "1.0.0", router_body=router_body), "demo")
    client = _client(app)
    assert client.get("/api/extensions/demo/public").status_code == 200


def test_package_style_relative_import(env):
    """qcode 类包式扩展：router.py 里 from . import crud 必须可用。"""
    buf = io.BytesIO()
    manifest = _manifest("pkg_ext", "1.0.0")
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("crud.py", "def hello():\n    return 'hi'\n")
        zf.writestr(
            "router.py",
            "from fastapi import APIRouter\n"
            "from . import crud\n\n"
            "router = APIRouter()\n\n"
            "@router.get('/hello')\n"
            "def hello():\n    return {'msg': crud.hello()}\n",
        )
        zf.writestr("migrations.sql", "CREATE TABLE IF NOT EXISTS ext_pkg_ext_items (id INTEGER PRIMARY KEY);\n")
    app = _fresh_app()
    _install(app, buf.getvalue(), "pkg_ext")
    assert _client(app).get("/api/extensions/pkg_ext/hello").json()["msg"] == "hi"


# ── 3. 更新成功 / 失败回滚 ─────────────────────────────────────────────────

def _add_column_migration(table: str) -> str:
    return (
        "def apply(db, ctx):\n"
        f"    ctx.add_column_if_missing('{table}', 'note', 'VARCHAR(128) NULL')\n"
    )


def test_update_keeps_data_and_creates_backup(env):
    app = _fresh_app()
    _install(app, _pkg("demo", "1.0.0"), "demo")
    with env["Session"]() as db:
        db.execute(text("INSERT INTO ext_demo_items (name) VALUES ('旧数据')"))
        db.commit()

    result = _install(
        app,
        _pkg("demo", "1.1.0", migrations={"0002_add_note.py": _add_column_migration("ext_demo_items")}),
        "demo",
    )
    assert result["action"] == "update"
    assert result["from_version"] == "1.0.0"
    assert Path(result["backup"]).is_dir(), "更新必须留一份旧版备份"
    with env["Session"]() as db:
        rows = db.execute(text("SELECT name, note FROM ext_demo_items")).fetchall()
    assert rows and rows[0][0] == "旧数据"
    assert _client(app).get("/api/extensions/demo/ping").json()["version"] == "1.1.0"


def test_update_failure_rolls_back_to_previous(env):
    app = _fresh_app()
    _install(app, _pkg("demo", "1.0.0"), "demo")
    broken = "def apply(db, ctx):\n    raise RuntimeError('迁移炸了')\n"
    with pytest.raises(lifecycle.LifecycleError):
        _install(app, _pkg("demo", "2.0.0", migrations={"0002_broken.py": broken}), "demo")
    live_manifest = json.loads((env["base"] / "demo" / "manifest.json").read_text())
    assert live_manifest["version"] == "1.0.0", "迁移失败不得换入新版本"
    assert _client(app).get("/api/extensions/demo/ping").json()["version"] == "1.0.0"


def test_same_version_same_sha_is_idempotent_rejected(env):
    app = _fresh_app()
    pkg = _pkg("demo", "1.0.0")
    _install(app, pkg, "demo")
    with pytest.raises(lifecycle.LifecycleError) as exc:
        _install(app, pkg, "demo")
    assert exc.value.status_code == 409


def test_downgrade_requires_flag(env):
    app = _fresh_app()
    _install(app, _pkg("demo", "2.0.0"), "demo")
    with pytest.raises(lifecycle.LifecycleError) as exc:
        _install(app, _pkg("demo", "1.0.0"), "demo")
    assert exc.value.status_code == 409
    result = _install(app, _pkg("demo", "1.0.0"), "demo", allow_downgrade=True)
    assert result["to_version"] == "1.0.0"


# ── 4. 卸载保留 / 重装恢复 / 彻底清除 ──────────────────────────────────────

def test_uninstall_keep_then_reinstall_restores_data(env):
    app = _fresh_app()
    _install(app, _pkg("demo", "1.0.0"), "demo")
    with env["Session"]() as db:
        db.execute(text("INSERT INTO ext_demo_items (name) VALUES ('保留我')"))
        db.commit()

    result = lifecycle.uninstall(app, "demo")
    assert result["policy"] == "keep"
    assert _client(app).get("/api/extensions/demo/ping").status_code == 404
    assert not (env["base"] / "demo").exists()
    assert Path(result["trash"]).is_dir()
    assert _table_exists(env, "ext_demo_items"), "keep 策略必须保留数据表"
    with env["Session"]() as db:
        assert db.execute(text("SELECT COUNT(*) FROM permissions WHERE code='ext.demo.view'")).scalar() == 0
    record = json.loads((env["base"] / ".state" / "registry.json").read_text())
    assert record["demo"]["status"] == "uninstalled_keep"

    _install(app, _pkg("demo", "1.0.0"), "demo")
    with env["Session"]() as db:
        assert db.execute(text("SELECT name FROM ext_demo_items")).scalar() == "保留我"
    assert _client(app).get("/api/extensions/demo/ping").status_code == 200


def test_uninstall_purge_drops_own_tables_but_not_core(env):
    app = _fresh_app()
    _install(app, _pkg("demo", "1.0.0"), "demo")
    with env["Session"]() as db:
        db.execute(text("INSERT INTO ext_demo_items (name) VALUES ('要清掉')"))
        db.commit()

    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.uninstall(app, "demo", purge=True, confirm_key="wrong")

    result = lifecycle.uninstall(app, "demo", purge=True, confirm_key="demo")
    assert result["policy"] == "purge"
    assert result["data"]["tables"] == ["ext_demo_items"]
    assert not _table_exists(env, "ext_demo_items")
    assert _table_exists(env, "stocks"), "核心表绝不允许被扩展清除"
    export_dir = Path(result["data"]["export_dir"])
    assert (export_dir / "ext_demo_items.jsonl").is_file()
    assert "要清掉" in (export_dir / "ext_demo_items.jsonl").read_text()
    record = json.loads((env["base"] / ".state" / "registry.json").read_text())
    assert "demo" not in record


# ── 5. 依赖 / 并发 / 修复 ──────────────────────────────────────────────────

def test_dependency_blocks_uninstall(env):
    app = _fresh_app()
    _install(app, _pkg("base_app", "1.0.0"), "base_app")
    _install(app, _pkg("child_app", "1.0.0", dependencies=[{"key": "base_app"}]), "child_app")
    with pytest.raises(lifecycle.LifecycleError) as exc:
        lifecycle.uninstall(app, "base_app")
    assert exc.value.status_code == 409
    assert "child_app" in str(exc.value)


def test_concurrent_lifecycle_lock(env):
    acquired = threading.Event()
    release = threading.Event()

    def holder():
        with lifecycle.lifecycle_lock("demo"):
            acquired.set()
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    assert acquired.wait(5)
    try:
        with pytest.raises(lifecycle.LifecycleError) as exc:
            with lifecycle.lifecycle_lock("demo", timeout=0.2):
                pass
        assert exc.value.status_code == 409
    finally:
        release.set()
        thread.join(5)


def test_missing_dir_repair_restores_backup(env):
    app = _fresh_app()
    _install(app, _pkg("demo", "1.0.0"), "demo")
    _install(app, _pkg("demo", "1.1.0"), "demo")  # 产生 1.0.0 备份
    # 模拟被外部删除
    import shutil

    shutil.rmtree(env["base"] / "demo")
    runtime.installed = scan_extensions(env["base"])
    assert "demo" not in runtime.installed

    result = lifecycle.repair(app, "demo")
    assert result["ok"] is True
    assert (env["base"] / "demo" / "manifest.json").is_file()
    assert _client(app).get("/api/extensions/demo/ping").status_code == 200
    assert json.loads((env["base"] / "demo" / "manifest.json").read_text())["version"] == "1.0.0"


def test_enable_disable_soft_plug(env):
    app = _fresh_app()
    _install(app, _pkg("demo", "1.0.0"), "demo")
    lifecycle.set_enabled(app, "demo", False)
    assert _client(app).get("/api/extensions/demo/ping").status_code == 404
    assert (env["base"] / "demo").is_dir(), "禁用保留文件与数据"
    lifecycle.set_enabled(app, "demo", True)
    assert _client(app).get("/api/extensions/demo/ping").status_code == 200


# ── 18. 热更新二次 import：表必须从共享 metadata 摘掉 ────────────────────────

_RELOAD_ROUTER = (
    "from fastapi import APIRouter\n"
    "from sqlalchemy import Integer, String\n"
    "from sqlalchemy.orm import Mapped, mapped_column\n"
    "\n"
    "from app.models.base import Base\n"
    "\n"
    "\n"
    "class ReloadItem(Base):\n"
    "    __tablename__ = 'ext_reload_items'\n"
    "    id: Mapped[int] = mapped_column(Integer, primary_key=True)\n"
    "    name: Mapped[str] = mapped_column(String(32), nullable=False)\n"
    "\n"
    "\n"
    "router = APIRouter()\n"
    "\n"
    "\n"
    "@router.get('/ping')\n"
    "def ping():\n"
    "    return {'ok': True}\n"
)

_RELOAD_SQL = (
    "CREATE TABLE IF NOT EXISTS ext_reload_items (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  name VARCHAR(32) NOT NULL\n"
    ");\n"
)


def test_reload_reimports_models_after_metadata_detach(env):
    """卸载→重装（同一进程）必须能重新 import 带 ORM 模型的扩展。

    扩展与核心共用 ``app.models.base.Base``：只清 ``sys.modules`` 时，第二次 import
    同一个模块会在声明类时报 ``Table 'ext_reload_items' is already defined``，热更新
    必然失败。``purge_extension_modules`` 现在会把该扩展的表从 metadata 摘掉。
    """
    data = {"retention": "keep", "tables": [{"name": "ext_reload_items", "mode": "own"}]}
    app = _fresh_app()

    first = _pkg("reload_ext", "1.0.0", router_body=_RELOAD_ROUTER, sql=_RELOAD_SQL, data=data)
    assert _install(app, first, "reload_ext")["ok"] is True

    lifecycle.uninstall(app, "reload_ext")
    # 卸载后该表应从共享 metadata 消失（数据表本身仍保留在库里）
    from app.models.base import Base
    assert "ext_reload_items" not in Base.metadata.tables

    second = _pkg("reload_ext", "1.1.0", router_body=_RELOAD_ROUTER, sql=_RELOAD_SQL, data=data)
    result = _install(app, second, "reload_ext")
    assert result["ok"] is True and result["to_version"] == "1.1.0"
    # 重装后表重新登记，且数据表没被 DROP（keep 策略）
    assert "ext_reload_items" in Base.metadata.tables
    assert _table_exists(env, "ext_reload_items")
