# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主 facade：供 ``app/main.py`` 与 CLI 调用的统一入口。"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal

from .loader import mount_extensions, run_extension_migrations
from .state import runtime

logger = logging.getLogger("uvicorn.error")


def hot_setup_extension(app, key: str) -> None:
    """安装/更新后运行期即时生效：执行迁移 + 注入权限 + 热挂载路由（无需重启）。

    app 为活的 FastAPI 实例（取自请求上下文 ``request.app``）。
    """
    from .loader import mount_extension_router

    info = runtime.installed.get(key)
    if not info:
        return
    # 幂等迁移（含新扩展的 migrations.sql）
    run_extension_migrations(extensions_base_dir())
    # 注入扩展声明的权限点
    _sync_permissions()
    # 热挂载扩展路由
    try:
        mount_extension_router(app, key, Path(info["path"]))
    except Exception as e:  # noqa: BLE001 - 热挂载失败不阻塞安装结果（重启仍可生效）
        logger.error("[extension] 运行期热挂载 %s 失败: %s", key, e)


def hot_teardown_extension(app, key: str) -> None:
    """卸载后运行期即时移除路由（无需重启）。"""
    from .loader import unmount_extension_router

    removed = unmount_extension_router(app, key)
    if removed:
        logger.info("[extension] 运行期移除扩展路由 %d 条: %s", removed, key)


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
    """on_startup 调用：迁移 + 权限注入 + 启动授权到期门控线程（失败开放）。"""
    if not settings.EXTENSIONS_ENABLED:
        return
    run_extension_migrations(extensions_base_dir())
    _sync_permissions()
    # 延迟导入避免循环依赖；线程在 web 进程内定期把 hub 已购快照刷进 runtime，
    # 由每请求 require_extension 门控实现“到期/吊销自动停用”。
    try:
        from app.api.admin.market.router import start_entitlement_thread

        start_entitlement_thread()
    except Exception as e:  # noqa: BLE001 - 门控线程启动失败不阻塞启动（失败开放）
        logger.warning("[extension] 授权门控线程启动失败: %s", e)


def _sync_permissions() -> None:
    """把已启用扩展声明的权限点写入 DB，并补授 admin 角色。"""
    from app.models.permission import Permission
    from app.models.role import Role

    wanted: dict[str, str] = {}
    for key, info in runtime.installed.items():
        if not runtime.is_enabled(key):
            continue
        for p in info["manifest"].permissions:
            code = str(p.get("code") or "").strip()
            if code:
                wanted[code] = str(p.get("name") or code)
    if not wanted:
        return

    db: Session = SessionLocal()
    try:
        existing = {p.code: p for p in db.scalars(select(Permission)).all()}
        created: list[Permission] = []
        for code, name in wanted.items():
            if code not in existing:
                perm = Permission(code=code, name=name)
                db.add(perm)
                existing[code] = perm
                created.append(perm)
        db.flush()
        # 补授：把 admin 角色缺失的所有扩展权限点补齐（不仅新建，修复历史遗留）
        admin = db.scalar(select(Role).where(Role.code == "admin"))
        if admin:
            admin_codes = {p.code for p in (admin.permissions or [])}
            missing = [existing[c] for c in wanted if c not in admin_codes]
            if missing:
                admin.permissions.extend(missing)
                logger.info("[extension] 补授扩展权限点到 admin %d 个: %s", len(missing), ", ".join(p.code for p in missing))
        if created:
            logger.info("[extension] 注入扩展权限点 %d 个: %s", len(created), ", ".join(p.code for p in created))
        db.commit()
    except Exception as e:  # noqa: BLE001 - 权限注入失败不阻塞启动
        db.rollback()
        logger.error("[extension] 同步扩展权限失败: %s", e)
    finally:
        db.close()
