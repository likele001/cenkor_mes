# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展迁移 v2：``migrations.sql`` + ``migrations/NNNN_*.py``，按 key 隔离执行。

约定：

- ``migrations.sql``：新装建表，只允许幂等语句（``CREATE TABLE IF NOT EXISTS`` 等）。
  指纹仍记在 ``.state/migrations.json``（``mtime:size``），与旧版兼容。
- ``migrations/0002_add_xxx.py``：存量升级，提供 ``apply(db, ctx)``；``ctx`` 提供
  ``add_column_if_missing`` / ``create_index_if_missing`` / ``create_table_if_missing``
  / ``drop_index_if_exists``，底层查 ``information_schema``（SQLite 走 PRAGMA）。
- 记录落 ``.state/schema.json``：``key -> [{version, filename, checksum, applied_at}]``。
- 每个扩展独立 try/except：一个失败不阻塞其他扩展，失败写 health/registry 且不换入新版本。
"""
from __future__ import annotations

import hashlib
import importlib.util
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from .registry import update_registry, write_health
from .state import StateStore, runtime

logger = logging.getLogger("uvicorn.error")

_DANGEROUS = re.compile(
    r"\b(DROP\s+TABLE|TRUNCATE\s+TABLE|RENAME\s+TABLE|ALTER\s+TABLE\s+\S+\s+(DROP|MODIFY|CHANGE))\b",
    re.IGNORECASE,
)
_NAME_RE = re.compile(r"^\d{3,}_[A-Za-z0-9_]+\.py$")


class MigrationError(RuntimeError):
    """迁移失败（不可继续换入新版本）。"""


def split_sql(sql_text: str) -> list[str]:
    """按顶层分号拆分 SQL，字符串/标识符/注释里的分号不切。

    支持 ``'...'`` ``"..."`` ``` `...` ```（含 ``''`` 与反斜杠转义）、``--`` 行注释和
    ``/* */`` 块注释。存储过程等内部分号语句仍不支持。
    """
    statements: list[str] = []
    buf: list[str] = []
    quote = ""
    i, n = 0, len(sql_text)
    while i < n:
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < n else ""
        if quote:
            buf.append(ch)
            if ch == "\\" and quote in ("'", '"') and nxt:
                buf.append(nxt)
                i += 2
                continue
            if ch == quote:
                if nxt == quote:  # 双写转义
                    buf.append(nxt)
                    i += 2
                    continue
                quote = ""
            i += 1
            continue
        if ch == "-" and nxt == "-":
            j = sql_text.find("\n", i)
            i = n if j == -1 else j
            continue
        if ch == "/" and nxt == "*":
            j = sql_text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


class MigrationContext:
    """迁移脚本可用的幂等 DDL 助手（MySQL information_schema / SQLite PRAGMA）。"""

    def __init__(self, db: Session, key: str):
        self.db = db
        self.key = key
        bind = db.get_bind() if hasattr(db, "get_bind") else None
        self.dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""

    # ---------- 探测 ----------
    def _scalar(self, sql: str, **params):
        return self.db.execute(text(sql), params).scalar()

    def table_exists(self, table: str) -> bool:
        if self.dialect == "sqlite":
            return bool(self._scalar(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:t", t=table
            ))
        return bool(self._scalar(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :t", t=table
        ))

    def column_exists(self, table: str, column: str) -> bool:
        if self.dialect == "sqlite":
            rows = self.db.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return any((row[1] or "") == column for row in rows)
        return bool(self._scalar(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c",
            t=table, c=column,
        ))

    def index_exists(self, table: str, index: str) -> bool:
        if self.dialect == "sqlite":
            return bool(self._scalar(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=:i", i=index
            ))
        return bool(self._scalar(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :i",
            t=table, i=index,
        ))

    # ---------- 幂等 DDL ----------
    def execute(self, sql: str, **params):
        return self.db.execute(text(sql), params)

    def add_column_if_missing(self, table: str, column: str, ddl: str) -> bool:
        """``ddl`` 是列定义（如 ``VARCHAR(64) NULL``）。已存在则不动。"""
        if self.column_exists(table, column):
            return False
        self.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        return True

    def create_index_if_missing(
        self, table: str, index: str, ddl: str | list[str] | tuple[str, ...]
    ) -> bool:
        """``ddl`` 可为完整 ``CREATE INDEX ...``、列清单字符串或列名列表。"""
        if self.index_exists(table, index):
            return False
        if isinstance(ddl, (list, tuple)):
            ddl = ", ".join(str(col) for col in ddl)
        stmt = ddl.strip()
        if stmt.upper().startswith("CREATE "):
            self.execute(stmt)
        else:
            self.execute(f"CREATE INDEX {index} ON {table} ({stmt})")
        return True

    def create_table_if_missing(self, table: str, ddl: str) -> bool:
        if self.table_exists(table):
            return False
        stmt = ddl.strip()
        if not stmt.upper().startswith("CREATE "):
            stmt = f"CREATE TABLE {table} ({ddl})"
        self.execute(stmt)
        return True

    def drop_index_if_exists(self, table: str, index: str) -> bool:
        """只清索引，不碰表/列（表与数据的删除永远走「彻底清除」）。"""
        if not self.index_exists(table, index):
            return False
        if self.dialect == "sqlite":
            self.execute(f"DROP INDEX {index}")
        else:
            self.execute(f"DROP INDEX {index} ON {table}")
        return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_apply(file: Path, key: str, seq: int):
    module_name = f"cenkormes_ext_{key}__migration_{seq}"
    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        raise MigrationError(f"无法加载迁移文件: {file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    fn = getattr(module, "apply", None)
    if not callable(fn):
        raise MigrationError(f"迁移文件 {file.name} 缺少 apply(db, ctx)")
    return fn


def _python_migrations(ext_path: Path) -> list[Path]:
    folder = ext_path / "migrations"
    if not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix == ".py"]
    bad = [p.name for p in files if not _NAME_RE.match(p.name)]
    if bad:
        raise MigrationError(f"迁移文件名不合法（要求 NNNN_name.py）：{', '.join(sorted(bad))}")
    return sorted(files, key=lambda p: p.name)


def _apply_sql_legacy(key: str, ext_path: Path, db: Session, applied: dict) -> int:
    file = ext_path / "migrations.sql"
    if not file.is_file():
        return 0
    stat = file.stat()
    fingerprint = f"{int(stat.st_mtime)}:{stat.st_size}"
    if applied.get(key) == fingerprint:
        return 0
    statements = split_sql(file.read_text(encoding="utf-8"))
    for stmt in statements:
        db.execute(text(stmt))
    db.commit()
    applied[key] = fingerprint
    logger.info("[extension] %s migrations.sql 已执行（%d 条语句）", key, len(statements))
    return len(statements)


def _apply_python(key: str, ext_path: Path, db: Session, records: list[dict]) -> list[str]:
    applied_names: list[str] = []
    by_name = {str(r.get("filename") or ""): r for r in records}
    for seq, file in enumerate(_python_migrations(ext_path), start=1):
        checksum = _sha256(file)
        prev = by_name.get(file.name)
        if prev:
            if str(prev.get("checksum") or "") != checksum:
                raise MigrationError(
                    f"迁移文件 {file.name} 在已执行后被修改（checksum 不一致），拒绝继续"
                )
            continue
        source = file.read_text(encoding="utf-8")
        if _DANGEROUS.search(source):
            raise MigrationError(f"迁移文件 {file.name} 含破坏性 DDL（DROP/TRUNCATE/RENAME/MODIFY）")
        fn = _load_apply(file, key, seq)
        ctx = MigrationContext(db, key)
        fn(db, ctx)
        db.commit()
        version = int(re.match(r"^(\d+)", file.name).group(1))
        record = {
            "version": version,
            "filename": file.name,
            "checksum": checksum,
            "applied_at": _now(),
        }
        records.append(record)
        by_name[file.name] = record
        applied_names.append(file.name)
        logger.info("[extension] %s 迁移 %s 已执行", key, file.name)
    records.sort(key=lambda r: (int(r.get("version") or 0), str(r.get("filename") or "")))
    return applied_names


def apply_for_key(key: str, ext_path: Path, db: Session, *, applied: dict, schema: dict) -> dict:
    """执行单个扩展的迁移（调用方负责提交/回滚与状态落盘）。"""
    sql_count = _apply_sql_legacy(key, ext_path, db, applied)
    records = list(schema.get(key) or [])
    names = _apply_python(key, ext_path, db, records)
    schema[key] = records
    return {"ok": True, "sql_statements": sql_count, "python_migrations": names}


def run_migrations(
    base_dir: Path,
    db: Session | None = None,
    *,
    only_key: str | None = None,
    force: bool = False,
) -> dict[str, dict]:
    """按 key 独立执行迁移；返回 ``{key: {ok, error?, ...}}``。

    force=True 跳过 ``is_enabled`` 门禁（安装/更新瞬间授权快照可能尚未刷新）。
    """
    from app.core.db import SessionLocal

    if runtime.store is None:
        runtime.store = StateStore(base_dir / ".state")
    store: StateStore = runtime.store
    applied: dict = store.load("migrations", {}) or {}
    schema: dict = store.load("schema", {}) or {}

    own_session = db is None
    if own_session:
        db = SessionLocal()
    results: dict[str, dict] = {}
    try:
        for key, info in runtime.installed.items():
            if only_key and key != only_key:
                continue
            if not force and not runtime.is_enabled(key):
                continue
            try:
                results[key] = apply_for_key(key, Path(info["path"]), db, applied=applied, schema=schema)
                write_health(key, True, [], migrations="ok")
            except Exception as e:  # noqa: BLE001 - 单扩展失败不阻塞其他扩展
                db.rollback()
                message = str(e) or e.__class__.__name__
                results[key] = {"ok": False, "error": message}
                logger.error("[extension] %s 迁移失败: %s", key, message)
                write_health(key, False, [f"迁移失败: {message}"])
                update_registry(key, status="broken", last_error=message)
        store.save("migrations", applied)
        store.save("schema", schema)
    finally:
        if own_session:
            db.close()
    return results
