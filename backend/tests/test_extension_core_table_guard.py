# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展清理不得摘掉核心表（扩展顺带 import 核心表的真实场景）。

根因链：worker 的 ``worker_init`` 与 ``worker_process_init`` 各调一次
``import_extension_modules()``；第二次会先走 ``purge_extension_modules()``，而
``_detach_extension_tables()`` 对 Table 对象强制把 owner 记成「当前扩展模块名」，
于是扩展模块里 ``from app.models.user import user_roles`` 引进来的**核心表**被从
共享 metadata 摘掉。``Role.users`` 这类字符串关系随后在首次 mapper 配置时找不到
表名，扩展任务在子进程里必失败：``expression 'user_roles' failed to locate a name``。

同时保证原有行为不被削弱：扩展**自己**声明的表在清理时仍会被摘掉。
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import Table

from app.extension_host.loader import load_extension, purge_extension_modules
from app.models.base import Base
from app.models.user import user_roles

KEY = "guardtest"


def _manifest(key: str) -> str:
    return json.dumps(
        {
            "key": key,
            "name": f"{key} 应用",
            "version": "1.0.0",
            "manifest_version": 2,
            "schema_version": 1,
            "product": "cenkormes",
            "min_core_version": "2.0.0",
            "permissions": [{"code": f"ext.{key}.view", "name": "查看"}],
            "data": {"retention": "keep", "tables": []},
        },
        ensure_ascii=False,
    )


def _write_extension(base: Path, key: str, router_src: str) -> Path:
    ext = base / key
    ext.mkdir()
    (ext / "manifest.json").write_text(_manifest(key), encoding="utf-8")
    (ext / "router.py").write_text(router_src, encoding="utf-8")
    return ext


CORE_TABLE_IMPORT = (
    "from fastapi import APIRouter\n"
    "from app.models.user import user_roles  # noqa: F401 - 故意把核心表引进扩展命名空间\n"
    "router = APIRouter()\n"
)


def test_purge_keeps_core_table_imported_by_extension(tmp_path: Path) -> None:
    """扩展 purge 后核心表仍在 metadata 里（回归主用例）。"""
    ext = _write_extension(tmp_path, KEY, CORE_TABLE_IMPORT)
    assert load_extension(ext, KEY) is not None
    assert "user_roles" in Base.metadata.tables

    purge_extension_modules(KEY)

    assert "user_roles" in Base.metadata.tables, "核心表被扩展清理误摘"
    assert Base.metadata.tables["user_roles"] is user_roles


def test_double_load_keeps_core_tables(tmp_path: Path) -> None:
    """连续两次加载（模拟 worker_init + worker_process_init）核心表不受影响。"""
    ext = _write_extension(tmp_path, KEY, CORE_TABLE_IMPORT)
    try:
        assert load_extension(ext, KEY) is not None
        assert load_extension(ext, KEY) is not None  # 第二次会先 purge 再 import
        assert "user_roles" in Base.metadata.tables
        assert Base.metadata.tables["user_roles"] is user_roles
    finally:
        purge_extension_modules(KEY)


def test_purge_still_drops_extension_owned_table(tmp_path: Path) -> None:
    """扩展自己命令式声明的表，清理时仍必须摘掉（保证热更新不撞 Table already defined）。"""
    router_src = (
        "from fastapi import APIRouter\n"
        "from sqlalchemy import Column, Integer, Table\n"
        "from app.models.base import Base\n"
        "router = APIRouter()\n"
        "ext_rows = Table(\n"
        "    'ext_guardtest_rows', Base.metadata, Column('id', Integer, primary_key=True)\n"
        ")\n"
    )
    ext = _write_extension(tmp_path, KEY, router_src)
    try:
        assert load_extension(ext, KEY) is not None
        assert "ext_guardtest_rows" in Base.metadata.tables
    finally:
        purge_extension_modules(KEY)

    assert "ext_guardtest_rows" not in Base.metadata.tables, "扩展自有表应在清理时摘除"
