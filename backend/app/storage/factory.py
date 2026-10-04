# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""存储后端工厂：按配置解析具体 Storage 实现。

设计：
- 内置云驱动（aliyun/tencent/qiniu）按需惰性 import，避免未装 SDK 时导入期失败；
  构造时从 cloud_storage_config 服务加载该 provider 的解密凭据。
- 向后兼容降级：未注册/构造失败（缺 SDK、凭据不全）一律降级 local 并告警，
  绝不因配置未就绪导致上传中断。
- register_driver 供测试/扩展注册零参自定义驱动。
"""
from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from app.storage.base import Storage
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)

# 内置云驱动：provider -> (module, class)；惰性 import
_CLOUD_BUILDERS: dict[str, tuple[str, str]] = {
    "aliyun": ("app.storage.drivers.aliyun", "AliyunOSSStorage"),
    "tencent": ("app.storage.drivers.tencent", "TencentCOSStorage"),
    "qiniu": ("app.storage.drivers.qiniu", "QiniuStorage"),
}

# 自定义零参驱动注册表（测试/扩展用）
_REGISTRY: dict[str, Callable[[], Storage]] = {}


def register_driver(name: str, factory: Callable[[], Storage]) -> None:
    """注册一个零参存储驱动（测试/扩展）。"""
    _REGISTRY[name] = factory


def registered_drivers() -> list[str]:
    return sorted({"local", *_REGISTRY, *_CLOUD_BUILDERS})


def _resolve_driver_name(driver: str | None) -> str:
    from app.core.config import settings
    return (driver or getattr(settings, "STORAGE_DRIVER", "local") or "local").strip().lower()


def _load_creds(provider: str, db: Any) -> dict:
    if db is None:
        return {}
    try:
        from app.services.cloud_storage_config import get_credentials
        return get_credentials(db, provider) or {}
    except Exception as exc:  # noqa: BLE001 - 读配置失败不致命，交给构造校验
        logger.warning("加载 %s 凭据失败: %s", provider, exc)
        return {}


def _construct(name: str, db: Any) -> Storage | None:
    if name == "local":
        return LocalStorage()
    if name in _REGISTRY:
        return _REGISTRY[name]()
    entry = _CLOUD_BUILDERS.get(name)
    if entry is None:
        return None
    module_path, class_name = entry
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(_load_creds(name, db))


def build_storage(driver: str | None = None, cfg: Any = None, db: Any = None) -> Storage:
    """按驱动名构造 Storage；未注册或构造失败时降级为 local（向后兼容）。"""
    name = _resolve_driver_name(driver)
    try:
        storage = _construct(name, db)
    except Exception as exc:  # noqa: BLE001 - 缺依赖/凭据不全等，降级本地保证可用
        logger.warning("构建存储驱动 %s 失败(%s)，降级为 local", name, exc)
        return LocalStorage()
    if storage is None:
        if name != "local":
            logger.warning("存储驱动 %s 未实现/未注册，降级为 local", name)
        return LocalStorage()
    return storage


def get_storage_backend(driver: str = "local") -> Storage:
    return build_storage(driver)


def get_active_storage(db: Any = None) -> Storage:
    """返回当前激活驱动：优先读 CloudStorageConfig.active_provider，回退 settings。"""
    provider = None
    if db is not None:
        try:
            from app.services.cloud_storage_config import get_or_create
            provider = get_or_create(db).active_provider
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取激活 provider 失败(%s)，回退 settings", exc)
            provider = None
    return build_storage(provider, db=db)


def get_storage_for(driver: str, db: Any = None) -> Storage:
    return build_storage(driver, db=db)


def load_storage_config(db: Any = None) -> Any:
    from app.core.config import settings
    return type("Cfg", (), {"driver": settings.STORAGE_DRIVER})()
