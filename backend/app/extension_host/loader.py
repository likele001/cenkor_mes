# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展扫描、迁移执行与路由挂载。

- 扫描 ``extensions/`` 下的一级子目录（跳过 ``.state`` 等点目录）
- 执行扩展自带 ``migrations.sql`` 与 ``migrations/*.py``（见 ``migrations.py``）
- 将扩展 ``router.py`` 中的 ``router`` / ``public_router`` 挂载到 ``/api/extensions/{key}``

包式扩展（目录内有 ``crud.py`` / ``models.py`` 等子模块，使用 ``from . import crud``
相对导入）必须把扩展目录登记为模块的 ``submodule_search_locations``，否则
``ModuleNotFoundError: No module named 'cenkormes_ext_xxx.crud'``。
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

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
    """FastAPI 依赖工厂：扩展必须处于启用状态（本地禁用/授权无效 → 403）。

    卸载流程会先把 key 放进 ``runtime.retiring``：排空窗口内新请求返回 503，
    避免请求打到已经摘掉一半路由/模块的扩展上。
    """

    def _dep() -> None:
        if key in runtime.retiring:
            raise HTTPException(status_code=503, detail=f"扩展 {key} 正在卸载，请稍后刷新")
        if not runtime.is_enabled(key):
            state = runtime.entitlement_state(key)
            raise HTTPException(status_code=403, detail=f"扩展 {key} 未启用（授权状态: {state}）")

    return _dep


def extension_module_name(key: str) -> str:
    return f"cenkormes_ext_{key}"


def _detach_extension_tables(module) -> int:
    """把扩展声明的表从共享 ``Base.metadata`` 摘掉。

    扩展与核心共用 ``app.models.base.Base``。只清 ``sys.modules`` 不够：第二次 import
    同一个 models 模块会在声明类时报 ``Table 'x' is already defined``，热更新/重装
    必踩。这里按「类/Table 对象的 __module__ 属于本扩展模块子树」精确识别，只摘
    自己的表，不碰核心与其他扩展。
    """
    from sqlalchemy import Table

    from app.models.base import Base

    meta = Base.metadata
    dropped = 0
    for obj in list(vars(module).values()):
        # celery.local.Proxy（@shared_task 装饰产物）在任务已被反注册后，
        # isinstance 会触发惰性解析并抛 NotRegistered；跳过即可，本函数只摘表。
        try:
            if isinstance(obj, type):
                table = getattr(obj, "__table__", None)
                owner = getattr(obj, "__module__", "") or ""
            elif isinstance(obj, Table):
                table = obj
                owner = module.__name__
            else:
                continue
        except Exception:  # noqa: BLE001 - 惰性代理解析失败不影响表清理
            continue
        if table is None or getattr(table, "metadata", None) is not meta:
            continue
        if owner != module.__name__ and not owner.startswith(module.__name__ + "."):
            continue
        if meta.tables.get(table.name) is table:
            meta.remove(table)
            dropped += 1
        # 类名注册表（declarative registry）里的引用一并摘掉，否则重新 import 时
        # 会刷「same class name and module name … will be replaced」警告。
        # _dispose_cls 是 SQLAlchemy 的官方清理入口：短名与 module.Class 两条
        # 引用（含 _MultipleClassMarker）都会按对象身份移除，不误删其他扩展的同名类。
        try:
            dispose = getattr(getattr(Base, "registry", None), "_dispose_cls", None)
            if callable(dispose):
                dispose(obj)
        except Exception:  # noqa: BLE001 - SQLAlchemy 内部结构变了也不影响功能
            pass
    return dropped


def purge_extension_modules(key: str) -> int:
    """清理 ``sys.modules`` 中该扩展的模块子树（更新/卸载时调用）。

    不清理的话，更新后 ``from . import crud`` 会命中旧子模块，热更新等于没更新。
    同时把该扩展声明的表从共享 metadata 摘掉，否则重新 import models 会报
    ``Table ... is already defined``。
    """
    prefix = extension_module_name(key)
    removed = [n for n in list(sys.modules) if n == prefix or n.startswith(prefix + ".")]
    for name in removed:
        module = sys.modules.get(name)
        if module is not None:
            _detach_extension_tables(module)
        sys.modules.pop(name, None)
    return len(removed)


def _load_module(file: Path, module_name: str, search_paths: list[Path] | None = None):
    """按文件路径加载 Python 模块（不依赖 sys.path）。

    必须先注册进 ``sys.modules`` 再 ``exec_module``：pydantic 2.11+ 不再从定义处
    的栈帧取父命名空间，而是按 ``cls.__module__`` 反查 ``sys.modules``。扩展普遍写了
    ``from __future__ import annotations``（注解是字符串），未注册时模型会被标记为
    「待补全」，直到生成 /openapi.json 或首次校验时才炸 ``class not fully defined``——
    表现为路由能调通、但 ``/docs`` 整页 500。

    search_paths: 传入时把该模块按**包**加载（``__path__`` 指向扩展目录），
    扩展内的 ``from . import crud`` / ``from .models import X`` 才可用。
    """
    spec = importlib.util.spec_from_file_location(
        module_name,
        file,
        submodule_search_locations=[str(p) for p in search_paths] if search_paths else None,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)  # 半个模块留在 sys.modules 更糟
        raise
    return module


@dataclass
class LoadedExtension:
    """一次扩展加载的结果（路由 + 模块 + 实际挂载数量）。"""

    key: str
    module: object | None = None
    router: APIRouter | None = None
    public_router: APIRouter | None = None
    route_count: int = 0
    extra: dict = field(default_factory=dict)


def _route_keys(router: APIRouter) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for r in router.routes:
        path = getattr(r, "path", "") or ""
        for method in getattr(r, "methods", None) or {"GET"}:
            keys.add((str(method).upper(), path))
    return keys


def _extension_route_target(route, key: str) -> bool:
    """判断某条 app 顶层路由是否属于指定扩展（前缀 /api/extensions/{key}）。

    兼容两种 FastAPI 行为：
    - 新版（FastAPI>=0.143 / Starlette 1.x）：``include_router`` 追加的是
      ``_IncludedRouter``，子路由嵌套其内、顶层无 ``path``；前缀记录在
      ``route.include_context.prefix``。只按 ``path`` 判断会一条都删不掉，
      卸载/更新后旧路由仍在。
    - 旧版：子路由被摊平为顶层 ``APIRoute``，带完整 ``path``。
    """
    prefix = f"/api/extensions/{key}"
    ctx = getattr(route, "include_context", None)
    if ctx is not None:
        rp = getattr(ctx, "prefix", "") or ""
        return rp == prefix or rp.startswith(prefix + "/")
    path = getattr(route, "path", "") or ""
    return bool(path) and (path == prefix or path.startswith(prefix + "/"))


def _app_route_keys(app: FastAPI, exclude_key: str | None = None) -> set[tuple[str, str]]:
    """活 app 上已有的 (method, path)，用于挂载前冲突检查。"""
    keys: set[tuple[str, str]] = set()
    for route in app.router.routes:
        if exclude_key and _extension_route_target(route, exclude_key):
            continue
        path = getattr(route, "path", "") or ""
        if not path:
            continue
        for method in getattr(route, "methods", None) or {"GET"}:
            keys.add((str(method).upper(), path))
    return keys


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
    # 扩展在 app.state 上挂的缓存一并清掉，避免卸载后残留对象
    state = getattr(app, "state", None)
    if state is not None:
        for attr in list(vars(state)) if hasattr(state, "__dict__") else []:
            if attr == f"ext_{key}" or attr.startswith(f"ext_{key}_"):
                try:
                    delattr(state, attr)
                except AttributeError:
                    pass
    return removed


def load_extension(ext_path: Path, key: str) -> LoadedExtension | None:
    """加载扩展模块并返回 router/public_router（无 router.py 返回 None）。

    不注册事件钩子——事件必须在路由挂载成功之后注册（见
    :func:`mount_extension_router`），否则挂载失败会留下悬空订阅。
    """
    router_file = ext_path / "router.py"
    if not router_file.is_file():
        return None
    purge_extension_modules(key)
    module = _load_module(router_file, extension_module_name(key), search_paths=[ext_path])
    router = getattr(module, "router", None)
    public_router = getattr(module, "public_router", None)
    if router is None and public_router is None:
        raise ImportError(f"扩展 {key} 的 router.py 未定义 router 或 public_router 对象")
    for name, value in (("router", router), ("public_router", public_router)):
        if value is not None and not isinstance(value, APIRouter):
            raise ImportError(f"扩展 {key} 的 {name} 必须是 fastapi.APIRouter")
    return LoadedExtension(key=key, module=module, router=router, public_router=public_router)


def _register_events(module, key: str) -> None:
    """调用扩展可选导出的 ``register_events(bus)``。

    幂等：先按 key 反注册再订阅（热重载不产生双份 handler）。
    失败仅记日志，**不影响路由挂载**——钩子是增强，不是加载前提。
    注意：本函数在模块导入期被调用，扩展的 register_events 不得做 DB/网络 IO。
    """
    fn = getattr(module, "register_events", None)
    if not callable(fn):
        return
    from .events import event_bus

    event_bus.unsubscribe_extension(key)
    try:
        fn(event_bus)
        logger.info("[extension] 已注册事件钩子: %s", key)
    except Exception as e:  # noqa: BLE001 - 钩子注册失败不阻塞扩展加载
        logger.error("[extension] %s register_events 失败（路由不受影响）: %s", key, e)


def load_extension_router(ext_path: Path, key: str) -> APIRouter | None:
    """兼容入口：加载 router.py 并注册事件钩子，返回主 router。

    新代码请用 :func:`load_extension` / :func:`mount_extension_router`。
    """
    loaded = load_extension(ext_path, key)
    if loaded is None:
        return None
    if loaded.module is not None:
        _register_events(loaded.module, key)
    return loaded.router


def mount_extension_router(app: FastAPI, key: str, ext_path: Path, auth_dependencies=None) -> int:
    """运行期热挂载单个扩展路由（先清除旧路由，支持更新/重装）。

    返回实际挂载的路由数量（无 router.py 返回 0）。
    挂载前做 (method, path) 冲突检查；挂载失败会反注册事件钩子。
    """
    if auth_dependencies is None:
        from app.core.deps import get_current_user

        auth_dependencies = [Depends(get_current_user)]

    loaded = load_extension(ext_path, key)
    if loaded is None:
        return 0

    existing = _app_route_keys(app, exclude_key=key)
    planned: set[tuple[str, str]] = set()
    if loaded.router is not None:
        planned |= _route_keys(loaded.router)
    if loaded.public_router is not None:
        planned |= _route_keys(loaded.public_router)
    conflicts = sorted(f"{m} {p}" for m, p in planned if (m, p) in existing)
    if conflicts:
        raise RuntimeError(f"扩展 {key} 路由与已挂载路由冲突: {', '.join(conflicts[:5])}")

    unmount_extension_router(app, key)
    prefix = f"/api/extensions/{key}"
    mounted = 0
    try:
        if loaded.router is not None:
            app.include_router(
                loaded.router,
                prefix=prefix,
                tags=[f"ext-{key}"],
                dependencies=[*auth_dependencies, Depends(require_extension(key))],
            )
            mounted += len(loaded.router.routes)
        if loaded.public_router is not None:
            # 公开路由只保留启用门禁，不强制登录（H5 填报/回调等场景）
            app.include_router(
                loaded.public_router,
                prefix=prefix,
                tags=[f"ext-{key}-public"],
                dependencies=[Depends(require_extension(key))],
            )
            mounted += len(loaded.public_router.routes)
    except Exception:
        from .events import event_bus

        event_bus.unsubscribe_extension(key)
        raise
    if loaded.module is not None:
        _register_events(loaded.module, key)
    runtime.interfaces[key] = {
        "has_router": loaded.router is not None,
        "has_public_router": loaded.public_router is not None,
        "route_count": mounted,
    }
    logger.info("[extension] 运行期热挂载扩展路由 %d 条: %s", mounted, key)
    return mounted


def mount_extensions(app: FastAPI, base_dir: Path, auth_dependencies=None) -> None:
    """扫描并挂载全部已安装扩展（模块导入期调用）。

    auth_dependencies: 挂到每个扩展路由上的附加依赖；
    默认 ``[Depends(get_current_user)]``，测试场景可传入空列表或替代实现。
    单个扩展加载/挂载失败只记日志，不阻塞其他扩展。
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
            mounted = mount_extension_router(
                app, key, Path(info["path"]), auth_dependencies=auth_dependencies
            )
        except Exception as e:  # noqa: BLE001 - 单个扩展失败不影响其他扩展
            logger.error("[extension] 加载 %s 路由失败: %s", key, e)
            _record_health(key, ok=False, error=str(e))
            continue
        if mounted:
            logger.info("[extension] 已挂载扩展路由: /api/extensions/%s", key)
            _record_health(key, ok=True)


def _record_health(key: str, *, ok: bool, error: str = "") -> None:
    """把加载结果写进 ``.state/health.json``（失败不抛出）。"""
    try:
        if runtime.store is None:
            return
        from datetime import datetime, timezone

        health = runtime.store.load("health", {}) or {}
        health[key] = {
            "ok": ok,
            "error": error,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        runtime.store.save("health", health)
    except Exception:  # noqa: BLE001 - 健康记录失败不影响加载
        pass


# ── 迁移（实现在 migrations.py，保留本模块历史入口）──────────────────────────

def run_extension_migrations(
    base_dir: Path,
    db: Session | None = None,
    *,
    only_key: str | None = None,
    force: bool = False,
) -> dict[str, dict]:
    """执行扩展迁移（按 key 独立事务；单扩展失败不阻塞其他扩展）。

    only_key: 只跑该扩展（安装/更新/修复时用）。
    force: 跳过 ``is_enabled`` 门禁（安装瞬间授权快照可能尚未刷新）。
    """
    from .migrations import run_migrations

    return run_migrations(base_dir, db=db, only_key=only_key, force=force)


def run_extension_migrations_for(key: str, db: Session | None = None, *, force: bool = True) -> dict:
    """只跑单个扩展迁移（安装/更新/修复）。"""
    base = runtime.extensions_dir
    if base is None:
        raise RuntimeError("扩展宿主尚未初始化（runtime.extensions_dir 为空）")
    return run_extension_migrations(base, db=db, only_key=key, force=force).get(key, {})
