# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""MES 扩展宿主：可插拔应用加载、生命周期与请求级门控。

- 扫描 ``EXTENSIONS_DIR`` 下每个子目录（含 manifest.json 的扩展包）
- 校验 manifest（v1 兼容 / v2 强校验）、执行迁移、挂载 ``/api/extensions/{key}``
- 请求级门控：未启用（本地禁用 / 授权非 active）返回 403；卸载中返回 503
- 生命周期（安装/更新/卸载/彻底清除/回滚/修复）见 ``lifecycle.py``
- 授权快照由独立应用中心（cenkor-admin）下发

应用目录、发卡、实例绑定、吊销等**管理动作在独立应用中心完成**，
MES 侧只保留本地启停与「彻底清除」这类不可逆操作。
"""
from .events import Event, EventBus, InterceptDecision, event_bus  # noqa: F401
from .host import (  # noqa: F401
    check_health,
    cleanup_permissions,
    extensions_base_dir,
    hot_setup_extension,
    hot_teardown_extension,
    mount_all,
    set_extension_enabled,
    startup_host,
    sync_permissions,
)
from .lifecycle import (  # noqa: F401
    LifecycleError,
    install_or_update,
    lifecycle_logs,
    preflight,
    purge_data,
    repair,
    rollback,
    set_enabled,
    uninstall,
)
from .manifest import ExtensionManifest, ManifestError, load_manifest  # noqa: F401
from .registry import read_audit, read_health, registry_info  # noqa: F401
from .state import runtime  # noqa: F401
from .version import compare_versions, is_newer, is_semver, meets_min_version, read_core_version  # noqa: F401
