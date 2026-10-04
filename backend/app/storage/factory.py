# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""存储后端工厂：按配置解析具体 Storage 实现。

设计：驱动注册表 + 向后兼容降级。
- 默认 local；未注册/未实现的云驱动降级为 local 并告警，
  避免历史部署（STORAGE_DRIVER 配了云但驱动未就绪）导致上传中断。
- 云驱动实现 app.storage.base.Storage 协议后，调用 register_driver 注册即生效。
- CS-2 起 get_active_storage 将优先读取 CloudStorageConfig 表的 active_provider。
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.storage.base import Storage
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)

# 驱动名 -> 构造工厂（惰性调用，避免未装对应 SDK 时 import 期即失败）
_REGISTRY: dict[str, Callable[[], Storage]] = {
    "local": LocalStorage,
}


def register_driver(name: str, factory: Callable[[], Storage]) -> None:
    """注册一个存储驱动实现（供云驱动模块在导入时调用）。"""
    _REGISTRY[name] = factory


def registered_drivers() -> list[str]:
    return sorted(_REGISTRY.keys())


def _resolve_driver_name(driver: str | None) -> str:
    from app.core.config import settings
    name = (driver or getattr(settings, "STORAGE_DRIVER", "local") or "local").strip().lower()
    return name


def build_storage(driver: str | None = None, cfg: Any = None) -> Storage:
    """按驱动名构造 Storage；未注册或构造失败时降级为 local（向后兼容）。"""
    name = _resolve_driver_name(driver)
    factory = _REGISTRY.get(name)
    if factory is None:
        if name != "local":
            logger.warning("存储驱动 %s 未实现/未注册，降级为 local", name)
        return LocalStorage()
    try:
        return factory()
    except Exception as exc:  # noqa: BLE001 - 缺依赖/凭据等构造失败，降级本地保证可用
        logger.warning("构建存储驱动 %s 失败(%s)，降级为 local", name, exc)
        return LocalStorage()


def get_storage_backend(driver: str = "local") -> Storage:
    return build_storage(driver)


def get_active_storage(db: Any = None) -> Storage:
    # CS-2 起改为优先读取 CloudStorageConfig.active_provider；当前沿用 settings.STORAGE_DRIVER
    return build_storage(None)


def get_storage_for(driver: str, db: Any = None) -> Storage:
    return build_storage(driver)


def load_storage_config(db: Any = None) -> Any:
    from app.core.config import settings
    return type("Cfg", (), {"driver": settings.STORAGE_DRIVER})()
