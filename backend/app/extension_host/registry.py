# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展生命周期登记与审计。

不新增数据库表，全部落在 ``extensions/.state/``：

- ``registry.json``   每个扩展的版本、状态、包指纹、备份、数据策略
- ``lifecycle.jsonl`` 安装/更新/卸载/回滚/修复审计（5MB 轮转保留 5 份）
- ``health.json``     最近一次健康检查结果
- ``schema.json``     迁移执行记录（见 migrations.py）
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .state import StateStore, runtime

logger = logging.getLogger("uvicorn.error")

_LOCK = threading.Lock()
AUDIT_MAX_BYTES = 5 * 1024 * 1024
AUDIT_KEEP = 5


def _store() -> StateStore | None:
    if runtime.store is not None:
        return runtime.store
    if runtime.extensions_dir is not None:
        return StateStore(Path(runtime.extensions_dir) / ".state")
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── registry ────────────────────────────────────────────────────────────────

def load_registry() -> dict[str, dict]:
    store = _store()
    if store is None:
        return {}
    data = store.load("registry", {}) or {}
    return data if isinstance(data, dict) else {}


def save_registry(data: dict[str, dict]) -> None:
    store = _store()
    if store is not None:
        store.save("registry", data)


def registry_info(key: str) -> dict:
    return load_registry().get(key) or {}


def update_registry(key: str, **fields: Any) -> dict:
    """合并写入某扩展的 registry 记录（None 值表示删除该字段）。"""
    with _LOCK:
        data = load_registry()
        item = dict(data.get(key) or {})
        for name, value in fields.items():
            if value is None:
                item.pop(name, None)
            else:
                item[name] = value
        data[key] = item
        save_registry(data)
    return item


def drop_registry(key: str) -> None:
    with _LOCK:
        data = load_registry()
        if data.pop(key, None) is not None:
            save_registry(data)


# ── 审计 ────────────────────────────────────────────────────────────────────

def _audit_path() -> Path | None:
    store = _store()
    if store is None:
        return None
    state_dir = getattr(store, "_dir", None)
    if state_dir is None:
        return None
    return Path(state_dir) / "lifecycle.jsonl"


def _rotate(path: Path) -> None:
    if not path.is_file() or path.stat().st_size < AUDIT_MAX_BYTES:
        return
    for index in range(AUDIT_KEEP - 1, 0, -1):
        src = path.with_name(f"{path.name}.{index}")
        dst = path.with_name(f"{path.name}.{index + 1}")
        if src.is_file():
            src.replace(dst)
    path.replace(path.with_name(f"{path.name}.1"))


def audit(operation: str, key: str, **fields: Any) -> dict:
    """追加一条生命周期审计（失败只记日志，绝不影响主流程）。"""
    entry = {"at": now_iso(), "operation": operation, "key": key, **fields}
    path = _audit_path()
    if path is None:
        logger.info("[extension] audit %s %s %s", operation, key, fields)
        return entry
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate(path)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:  # noqa: BLE001 - 审计失败不影响业务
        logger.warning("[extension] 写审计失败: %s", e)
    return entry


def read_audit(limit: int = 100, key: str | None = None) -> list[dict]:
    """读取最近审计（新→旧）。"""
    path = _audit_path()
    if path is None or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if key and entry.get("key") != key:
            continue
        items.append(entry)
        if len(items) >= limit:
            break
    return items


# ── 健康 ────────────────────────────────────────────────────────────────────

def write_health(key: str, ok: bool, errors: list[str] | None = None, **extra: Any) -> dict:
    store = _store()
    record = {
        "ok": ok,
        "errors": list(errors or []),
        "checked_at": now_iso(),
        **extra,
    }
    if store is not None:
        try:
            health = store.load("health", {}) or {}
            health[key] = record
            store.save("health", health)
        except Exception as e:  # noqa: BLE001
            logger.warning("[extension] 写健康记录失败: %s", e)
    update_registry(key, health="ok" if ok else "error", last_error="; ".join(record["errors"])[:500])
    return record


def read_health(key: str) -> dict:
    store = _store()
    if store is None:
        return {}
    try:
        return (store.load("health", {}) or {}).get(key) or {}
    except Exception:  # noqa: BLE001
        return {}
