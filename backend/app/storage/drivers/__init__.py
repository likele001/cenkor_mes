# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储驱动包。

刻意在包级别不 import 具体驱动模块，避免未安装对应 SDK 时导入本包即失败；
由 app.storage.factory 按需惰性 import 具体驱动。
"""
