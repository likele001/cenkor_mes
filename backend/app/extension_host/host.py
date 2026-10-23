# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主 facade：供 ``app/main.py``、市场 API 与 CLI 调用的统一入口。

热插拔的三个动作都在这里：

- :func:`hot_setup_extension`   迁移 + 权限 + 挂载 + 任务 + 健康检查（安装/更新/启用/修复）
- :func:`hot_teardown_extension` 摘路由 + 反注册事件/任务/模块（卸载/禁用/更新前）
- :func:`cleanup_permissions`   删除 ``ext.<key>.*`` 权限点与角色绑定（卸载）
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal

from .loader import mount_extensions, mount_extension_router, run_extension_migrations, unmount_extension_router
from .registry import audit, write_health
from .state import runtime

logger = logging.getLogger("uvicorn.error")


def extensions_base_dir() -> Path:
    """解析扩展目录（相对路径按 backend/ 解析）。"""
    raw = (settings.EXTENSIONS_DIR or "./extensions").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / raw
    return path.resolve()


def mount_all(app) -> None:
    """模块导入期调用：扫描扩展并挂载路由（总开关关闭时跳过）。"""
    if not settings.EXTENSIONS_ENABLED:
        logger.info("[extension] 扩展宿主已关闭（EXTENSIONS_ENABLED=0）")
        return
    base = extensions_base_dir()
    base.mkdir(parents=True, exist_ok=True)
    mount_extensions(app, base)
    if runtime.installed:
        logger.info("[extension] 已发现 %d 个扩展: %s", len(runtime.installed), ", ".join(sorted(runtime.installed)))


def startup_host() -> None:
    """on_startup 调用：版本号 + 迁移 + 权限注入 + 启动授权到期门控线程（失败开放）。"""
    if not settings.EXTENSIONS_ENABLED:
        return
    from .version import read_core_version

    runtime.app_version = read_core_version()
    run_extension_migrations(extensions_base_dir())
    sync_permissions()
    # 延迟导入避免循环依赖；线程在 web 进程内定期把 hub 已购快照刷进 runtime，
    # 由每请求 require_extension 门控实现“到期/吊销自动停用”。
    try:
        from app.api.admin.market.router import start_entitlement_thread

        start_entitlement_thread()
    except Exception as e:  # noqa: BLE001 - 门控线程启动失败不阻塞启动（失败开放）
        logger.warning("[extension] 授权门控线程启动失败: %s", e)


# ── 权限 ────────────────────────────────────────────────────────────────────

def _manifest_permissions(key: str) -> dict[str, str]:
    info = runtime.installed.get(key) or {}
    manifest = info.get("manifest")
    if manifest is None:
        return {}
    return {
        str(p.get("code")).strip(): str(p.get("name") or p.get("code"))
        for p in manifest.permissions
        if p.get("code")
    }


def sync_permissions(only_key: str | None = None, *, force: bool = False, prune: bool = False) -> dict:
    """把扩展声明的权限点写入 DB，并补授 admin 角色。

    only_key: 只同步该扩展（安装/更新/修复），配合 force 跳过 ``is_enabled`` 门禁。
    prune: 删除该扩展已不再声明的 ``ext.<key>.*`` 权限点（更新降级时清残留）。
    """
    from app.models.permission import Permission
    from app.models.role import Role, role_permissions

    wanted: dict[str, str] = {}
    for key in runtime.installed:
        if only_key and key != only_key:
            continue
        if not (force and key == only_key) and not runtime.is_enabled(key):
            continue
        wanted.update(_manifest_permissions(key))

    db: Session = SessionLocal()
    created: list[str] = []
    granted: list[str] = []
    removed: list[str] = []
    try:
        existing = {p.code: p for p in db.scalars(select(Permission)).all()}
        for code, name in wanted.items():
            if code not in existing:
                perm = Permission(code=code, name=name)
                db.add(perm)
                existing[code] = perm
                created.append(code)
        db.flush()
        admin = db.scalar(select(Role).where(Role.code == "admin"))
        if admin:
            admin_codes = {p.code for p in (admin.permissions or [])}
            missing = [existing[c] for c in wanted if c not in admin_codes]
            if missing:
                admin.permissions.extend(missing)
                granted = [p.code for p in missing]
        if prune and only_key:
            prefix = f"ext.{only_key}."
            stale = [p for code, p in existing.items() if code.startswith(prefix) and code not in wanted]
            for perm in stale:
                db.execute(delete(role_permissions).where(role_permissions.c.permission_id == perm.id))
                db.delete(perm)
                removed.append(perm.code)
        db.commit()
        if created:
            logger.info("[extension] 注入扩展权限点 %d 个: %s", len(created), ", ".join(created))
        if removed:
            logger.info("[extension] 清理过期扩展权限点 %d 个: %s", len(removed), ", ".join(removed))
    except Exception as e:  # noqa: BLE001 - 权限注入失败不阻塞启动
        db.rollback()
        logger.error("[extension] 同步扩展权限失败: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        db.close()
    return {"ok": True, "created": created, "granted": granted, "removed": removed}


def cleanup_permissions(key: str, extra_codes: list[str] | None = None) -> dict:
    """卸载：删除 ``ext.<key>.*`` 权限点与角色绑定（不碰其他前缀）。

    extra_codes: manifest 里声明的历史权限码（v1 兼容，可能不在 ``ext.<key>.`` 下）。
    """
    from app.models.permission import Permission
    from app.models.role import role_permissions

    prefix = f"ext.{key}."
    wanted = set(extra_codes or []) | {c for c in _manifest_permissions(key)}
    db: Session = SessionLocal()
    try:
        targets = [
            p for p in db.scalars(select(Permission)).all()
            if p.code.startswith(prefix) or p.code in wanted
        ]
        if not targets:
            return {"ok": True, "removed": []}
        ids = [p.id for p in targets]
        db.execute(delete(role_permissions).where(role_permissions.c.permission_id.in_(ids)))
        for perm in targets:
            db.delete(perm)
        db.commit()
        removed = [p.code for p in targets]
        logger.info("[extension] 卸载清理权限点 %d 个: %s", len(removed), ", ".join(removed))
        return {"ok": True, "removed": removed}
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error("[extension] 清理扩展权限失败 %s: %s", key, e)
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


# ── 任务（Celery worker / beat）─────────────────────────────────────────────

def register_tasks(key: str, manifest=None) -> dict:
    """按 manifest.tasks 把任务登记到当前进程的 Celery（web 进程内即时生效）。"""
    manifest = manifest or (runtime.installed.get(key) or {}).get("manifest")
    if manifest is None:
        return {"ok": True, "celery": [], "beat": []}
    tasks = getattr(manifest, "tasks", {}) or {}
    celery_names = [str(t) for t in (tasks.get("celery") or [])]
    beat_names = [str(t) for t in (tasks.get("beat") or [])]
    if not celery_names and not beat_names:
        return {"ok": True, "celery": [], "beat": []}
    try:
        from app.celery_app import celery
    except Exception as e:  # noqa: BLE001 - 无 celery 环境（测试/裁剪部署）
        logger.warning("[extension] Celery 不可用，任务注册跳过: %s", e)
        return {"ok": False, "error": str(e), "celery": celery_names, "beat": beat_names}
    registered = [name for name in celery_names if name in celery.tasks]
    schedule = getattr(celery.conf, "beat_schedule", None) or {}
    return {
        "ok": True,
        "celery": registered,
        "missing": [n for n in celery_names if n not in registered],
        "beat": [n for n in beat_names if n in schedule],
    }


def unregister_tasks(key: str, manifest=None) -> dict:
    """从当前进程的 Celery 注册表与 beat_schedule 摘掉该扩展的任务。"""
    manifest = manifest or (runtime.installed.get(key) or {}).get("manifest")
    tasks = getattr(manifest, "tasks", {}) if manifest is not None else {}
    tasks = tasks or {}
    celery_names = [str(t) for t in (tasks.get("celery") or [])]
    beat_names = set(str(t) for t in (tasks.get("beat") or []))
    removed: list[str] = []
    beat_removed: list[str] = []
    try:
        from app.celery_app import celery
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "worker_restart_required": bool(celery_names or beat_names)}
    for name in celery_names:
        if celery.tasks.pop(name, None) is not None:
            removed.append(name)
    schedule = getattr(celery.conf, "beat_schedule", None) or {}
    for name, entry in list(schedule.items()):
        task = str((entry or {}).get("task") or "")
        if name in beat_names or task in celery_names or name.startswith(f"ext.{key}."):
            schedule.pop(name, None)
            beat_removed.append(name)
    return {"ok": True, "celery": removed, "beat": beat_removed, "worker_restart_required": bool(removed or beat_removed)}


# ── 健康检查 ────────────────────────────────────────────────────────────────

def check_health(key: str, route_count: int | None = None) -> dict:
    """检查扩展可用性：模块/路由/表/迁移记录/前端/权限点。"""
    import sys

    from .loader import extension_module_name
    from .migrations import _python_migrations
    from .state import StateStore

    info = runtime.installed.get(key)
    errors: list[str] = []
    if not info:
        errors.append("扩展未安装")
    else:
        manifest = info["manifest"]
        path = Path(info["path"])
        module = sys.modules.get(extension_module_name(key))
        if module is None:
            errors.append("扩展模块未加载")
        if route_count is None:
            route_count = int((runtime.interfaces.get(key) or {}).get("route_count", 0))
        if route_count <= 0:
            errors.append("未挂载任何路由")
        store: StateStore | None = runtime.store
        if store is not None:
            records = (store.load("schema", {}) or {}).get(key) or []
            done = {str(r.get("filename")) for r in records}
            try:
                pending = [p.name for p in _python_migrations(path) if p.name not in done]
            except Exception as e:  # noqa: BLE001
                pending = []
                errors.append(f"迁移目录不合法: {e}")
            if pending:
                errors.append(f"存在未执行迁移: {', '.join(pending)}")
        tables = [str(t.get("name")) for t in ((manifest.data or {}).get("tables") or []) if t.get("name")]
        if tables:
            db: Session = SessionLocal()
            try:
                for table in tables:
                    try:
                        db.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                    except Exception:  # noqa: BLE001 - 表不存在/无权限都算不健康
                        errors.append(f"声明的表不存在: {table}")
                        db.rollback()
            finally:
                db.close()
        if (path / "frontend" / "plugin.js").is_file() or (path / "frontend").is_dir():
            if not (path / "frontend" / "plugin.js").is_file():
                errors.append("前端目录存在但缺少 plugin.js")
        if manifest.permissions:
            from app.models.permission import Permission

            db = SessionLocal()
            try:
                codes = {p.code for p in db.scalars(select(Permission)).all()}
                missing = [p.get("code") for p in manifest.permissions if p.get("code") not in codes]
                if missing:
                    errors.append(f"权限点未落库: {', '.join(str(m) for m in missing)}")
            finally:
                db.close()
        hook = getattr(module, "healthcheck", None) if module else None
        if callable(hook):
            try:
                hook_errors = hook()
                if isinstance(hook_errors, str):
                    hook_errors = [hook_errors]
                errors.extend(str(e) for e in (hook_errors or []))
            except Exception as e:  # noqa: BLE001 - 扩展自带检查失败只记错误
                errors.append(f"扩展 healthcheck 失败: {e}")
    record = write_health(key, not errors, errors, route_count=route_count or 0)
    return record


# ── 热插拔 ──────────────────────────────────────────────────────────────────

def hot_setup_extension(app, key: str, *, force: bool = True, migrate: bool = True) -> dict:
    """安装/更新/启用/修复后运行期即时生效。

    顺序：迁移 → 权限 → 挂载路由 → 注册任务 → 健康检查。
    迁移失败直接返回，不挂载新版本（旧版仍由调用方负责回滚）。
    """
    info = runtime.installed.get(key)
    if not info:
        return {"ok": False, "error": f"扩展 {key} 未安装"}
    result: dict = {"ok": True, "key": key, "migrations": {}, "permissions": {}, "tasks": {}, "routes": 0}
    if migrate:
        outcomes = run_extension_migrations(extensions_base_dir(), only_key=key, force=force)
        result["migrations"] = outcomes.get(key, {})
        if not result["migrations"].get("ok", False):
            result["ok"] = False
            result["error"] = f"迁移失败: {result['migrations'].get('error', '')}"
            return result
    result["permissions"] = sync_permissions(only_key=key, force=force, prune=True)
    try:
        result["routes"] = mount_extension_router(app, key, Path(info["path"]))
    except Exception as e:  # noqa: BLE001 - 热挂载失败仍可重启生效，但要留痕
        logger.error("[extension] 运行期热挂载 %s 失败: %s", key, e)
        result["ok"] = False
        result["error"] = f"热挂载失败: {e}"
        write_health(key, False, [result["error"]])
        return result
    result["tasks"] = register_tasks(key, info["manifest"])
    result["health"] = check_health(key, result["routes"])
    result["ok"] = bool(result["health"].get("ok"))
    audit(
        "setup", key,
        version=getattr(info["manifest"], "version", ""),
        routes=result["routes"],
        permissions=result["permissions"].get("created", []),
        health="ok" if result["ok"] else "error",
    )
    return result


def hot_teardown_extension(
    app,
    key: str,
    *,
    purge_permissions: bool = False,
    purge_modules: bool = True,
    clear_override: bool = True,
) -> dict:
    """卸载/禁用/更新前：摘路由 + 反注册事件 + 清模块 + 清缓存。

    purge_permissions=True 时同时删除 ``ext.<key>.*`` 权限点（卸载/彻底清除）。
    默认不清 overrides（禁用要留下 disabled 标记），卸载由调用方决定。
    """
    from .events import event_bus
    from .loader import purge_extension_modules

    runtime.retiring.add(key)
    try:
        removed_routes = unmount_extension_router(app, key)
        hooks = event_bus.unsubscribe_extension(key)
        # ABAC 类扩展的授权提供者也必须随禁用/卸载一起摘掉，否则陈旧策略继续生效
        from app.core.authorization import unregister_all
        unregister_all(key)
        tasks = unregister_tasks(key)
        modules = purge_extension_modules(key) if purge_modules else 0
        runtime.interfaces.pop(key, None)
        if clear_override:
            runtime.set_override(key, None)
        permissions = cleanup_permissions(key) if purge_permissions else {"ok": True, "removed": []}
    finally:
        runtime.retiring.discard(key)
    if removed_routes:
        logger.info("[extension] 运行期移除扩展路由 %d 条: %s", removed_routes, key)
    if hooks:
        logger.info("[extension] 运行期反注册事件钩子 %d 个: %s", hooks, key)
    return {
        "ok": True,
        "routes": removed_routes,
        "hooks": hooks,
        "modules": modules,
        "tasks": tasks,
        "permissions": permissions,
    }


def set_extension_enabled(app, key: str, enabled: bool) -> dict:
    """软插/软拔：启用 = 清 override + 挂载；禁用 = 停门禁 + 摘路由，保留文件与数据。"""
    info = runtime.installed.get(key)
    if not info:
        return {"ok": False, "error": f"扩展 {key} 未安装"}
    if enabled:
        runtime.set_override(key, None)
        return hot_setup_extension(app, key, force=True, migrate=True)
    runtime.set_override(key, "disabled")
    result = hot_teardown_extension(app, key, clear_override=False)
    result["enabled"] = False
    return result


# 兼容旧名（CLI / 历史调用）
def _sync_permissions() -> None:
    sync_permissions()
