# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展扫描、迁移执行与路由挂载。

- 扫描 ``extensions/`` 下的一级子目录（跳过 ``.state`` 等点目录）
- 执行扩展自带 ``migrations.sql``（要求幂等，如 CREATE TABLE IF NOT EXISTS）
- 将扩展 ``router.py`` 中的 ``router``（fastapi.APIRouter）挂载到 ``/api/extensions/{key}``
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal

from .manifest import ManifestError, load_manifest
from .state import StateStore, runtime

logger = logging.getLogger("uvicorn.error")


def scan_extensions(base_dir: Path) -> dict[str, dict]:
    """扫描已安装扩展（目录名 = key；非法 manifest 跳过并告警）。"""
    found: dict[str, dict] = {}
    if not base_dir.is_dir():
        return found
    for child in sorted(base_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            manifest = load_manifest(child)
        except ManifestError as e:
            logger.warning("[extension] 跳过 %s: %s", child.name, e)
            continue
        found[manifest.key] = {"manifest": manifest, "path": child}
    return found


def require_extension(key: str):
    """FastAPI 依赖工厂：扩展必须处于启用状态（本地禁用/授权无效 → 403）。"""

    def _dep() -> None:
        if not runtime.is_enabled(key):
            state = runtime.entitlement_state(key)
            raise HTTPException(status_code=403, detail=f"扩展 {key} 未启用（授权状态: {state}）")

    return _dep


def _load_module(file: Path, module_name: str):
    """按文件路径加载 Python 模块（不依赖 sys.path）。"""
    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extension_route_target(route, key: str) -> bool:
    """判断某条 app 路由是否属于指定扩展（前缀 /api/extensions/{key}）。"""
    prefix = f"/api/extensions/{key}"
    path = getattr(route, "path", "") or ""
    return path == prefix or path.startswith(prefix + "/")


def unmount_extension_router(app: FastAPI, key: str) -> int:
    """从活的 app 中移除某扩展已挂载的路由（更新/卸载时调用）。

    Starlette ``Router.app`` 每次请求实时遍历 ``self.routes`` 匹配，故原地
    修改该列表立即生效，无需重启。返回移除的路由数量。
    """
    routes = app.router.routes
    keep = [r for r in routes if not _extension_route_target(r, key)]
    removed = len(routes) - len(keep)
    if removed:
        routes[:] = keep
    return removed


def mount_extension_router(app: FastAPI, key: str, ext_path: Path, auth_dependencies=None) -> bool:
    """运行期热挂载单个扩展路由（先清除旧路由，支持更新/重装）。

    返回是否实际挂载（扩展无 router.py 时返回 False）。
    """
    if auth_dependencies is None:
        from app.core.deps import get_current_user

        auth_dependencies = [Depends(get_current_user)]
    ext_router = load_extension_router(ext_path, key)
    if ext_router is None:
        return False
    unmount_extension_router(app, key)
    app.include_router(
        ext_router,
        prefix=f"/api/extensions/{key}",
        tags=[f"ext-{key}"],
        dependencies=[*auth_dependencies, Depends(require_extension(key))],
    )
    logger.info("[extension] 运行期热挂载扩展路由: /api/extensions/%s", key)
    return True


def load_extension_router(ext_path: Path, key: str) -> APIRouter | None:
    """加载扩展的 router.py；无该文件返回 None。"""
    router_file = ext_path / "router.py"
    if not router_file.is_file():
        return None
    module = _load_module(router_file, f"cenkormes_ext_{key}")
    router = getattr(module, "router", None)
    if router is None:
        raise ImportError(f"扩展 {key} 的 router.py 未定义 router 对象")
    if not isinstance(router, APIRouter):
        raise ImportError(f"扩展 {key} 的 router 必须是 fastapi.APIRouter")
    return router


def mount_extensions(app: FastAPI, base_dir: Path, auth_dependencies=None) -> None:
    """扫描并挂载全部已安装扩展（模块导入期调用）。

    auth_dependencies: 挂到每个扩展路由上的附加依赖；
    默认 ``[Depends(get_current_user)]``，测试场景可传入空列表或替代实现。
    """
    if auth_dependencies is None:
        from app.core.deps import get_current_user

        auth_dependencies = [Depends(get_current_user)]

    runtime.extensions_dir = base_dir
    runtime.store = StateStore(base_dir / ".state")
    runtime.load_from_disk()
    runtime.installed = scan_extensions(base_dir)

    for key, info in runtime.installed.items():
        try:
            ext_router = load_extension_router(info["path"], key)
        except Exception as e:  # noqa: BLE001 - 单个扩展加载失败不影响其他扩展
            logger.error("[extension] 加载 %s 路由失败: %s", key, e)
            continue
        if ext_router is None:
            continue
        app.include_router(
            ext_router,
            prefix=f"/api/extensions/{key}",
            tags=[f"ext-{key}"],
            dependencies=[*auth_dependencies, Depends(require_extension(key))],
        )
        logger.info("[extension] 已挂载扩展路由: /api/extensions/%s", key)


def _split_sql(sql_text: str) -> list[str]:
    """按行尾分号拆分 SQL 语句（忽略空行与 ``--`` 注释）。

    注意：仅支持简单语句，扩展迁移请避免使用含分号字符串/存储过程。
    """
    statements: list[str] = []
    buffer: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buffer).strip().rstrip(";").strip()
            if stmt:
                statements.append(stmt)
            buffer = []
    tail = "\n".join(buffer).strip().rstrip(";").strip()
    if tail:
        statements.append(tail)
    return statements


def run_extension_migrations(base_dir: Path, db: Session | None = None) -> None:
    """执行已启用扩展的 ``migrations.sql``（幂等；按文件指纹记录）。

    db: 传入则复用（测试用），否则自建 SessionLocal。
    """
    if runtime.store is None:
        runtime.store = StateStore(base_dir / ".state")
    applied: dict = runtime.store.load("migrations", {}) or {}

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        for key, info in runtime.installed.items():
            if not runtime.is_enabled(key):
                continue
            file = Path(info["path"]) / "migrations.sql"
            if not file.is_file():
                continue
            stat = file.stat()
            fingerprint = f"{int(stat.st_mtime)}:{stat.st_size}"
            if applied.get(key) == fingerprint:
                continue
            statements = _split_sql(file.read_text(encoding="utf-8"))
            for stmt in statements:
                db.execute(text(stmt))
            db.commit()
            applied[key] = fingerprint
            logger.info("[extension] %s 迁移已执行（%d 条语句）", key, len(statements))
        runtime.store.save("migrations", applied)
    except Exception as e:  # noqa: BLE001 - 迁移失败记录日志，不阻塞启动
        db.rollback()
        logger.error("[extension] 执行扩展迁移失败: %s", e)
    finally:
        if own_session:
            db.close()
