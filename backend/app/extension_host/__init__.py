# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""MES 扩展宿主：极薄的扩展加载机制（零管理界面）。

- 扫描 ``EXTENSIONS_DIR`` 下每个子目录（含 manifest.json 的扩展包）
- 校验 manifest、执行幂等迁移、挂载 ``/api/extensions/{key}`` 路由
- 请求级门控：未启用（本地禁用 / 授权非 active）返回 403
- 可选周期性心跳：从独立应用中心（cenkormes-center）同步授权快照

应用目录、发卡、实例绑定、吊销等**全部管理动作均在独立应用中心完成**，
MES 不提供任何应用安装/授权管理界面。
"""
from .host import (  # noqa: F401
    extensions_base_dir,
    hot_setup_extension,
    hot_teardown_extension,
    mount_all,
    startup_host,
)
from .state import runtime  # noqa: F401
