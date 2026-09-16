# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""存储配置加载 单元测试

其余存储用例针对的历史接口（LocalStorage 传入根路径、save 传 tenant_id、
app.storage.factory.settings）在 cenkormes 已不存在，已清理。
"""
from app.storage.factory import load_storage_config


def test_load_storage_config_defaults_without_db():
    cfg = load_storage_config(None)
    assert cfg.driver == "local"