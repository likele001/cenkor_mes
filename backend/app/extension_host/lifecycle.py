# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展生命周期（安装 / 更新 / 卸载 / 彻底清除 / 回滚 / 修复 / 启停）。

设计不变量：

- live 目录永远是完整版本：新版本先解压到 ``.staging``，迁移成功后才换入。
- 更新前把旧版移到 ``.backup/<key>/<version>-<ts>``（保留最近 3 份），
  换入失败立即换回，业务数据不受影响。
- 迁移只做加法（新列可空/不删列/不改类型），失败不换入新版本。
- 卸载默认保留数据；「彻底清除」必须先导出 JSONL 备份、只删 manifest 声明的
  own 表，核心表与其他扩展表在 denylist 中一律拒绝 DROP。
- 所有动作写 ``.state/lifecycle.jsonl`` 审计与 ``.state/registry.json``。
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import re
import shutil
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Iterable

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .manifest import ExtensionManifest, ManifestError, load_manifest
from .registry import audit, drop_registry, now_iso, read_audit, registry_info, update_registry, write_health
from .state import runtime
from .version import compare_versions, is_semver, meets_min_version, read_core_version

logger = logging.getLogger("uvicorn.error")

PRODUCT = "cenkormes"
MAX_UNPACK_BYTES = 200 * 1024 * 1024
MAX_UNPACK_FILES = 5000
BACKUP_KEEP = 3
DRAIN_SECONDS = 2.0

FORBIDDEN_DIRS = {"__MACOSX", ".git", ".svn", ".hg", "node_modules", "__pycache__", ".idea", ".vscode"}
FORBIDDEN_SUFFIX = {".pyc", ".pyo", ".bak", ".swp", ".swo", ".orig", ".rej"}
_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?([A-Za-z0-9_]+)[`\"]?", re.IGNORECASE
)

_KEY_LOCKS: dict[str, threading.Lock] = {}
_KEY_LOCKS_GUARD = threading.Lock()


class LifecycleError(RuntimeError):
    """生命周期操作失败（status_code 决定 HTTP 语义）。"""

    def __init__(self, message: str, status_code: int = 400, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.extra = extra


@dataclass
class Preflight:
    key: str
    version: str
    manifest: ExtensionManifest
    sha256: str
    members: list[str] = field(default_factory=list)
    action: str = "install"
    previous_version: str = ""


# ── 基础路径与锁 ────────────────────────────────────────────────────────────

def base_dir() -> Path:
    from .host import extensions_base_dir

    return Path(runtime.extensions_dir or extensions_base_dir())


def live_dir(key: str) -> Path:
    return base_dir() / key


def staging_root() -> Path:
    return base_dir() / ".staging"


def backup_root() -> Path:
    return base_dir() / ".backup"


def trash_root() -> Path:
    return base_dir() / ".trash"


def data_root() -> Path:
    return base_dir() / "data"


def _state_dir() -> Path:
    return base_dir() / ".state"


@contextlib.contextmanager
def use_base(path):
    """临时把生命周期根目录指向指定路径（市场安装与隔离测试用）。"""
    previous = runtime.extensions_dir
    runtime.extensions_dir = Path(path)
    try:
        yield Path(path)
    finally:
        runtime.extensions_dir = previous


@contextlib.contextmanager
def lifecycle_lock(key: str, *, timeout: float = 30.0):
    """进程内锁 + 文件锁，防并发安装把目录换乱。"""
    with _KEY_LOCKS_GUARD:
        lock = _KEY_LOCKS.setdefault(key, threading.Lock())
    if not lock.acquire(timeout=timeout):
        raise LifecycleError(f"扩展 {key} 正在被其他操作占用，请稍后重试", status_code=409)
    handle = None
    try:
        state = _state_dir()
        state.mkdir(parents=True, exist_ok=True)
        handle = (state / "lifecycle.lock").open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise LifecycleError(f"扩展 {key} 正在被其他进程操作，请稍后重试", status_code=409)
        yield
    finally:
        if handle is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        lock.release()


# ── 冲突探测 ────────────────────────────────────────────────────────────────

def core_table_names() -> set[str]:
    try:
        import app.models  # noqa: F401 - 触发全部模型注册
        from app.models.base import Base

        return set(Base.metadata.tables)
    except Exception as e:  # noqa: BLE001 - 取不到核心表时不阻断（denylist 仍含内置表）
        logger.warning("[extension] 读取核心表清单失败: %s", e)
        return set()


def own_tables(manifest: ExtensionManifest, ext_path: Path | None = None) -> set[str]:
    """own 表 = manifest 声明 mode=own ∪ migrations.sql 里的 CREATE TABLE。"""
    tables = {
        str(t.get("name")).strip()
        for t in ((manifest.data or {}).get("tables") or [])
        if isinstance(t, dict) and t.get("name") and str(t.get("mode") or "own") == "own"
    }
    if ext_path is not None:
        sql_file = Path(ext_path) / "migrations.sql"
        if sql_file.is_file():
            try:
                tables |= set(_CREATE_TABLE_RE.findall(sql_file.read_text(encoding="utf-8")))
            except OSError:
                pass
    return tables


def other_extension_tables(key: str) -> set[str]:
    tables: set[str] = set()
    for other_key, info in runtime.installed.items():
        if other_key == key:
            continue
        try:
            tables |= own_tables(info["manifest"], Path(info["path"]))
        except Exception:  # noqa: BLE001 - 单个扩展 manifest 异常不影响其他判断
            continue
    return tables


def own_tables_from_zip(manifest: ExtensionManifest, zf: zipfile.ZipFile) -> set[str]:
    """preflight 阶段没能解压落盘：own 表 = manifest mode=own ∪ 包内 migrations.sql。"""
    tables = own_tables(manifest)
    try:
        sql = zf.read("migrations.sql").decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        sql = ""
    if sql:
        tables |= set(_CREATE_TABLE_RE.findall(sql))
    return tables


def _check_table_conflicts(
    key: str, manifest: ExtensionManifest, zf: zipfile.ZipFile | None = None
) -> None:
    # 只校验扩展真正拥有的表；manifest 里 mode=read/write 的是对核心表的引用，
    # 属于预期内的读写依赖，不应参与冲突判断。
    mine = own_tables_from_zip(manifest, zf) if zf is not None else own_tables(manifest)
    if not mine:
        return
    core = core_table_names()
    clash = sorted(mine & core)
    if clash:
        raise LifecycleError(f"扩展表与核心表冲突：{', '.join(clash[:5])}", status_code=409)
    clash = sorted(mine & other_extension_tables(key))
    if clash:
        raise LifecycleError(f"扩展表与其他已装扩展冲突：{', '.join(clash[:5])}", status_code=409)


# ── 包校验（preflight）──────────────────────────────────────────────────────

def _validate_members(zf: zipfile.ZipFile) -> list[str]:
    total = 0
    names: list[str] = []
    for info in zf.infolist():
        raw = info.filename
        if raw.endswith("/"):
            continue
        if not raw or "\\" in raw or raw.startswith("/"):
            raise LifecycleError(f"扩展包含非法路径：{raw!r}")
        parts = PurePosixPath(raw).parts
        if any(p in ("", ".", "..") for p in parts):
            raise LifecycleError(f"扩展包含路径穿越：{raw!r}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise LifecycleError(f"扩展包含符号链接：{raw!r}")
        if any(p in FORBIDDEN_DIRS for p in parts[:-1]) or parts[-1] in FORBIDDEN_DIRS:
            raise LifecycleError(f"扩展包含禁止目录：{raw!r}")
        if PurePosixPath(raw).suffix.lower() in FORBIDDEN_SUFFIX:
            raise LifecycleError(f"扩展包含禁止文件：{raw!r}")
        total += int(info.file_size or 0)
        if total > MAX_UNPACK_BYTES:
            raise LifecycleError("扩展包解压后体积超限")
        names.append(raw)
        if len(names) > MAX_UNPACK_FILES:
            raise LifecycleError("扩展包文件数超限")
    if "manifest.json" not in names:
        raise LifecycleError("扩展包根级缺少 manifest.json（不允许再套一层目录）")
    return names


def _read_manifest_from_zip(zf: zipfile.ZipFile) -> ExtensionManifest:
    tmp = staging_root() / f".manifest-{uuid.uuid4().hex[:8]}"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        (tmp / "manifest.json").write_bytes(zf.read("manifest.json"))
        return load_manifest(tmp, check_dir_name=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _check_dependencies(manifest: ExtensionManifest) -> None:
    for dep in manifest.dependencies or []:
        dep_key = str(dep.get("key") or "").strip()
        if not dep_key:
            continue
        if dep_key not in runtime.installed:
            raise LifecycleError(f"缺少依赖扩展：{dep_key}", status_code=409)
        minimum = str(dep.get("min_version") or dep.get("version") or "").strip()
        if minimum and not minimum.startswith((">", "<", "=", "~", "^")):
            current = getattr(runtime.installed[dep_key]["manifest"], "version", "")
            if is_semver(minimum) and not meets_min_version(current, minimum):
                raise LifecycleError(
                    f"依赖 {dep_key} 版本过低（需要 {minimum}，已装 {current}）", status_code=409
                )


def _check_core_version(manifest: ExtensionManifest) -> None:
    current = runtime.app_version or read_core_version()
    if manifest.min_core_version and not meets_min_version(current, manifest.min_core_version):
        raise LifecycleError(
            f"扩展要求核心版本 >= {manifest.min_core_version}，当前 {current}", status_code=409
        )
    if manifest.max_core_version and compare_versions(current, manifest.max_core_version) > 0:
        raise LifecycleError(
            f"扩展仅支持核心版本 <= {manifest.max_core_version}，当前 {current}", status_code=409
        )


def preflight(package_bytes: bytes, app_key: str, *, product: str = PRODUCT) -> Preflight:
    """包级校验：key/manifest/semver/产品/核心版本/依赖/表冲突/zip 成员。"""
    import hashlib

    try:
        zf = zipfile.ZipFile(BytesIO(package_bytes))
    except zipfile.BadZipFile as e:
        raise LifecycleError(f"扩展包不是合法 zip：{e}") from e
    with zf:
        members = _validate_members(zf)
        try:
            manifest = _read_manifest_from_zip(zf)
        except ManifestError as e:
            raise LifecycleError(str(e)) from e
        if manifest.key != app_key:
            raise LifecycleError(f"扩展 key 不匹配：包内 {manifest.key} != 请求 {app_key}")
        if manifest.product and manifest.product != product:
            raise LifecycleError(f"扩展包产品不匹配：{manifest.product} != {product}", status_code=400)
        if not is_semver(manifest.version):
            raise LifecycleError(f"扩展版本号不是 semver：{manifest.version!r}")
        _check_core_version(manifest)
        _check_dependencies(manifest)
        _check_table_conflicts(manifest.key, manifest, zf)
    return Preflight(
        key=manifest.key,
        version=manifest.version,
        manifest=manifest,
        sha256=hashlib.sha256(package_bytes).hexdigest(),
        members=members,
    )


# ── staging / backup / swap ─────────────────────────────────────────────────

def stage(package_bytes: bytes, pre: Preflight) -> Path:
    """解压到 ``.staging/<key>-<version>-<uuid>``，不碰 live 目录。"""
    staging_root().mkdir(parents=True, exist_ok=True)
    target = staging_root() / f"{pre.key}-{pre.version}-{uuid.uuid4().hex[:8]}"
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    try:
        with zipfile.ZipFile(BytesIO(package_bytes)) as zf:
            for name in pre.members:
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, dest.open("wb") as out:
                    shutil.copyfileobj(src, out)
        for path in target.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        target.chmod(0o755)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return target


def _prune_backups(folder: Path) -> None:
    backups = sorted([p for p in folder.iterdir() if p.is_dir()], key=lambda p: p.name)
    for old in backups[:-BACKUP_KEEP]:
        shutil.rmtree(old, ignore_errors=True)


def backup_target(key: str, version: str) -> Path:
    """返回旧版将要移入的备份路径（并顺带清理超出保留份数的旧备份）。"""
    folder = backup_root() / key
    folder.mkdir(parents=True, exist_ok=True)
    _prune_backups(folder)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return folder / f"{version or 'unknown'}-{stamp}"


def latest_backup(key: str) -> Path | None:
    folder = backup_root() / key
    if not folder.is_dir():
        return None
    items = sorted([p for p in folder.iterdir() if p.is_dir()], key=lambda p: p.name)
    return items[-1] if items else None


def swap(key: str, stage_dir: Path, backup_path: Path | None) -> dict:
    """live → backup，stage → live；第二步失败立即换回旧版。"""
    live = live_dir(key)
    moved = False
    if live.exists():
        if backup_path is None:
            raise LifecycleError("内部错误：缺少备份路径", status_code=500)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if backup_path.exists():
            shutil.rmtree(backup_path, ignore_errors=True)
        os.replace(live, backup_path)
        moved = True
    try:
        os.replace(stage_dir, live)
    except Exception as e:  # noqa: BLE001 - 换入失败必须还原旧版
        if moved and backup_path is not None and backup_path.exists():
            os.replace(backup_path, live)
        raise LifecycleError(f"换入新版本失败，已还原旧版：{e}", status_code=500) from e
    return {"backup": str(backup_path) if moved else "", "live": str(live)}


# ── 迁移：在 staging 上先跑 ─────────────────────────────────────────────────

def _rescan() -> None:
    from .host import extensions_base_dir
    from .loader import scan_extensions

    base = Path(runtime.extensions_dir or extensions_base_dir())
    runtime.extensions_dir = base
    runtime.installed = scan_extensions(base)


def migrate_stage(key: str, stage_dir: Path) -> dict:
    """在 staging 目录上执行迁移；失败即终止（live 目录仍是旧版）。"""
    from app.core.db import SessionLocal

    from .migrations import apply_for_key
    from .state import StateStore

    store = runtime.store or StateStore(base_dir() / ".state")
    runtime.store = store
    applied: dict = store.load("migrations", {}) or {}
    schema: dict = store.load("schema", {}) or {}
    db: Session = SessionLocal()
    try:
        result = apply_for_key(key, stage_dir, db, applied=applied, schema=schema)
    except Exception as e:  # noqa: BLE001 - 迁移失败按生命周期错误上报
        db.rollback()
        raise LifecycleError(f"迁移失败：{e}", status_code=500) from e
    finally:
        db.close()
    store.save("migrations", applied)
    store.save("schema", schema)
    return result


def _worker_flags(manifest: ExtensionManifest | None) -> dict:
    tasks = getattr(manifest, "tasks", {}) if manifest is not None else {}
    has_tasks = bool((tasks or {}).get("celery") or (tasks or {}).get("beat"))
    raw = str(os.environ.get("WEB_CONCURRENCY") or "").strip()
    multi = False
    if raw.isdigit() and int(raw) > 1:
        multi = True
    return {"worker_restart_required": has_tasks, "multi_worker": multi}


def _trash_target(key: str, reason: str = "uninstall") -> Path:
    root = trash_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return root / f"{key}-{reason}-{stamp}"


# ── 安装 / 更新 ─────────────────────────────────────────────────────────────

def install_or_update(
    app,
    package_bytes: bytes,
    app_key: str,
    *,
    actor: str = "",
    allow_downgrade: bool = False,
    product: str = PRODUCT,
) -> dict:
    """安装或更新扩展：preflight → stage → migrate → backup → swap → activate → health。"""
    from .host import hot_setup_extension, hot_teardown_extension

    started = datetime.now(timezone.utc)
    pre = preflight(package_bytes, app_key, product=product)
    installed = runtime.installed.get(app_key)
    previous_version = getattr(installed["manifest"], "version", "") if installed else ""
    previous_record = registry_info(app_key) or {}

    if installed:
        delta = compare_versions(pre.version, previous_version)
        if delta == 0:
            if previous_record.get("package_sha256") == pre.sha256:
                raise LifecycleError(f"{app_key} {pre.version} 已是最新版本", status_code=409)
            raise LifecycleError(
                f"{app_key} {pre.version} 已安装但包内容不同，拒绝覆盖（请提升版本号）",
                status_code=409,
            )
        if delta < 0 and not allow_downgrade:
            raise LifecycleError(
                f"不允许降级：已装 {previous_version}，待装 {pre.version}（需 allow_downgrade=true）",
                status_code=409,
            )

    action = "update" if installed else "install"
    with lifecycle_lock(app_key):
        stage_dir = stage(package_bytes, pre)
        moved: dict = {}
        try:
            migrate_stage(app_key, stage_dir)
            if installed:
                hot_teardown_extension(app, app_key, clear_override=False)
            moved = swap(
                app_key,
                stage_dir,
                backup_target(app_key, previous_version) if installed else None,
            )
        except Exception as e:
            if stage_dir.exists():
                shutil.rmtree(stage_dir, ignore_errors=True)
            if installed:
                _rescan()
                hot_setup_extension(app, app_key, migrate=False, force=True)
            update_registry(
                app_key,
                status="broken" if installed else "available",
                last_error=str(e),
                last_operation=action,
            )
            audit(action, app_key, from_version=previous_version, to_version=pre.version,
                  result="failed", error=str(e), actor=actor, sha256=pre.sha256)
            raise

        _rescan()
        result = hot_setup_extension(app, app_key, migrate=False, force=True)
        if not result.get("ok"):
            restored = _restore_previous(app, app_key, moved.get("backup", ""))
            update_registry(
                app_key,
                status="installed_enabled" if restored else "broken",
                last_error=str(result.get("error") or "健康检查失败"),
                last_operation=action,
            )
            audit(action, app_key, from_version=previous_version, to_version=pre.version,
                  result="rolled_back", error=str(result.get("error") or ""), actor=actor,
                  sha256=pre.sha256, restored=restored)
            raise LifecycleError(
                f"{app_key} {pre.version} 健康检查失败，已回滚到 {previous_version or '无'}："
                f"{result.get('error') or '未知原因'}",
                status_code=500,
                rollback=True,
            )

        manifest = pre.manifest
        record = update_registry(
            app_key,
            version=pre.version,
            schema_version=manifest.schema_version,
            manifest_version=manifest.manifest_version,
            min_core_version=manifest.min_core_version,
            installed_at=now_iso(),
            package_sha256=pre.sha256,
            previous_version=previous_version,
            status="installed_enabled",
            data_policy=str((manifest.data or {}).get("retention") or "keep"),
            data_tables=sorted(own_tables(manifest)),
            files=list((manifest.data or {}).get("files") or []),
            # 与 check_health 落盘的结论保持同源，不写死 "ok"
            health="ok" if (result.get("health") or {}).get("ok") else "error",
            last_error=None,
            last_operation=action,
            backup=moved.get("backup", ""),
            **_worker_flags(manifest),
        )
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        audit(
            action, app_key,
            from_version=previous_version, to_version=pre.version,
            result="ok", actor=actor, sha256=pre.sha256,
            elapsed_ms=elapsed_ms, backup=moved.get("backup", ""),
        )
        return {
            "ok": True,
            "action": action,
            "key": app_key,
            "from_version": previous_version,
            "to_version": pre.version,
            "sha256": pre.sha256,
            "health": result.get("health") or {},
            "routes": result.get("routes", 0),
            "permissions": result.get("permissions") or {},
            "tasks": result.get("tasks") or {},
            "backup": moved.get("backup", ""),
            "worker_restart_required": record.get("worker_restart_required", False),
            "multi_worker": record.get("multi_worker", False),
            "elapsed_ms": elapsed_ms,
        }


def _restore_previous(app, key: str, backup: str) -> bool:
    """回滚文件：live（新版）→ .trash，backup（旧版）→ live，并重新挂载。"""
    from .host import hot_setup_extension

    backup_path = Path(backup) if backup else None
    if not backup_path or not backup_path.is_dir():
        return False
    live = live_dir(key)
    trash = _trash_target(key, "failed")
    try:
        if live.exists():
            os.replace(live, trash)
        os.replace(backup_path, live)
    except OSError as e:
        logger.error("[extension] %s 回滚文件失败: %s", key, e)
        return False
    _rescan()
    result = hot_setup_extension(app, key, migrate=False, force=True)
    return bool(result.get("ok"))


# ── 卸载 / 彻底清除 ─────────────────────────────────────────────────────────

def _dependent_extensions(key: str) -> list[str]:
    dependents: list[str] = []
    for other_key, info in runtime.installed.items():
        if other_key == key:
            continue
        deps = getattr(info["manifest"], "dependencies", []) or []
        if any(str(d.get("key") or "") == key for d in deps if isinstance(d, dict)):
            dependents.append(other_key)
    return dependents


def _newest_trash(key: str) -> Path | None:
    root = trash_root()
    if not root.is_dir():
        return None
    items = sorted(
        [p for p in root.iterdir() if p.is_dir() and p.name.startswith(f"{key}-")],
        key=lambda p: p.name,
    )
    return items[-1] if items else None


def purge_data(key: str, manifest: ExtensionManifest | None, ext_path: Path | None = None) -> dict:
    """彻底清除：先导出 own 表 JSONL，再按逆序 DROP，最后删 data/<key>。"""
    from app.core.db import SessionLocal

    tables = own_tables(manifest, ext_path) if manifest is not None else set(
        registry_info(key).get("data_tables") or []
    )
    deny = core_table_names() | other_extension_tables(key)
    targets = sorted(t for t in tables if t not in deny)
    skipped = sorted(tables & deny)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    export_dir = data_root() / ".purge_backups" / f"{key}-{stamp}"
    exported: list[str] = []
    db: Session = SessionLocal()
    try:
        existing = set(inspect(db.get_bind()).get_table_names())
        for table in targets:
            if table not in existing:
                continue
            export_dir.mkdir(parents=True, exist_ok=True)
            rows = db.execute(text(f"SELECT * FROM {table}")).mappings().all()
            with (export_dir / f"{table}.jsonl").open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(dict(row), ensure_ascii=False, default=str) + "\n")
            exported.append(table)
        for table in reversed(targets):
            if table in existing:
                db.execute(text(f"DROP TABLE IF EXISTS {table}"))
        db.commit()
    except Exception as e:  # noqa: BLE001 - 导出/删除失败必须终止（数据不可逆）
        db.rollback()
        raise LifecycleError(f"彻底清除失败（数据表已保留）：{e}", status_code=500) from e
    finally:
        db.close()
    removed_files: list[str] = []
    candidates = {data_root() / key}
    for raw in ((manifest.data or {}).get("files") if manifest is not None else []) or []:
        path = (base_dir() / str(raw)).resolve()
        if base_dir().resolve() in path.parents:
            candidates.add(path)
    for path in candidates:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            removed_files.append(str(path))
    return {
        "tables": exported,
        "skipped": skipped,
        "files": removed_files,
        "export_dir": str(export_dir) if exported else "",
    }


def uninstall(
    app,
    key: str,
    *,
    purge: bool = False,
    confirm_key: str | None = None,
    actor: str = "",
) -> dict:
    """卸载：停门禁 → 排空 → 摘路由/事件/任务/权限/模块 → 目录入 trash。"""
    import time

    from .host import hot_teardown_extension

    installed = runtime.installed.get(key)
    record = registry_info(key)
    if not installed and not record:
        raise LifecycleError(f"扩展 {key} 未安装", status_code=404)
    if purge and confirm_key != key:
        raise LifecycleError("彻底清除需要 confirm_key 与扩展 key 一致", status_code=400)
    dependents = _dependent_extensions(key)
    if dependents:
        raise LifecycleError(f"以下扩展依赖 {key}，请先卸载：{', '.join(dependents)}", status_code=409)

    manifest = installed["manifest"] if installed else None
    version = getattr(manifest, "version", "") or str(record.get("version") or "")
    data_result: dict = {}
    trash_path = ""
    with lifecycle_lock(key):
        runtime.retiring.add(key)
        try:
            if DRAIN_SECONDS > 0:
                time.sleep(DRAIN_SECONDS)
            teardown = hot_teardown_extension(app, key, purge_permissions=True, clear_override=True)
            live = live_dir(key)
            if live.exists():
                trash_path = str(_trash_target(key))
                os.replace(live, trash_path)
            runtime.installed.pop(key, None)
            if purge:
                data_result = purge_data(key, manifest, Path(trash_path) if trash_path else None)
        finally:
            runtime.retiring.discard(key)
        if purge:
            drop_registry(key)
            audit("purge", key, version=version, actor=actor, result="ok", **data_result)
        else:
            update_registry(
                key,
                status="uninstalled_keep",
                uninstalled_at=now_iso(),
                trash=trash_path,
                last_operation="uninstall",
            )
            audit("uninstall", key, version=version, actor=actor, result="ok",
                  policy="keep", trash=trash_path)
    return {
        "ok": True,
        "key": key,
        "policy": "purge" if purge else "keep",
        "version": version,
        "trash": trash_path,
        "teardown": teardown,
        "data": data_result,
        "message": "已彻底清除（含数据）" if purge else "已卸载，数据与权限记录保留，可重装恢复",
    }


# ── 回滚 / 修复 / 启停 ──────────────────────────────────────────────────────

def rollback(app, key: str, *, actor: str = "") -> dict:
    """回滚到最近备份版本；旧版不兼容新 schema 时标记 rollback_blocked。"""
    from .host import hot_setup_extension, hot_teardown_extension

    backup = latest_backup(key)
    if backup is None:
        raise LifecycleError(f"扩展 {key} 没有可用备份", status_code=404)
    current_version = getattr((runtime.installed.get(key) or {}).get("manifest"), "version", "")
    with lifecycle_lock(key):
        hot_teardown_extension(app, key, clear_override=False)
        live = live_dir(key)
        parked = _trash_target(key, "pre-rollback")
        if live.exists():
            os.replace(live, parked)
        os.replace(backup, live)
        _rescan()
        result = hot_setup_extension(app, key, migrate=False, force=True)
        if not result.get("ok"):
            # 旧版跑不起来：还原新版本，标记 rollback_blocked（不强行降级）
            if live.exists():
                os.replace(live, backup)
            if parked.exists():
                os.replace(parked, live)
            _rescan()
            hot_setup_extension(app, key, migrate=False, force=True)
            update_registry(key, status="rollback_blocked", last_error=str(result.get("error") or ""))
            audit("rollback", key, result="blocked", error=str(result.get("error") or ""), actor=actor)
            raise LifecycleError(
                f"回滚失败：旧版与当前数据结构不兼容，已保持在新版本（rollback_blocked）",
                status_code=409,
            )
        new_version = getattr((runtime.installed.get(key) or {}).get("manifest"), "version", "")
        update_registry(
            key,
            version=new_version,
            previous_version=current_version,
            status="installed_enabled",
            health="ok" if (result.get("health") or {}).get("ok") else "error",
            last_error=None,
            last_operation="rollback",
        )
        audit("rollback", key, from_version=current_version, to_version=new_version,
              result="ok", actor=actor)
    return {"ok": True, "key": key, "from_version": current_version, "to_version": new_version}


def repair(app, key: str, *, actor: str = "") -> dict:
    """修复：目录丢失从备份/trash 还原 → 补迁移 → 补权限 → 重新挂载 → 健康检查。"""
    from .host import hot_setup_extension

    record = registry_info(key)
    if not runtime.installed.get(key) and not record:
        raise LifecycleError(f"未找到扩展 {key} 的安装记录", status_code=404)
    restored_from = ""
    with lifecycle_lock(key):
        if not runtime.installed.get(key):
            source = latest_backup(key) or _newest_trash(key)
            if source is None:
                raise LifecycleError(f"扩展 {key} 目录缺失且没有可用备份，请重新安装", status_code=409)
            target = live_dir(key)
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            os.replace(source, target)
            restored_from = str(source)
            _rescan()
        result = hot_setup_extension(app, key, force=True)
        if not result.get("ok"):
            update_registry(key, status="broken", last_operation="repair",
                            last_error=str(result.get("error") or ""))
            audit("repair", key, result="failed", error=str(result.get("error") or ""),
                  actor=actor, restored_from=restored_from)
            raise LifecycleError(f"修复失败：{result.get('error') or '健康检查未通过'}", status_code=500)
        update_registry(key, status="installed_enabled",
                        health="ok" if (result.get("health") or {}).get("ok") else "error",
                        last_error=None, last_operation="repair")
        audit("repair", key, result="ok", actor=actor, restored_from=restored_from)
    return {"ok": True, "key": key, "restored_from": restored_from, "health": result.get("health") or {}}


def set_enabled(app, key: str, enabled: bool, *, actor: str = "") -> dict:
    from .host import set_extension_enabled

    if key not in runtime.installed:
        raise LifecycleError(f"扩展 {key} 未安装", status_code=404)
    result = set_extension_enabled(app, key, enabled)
    update_registry(
        key,
        status="installed_enabled" if enabled else "installed_disabled",
        last_operation="enable" if enabled else "disable",
    )
    audit("enable" if enabled else "disable", key,
          result="ok" if result.get("ok") else "failed", actor=actor,
          error=str(result.get("error") or ""))
    return result


def lifecycle_logs(limit: int = 100, key: str | None = None) -> list[dict]:
    return read_audit(limit=limit, key=key)
