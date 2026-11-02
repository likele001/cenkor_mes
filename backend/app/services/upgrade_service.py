# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""后台在线升级 / 回滚服务。

设计要点：
- 所有重活放在守护线程里跑，HTTP 请求只负责建任务和下指令；
- 每一步都写文件日志（backend/data/upgrade_logs/{job_id}.log）并回写 DB 的 stage，
  前端靠轮询任务表 + 读日志展示进度；
- 数据库备份失败立即中止，绝不带病继续；
- 重启分两种模式：配置了 CENKORMES_RESTART_CMD 则执行该命令；未配置则「杀掉
  8500 监听进程，由宝塔面板的项目守护进程在约 60s 内拉起」；
- 重启会杀掉本进程，因此重启 + 健康校验交给一份独立会话的守护脚本执行，结果落盘
  到 /tmp/cenkormes-upgrade-restart-{job}.json，下次访问任务接口或服务启动时由
  reconcile_restarts() 回写最终状态，任务不会永远停在 running。
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.upgrade_job import UpgradeJob

ROOT = Path(__file__).resolve().parents[3]           # /www/wwwroot/cenkormes
VERSION_FILE = ROOT / "VERSION"
BACKUP_DIR = ROOT / "backend/data/backups"
LOG_DIR = ROOT / "backend/data/upgrade_logs"
LOCK_FILE = Path("/tmp/cenkormes-upgrade.lock")
RESTART_CMD = os.environ.get("CENKORMES_RESTART_CMD", "")

BACKEND_DIR = ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env"
HEALTH_URL = os.environ.get("CENKORMES_HEALTH_URL", "http://127.0.0.1:8500/api/health")
BACKEND_PORT = urlsplit(HEALTH_URL).port or 8500
# 杀进程后要等面板守护进程（约 60s 一轮）拉起，再留出应用启动时间
VERIFY_TIMEOUT = 180
RESTART_RESULT_DIR = Path("/tmp")

VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
ACTIVE_STATUSES = ("pending", "running")
# nginx 直接服务 dist，代码升级后必须重建；只重建源码有改动的应用
FRONTEND_APPS = (("frontend-admin-pro", "管理后台"), ("frontend-h5", "H5"))


# ── 基础工具 ──────────────────────────────────────────────────────────


def read_local_version() -> str:
    """读 VERSION 文件；任何异常都返回 "unknown"。"""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "unknown"
    except (OSError, UnicodeDecodeError):
        return "unknown"


def _run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 600, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _tag_key(tag: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in tag.lstrip("v").split("."))
    except ValueError:
        return (0, 0, 0)


def list_remote_tags() -> list[str]:
    """git ls-remote --tags origin，过滤 ^{} 解引用行，按语义版本升序返回。"""
    res = _run_cmd(["git", "-C", str(ROOT), "ls-remote", "--tags", "origin"], timeout=60)
    if res.returncode != 0:
        raise RuntimeError(f"git ls-remote 失败：{(res.stderr or res.stdout).strip()[:300]}")
    tags: list[str] = []
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        ref = parts[1].strip()
        if not ref.startswith("refs/tags/") or ref.endswith("^{}"):
            continue
        name = ref[len("refs/tags/"):]
        if VERSION_RE.match(name):
            tags.append(name)
    return sorted(set(tags), key=_tag_key)


def _disk_free_gb() -> float | None:
    try:
        usage = os.statvfs(str(ROOT))
        return round(usage.f_bavail * usage.f_frsize / (1024 ** 3), 2)
    except OSError:
        return None


def working_tree_dirty() -> bool:
    """tracked 文件是否有未提交改动（新日志/备份/构建产物均为 untracked，不阻塞升级）。"""
    res = _run_cmd(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
        timeout=30,
    )
    if res.returncode != 0:
        raise RuntimeError(f"git status 失败：{(res.stderr or res.stdout).strip()[:300]}")
    return bool(res.stdout.strip())


def _assert_clean_tree(action: str) -> None:
    """回滚用 checkout -f，会丢弃本地改动；升级 checkout 也可能把改动带进新版本。"""
    if working_tree_dirty():
        raise RuntimeError(f"工作区有未提交改动，不能{action}；请先提交或 stash 后再试")


def check_update() -> dict:
    """当前版本 / 远端最新版本 / 是否可更新 / 重启命令是否配置 / 磁盘余量。"""
    current = read_local_version()
    tags = list_remote_tags()          # 远端不可达时抛 RuntimeError，由路由转 400
    latest = tags[-1] if tags else current
    if tags and VERSION_RE.match(current):
        has_update = _tag_key(latest) > _tag_key(current)
    else:
        has_update = bool(tags) and latest != current
    try:
        dirty = working_tree_dirty()
    except RuntimeError:
        dirty = False
    return {
        "current": current,
        "latest": latest,
        "has_update": has_update,
        # 两种模式都能自动重启：自定义命令 / 杀进程后由面板守护进程拉起
        "restart_configured": True,
        "restart_mode": "cmd" if RESTART_CMD.strip() else "guard",
        "disk_free_gb": _disk_free_gb(),
        "working_tree_dirty": dirty,
    }


def _venv_python() -> Path:
    """项目 python 解释器。

    优先当前进程的 sys.executable —— 生产是宝塔托管环境
    /www/server/pyporject_evn/cenkormes/bin/python3.13，与本进程一致才不会把依赖
    装进 backend/venv 这种「僵尸虚拟环境」。其次退回 backend/.venv、backend/venv。
    """
    import sys

    for candidate in (Path(sys.executable), BACKEND_DIR / ".venv/bin/python", BACKEND_DIR / "venv/bin/python"):
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def _read_db_url() -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("DB_URL="):
            value = line.split("=", 1)[1].strip()
            return value.strip('"').strip("'")
    return ""


def _parse_db_url(url: str) -> dict:
    """mysql+pymysql://user:pass@host:port/db?charset → 连接参数。"""
    if "://" not in url:
        raise RuntimeError("DB_URL 格式不合法")
    u = urlsplit(url)
    if not u.hostname or not u.path.lstrip("/"):
        raise RuntimeError("DB_URL 缺少 host 或库名")
    return {
        "user": u.username or "root",
        "password": u.password or "",
        "host": u.hostname,
        "port": str(u.port or 3306),
        "db": u.path.lstrip("/"),
    }


# ── 日志 / 状态 ──────────────────────────────────────────────────────


def _log_path(job_id: int) -> Path:
    return LOG_DIR / f"{job_id}.log"


def _log(job_id: int, msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(_log_path(job_id), "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except OSError:
        pass


def log_note(job_id: int, msg: str) -> None:
    """给路由层写一条附加日志（如 skip_frontend 取值）。"""
    _log(job_id, msg)


def read_log(job_id: int, offset: int = 0, limit: int = 2000) -> str:
    """返回日志文本切片；offset/limit 均为字符数。"""
    path = _log_path(job_id)
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="ignore")
    start = max(0, int(offset))
    return content[start:start + max(1, int(limit))]


def _set(db, job: UpgradeJob, *, status: str | None = None, stage: str | None = None) -> None:
    if status:
        job.status = status
    if stage:
        job.stage = stage
    db.add(job)
    db.commit()


# ── 锁 ───────────────────────────────────────────────────────────────


def _acquire_lock() -> int:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        return fd
    except FileExistsError:
        # 崩溃残留锁：超过 3 小时视为过期，清掉重试一次
        try:
            if time.time() - LOCK_FILE.stat().st_mtime > 3 * 3600:
                LOCK_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            return fd
        except FileExistsError:
            raise RuntimeError("已有升级任务正在执行（/tmp/cenkormes-upgrade.lock 存在）")


def _release_lock(fd: int | None) -> None:
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


# ── 建任务 ───────────────────────────────────────────────────────────


def _current_git_ref() -> str | None:
    res = _run_cmd(["git", "-C", str(ROOT), "rev-parse", "HEAD"], timeout=30)
    return res.stdout.strip() if res.returncode == 0 else None


def _current_alembic_rev(db) -> str | None:
    try:
        from sqlalchemy import text

        row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
        return row[0] if row else None
    except Exception:  # 表不存在 / 无权限都不该阻断建任务
        return None


def create_job(db, action: str, to_version: str, operator_id: int | None = None) -> UpgradeJob:
    action = (action or "").strip()
    if action not in ("upgrade", "rollback"):
        raise ValueError("action 只能是 upgrade 或 rollback")
    to_version = (to_version or "").strip()
    if not VERSION_RE.match(to_version):
        raise ValueError("版本号格式不合法，应形如 v2.2.1")
    if working_tree_dirty():
        raise ValueError("工作区有未提交改动，请先提交或 stash 后再升级")

    active = db.execute(
        select(UpgradeJob).where(UpgradeJob.status.in_(ACTIVE_STATUSES))
    ).scalars().first()
    if active is not None:
        raise ValueError(f"已有进行中的任务 #{active.id}（{active.status}），请等待其结束")

    job = UpgradeJob(
        action=action,
        from_version=read_local_version(),
        to_version=to_version,
        status="pending",
        stage="backup" if action == "upgrade" else "checkout",
        from_ref=_current_git_ref(),
        alembic_rev=_current_alembic_rev(db),
        operator_id=operator_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job.log_path = str(_log_path(job.id))
    db.add(job)
    db.commit()
    db.refresh(job)
    _log(job.id, f"任务创建：{action} {job.from_version} -> {to_version}，from_ref={job.from_ref or '-'}")
    return job


# ── 执行入口 ─────────────────────────────────────────────────────────


def run_job(job_id: int, restore_db: bool = False, skip_frontend: bool = False) -> threading.Thread:
    """守护线程执行任务；进程退出即中断（需要真重启时由 awaiting_restart 兜住）。"""
    t = threading.Thread(target=_execute, args=(job_id, restore_db, skip_frontend), daemon=True)
    t.start()
    return t


def _execute(job_id: int, restore_db: bool, skip_frontend: bool = False) -> None:
    db = SessionLocal()
    fd = None
    try:
        fd = _acquire_lock()
        job = db.get(UpgradeJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = datetime.now()
        db.commit()
        _log(job_id, "开始执行")
        if job.action == "rollback":
            _do_rollback(db, job, restore_db, skip_frontend)
        else:
            _do_upgrade(db, job, skip_frontend)
    except Exception as exc:  # 任何未捕获异常都要落到 failed，不能静默
        _log(job_id, f"执行中断：{exc}")
        try:
            job = db.get(UpgradeJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:2000]
                job.finished_at = datetime.now()
                db.commit()
        except Exception:
            db.rollback()
    finally:
        _release_lock(fd)
        db.close()


def _changed_frontend_apps(from_ref: str | None, to_ref: str | None) -> list[str]:
    """两个 git ref 之间源码有改动的前端应用；ref 缺失时保守全量重建。"""
    names = [name for name, _ in FRONTEND_APPS]
    if not from_ref or not to_ref:
        return names
    res = _run_cmd(
        ["git", "-C", str(ROOT), "diff", "--name-only", f"{from_ref}..{to_ref}", "--", *names],
        timeout=120,
    )
    if res.returncode != 0:
        raise RuntimeError(f"比较前端源码改动失败：{(res.stderr or res.stdout).strip()[:300]}")
    touched = {line.split("/", 1)[0] for line in res.stdout.splitlines() if line.strip()}
    return [name for name in names if name in touched]


def _npm_bin() -> str:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("未找到 npm，无法重建前端；可勾选「跳过前端构建」后重试")
    return npm


def _build_frontend(app: str, job_id: int) -> Path:
    """构建到临时目录，不碰线上 dist；返回临时产物目录。"""
    app_dir = ROOT / app
    if not (app_dir / "package.json").exists():
        raise RuntimeError(f"{app} 缺少 package.json，无法构建")
    npm = _npm_bin()
    out_name = f".dist-build-{job_id}"
    out_dir = app_dir / out_name
    shutil.rmtree(out_dir, ignore_errors=True)
    if not (app_dir / "node_modules").exists():
        _log(job_id, f"{app}: node_modules 不存在，执行 npm ci")
        res = _run_cmd([npm, "ci", "--no-audit", "--no-fund"], cwd=app_dir, timeout=1800)
        _log(job_id, (res.stdout or "")[-1500:])
        if res.returncode != 0:
            raise RuntimeError(f"{app} 依赖安装失败：{(res.stderr or res.stdout).strip()[:500]}")
    _log(job_id, f"{app}: npm run build -- --outDir {out_name}")
    res = _run_cmd([npm, "run", "build", "--", "--outDir", out_name], cwd=app_dir, timeout=1800)
    _log(job_id, (res.stdout or "")[-3000:])
    if res.returncode != 0 or not (out_dir / "index.html").exists():
        shutil.rmtree(out_dir, ignore_errors=True)
        raise RuntimeError(f"{app} 构建失败：{(res.stderr or res.stdout).strip()[:500]}")
    return out_dir


def _promote_frontend(app: str, out_dir: Path, job_id: int) -> None:
    """原子换入：线上 dist 改名为 dist.__bak，临时产物改名为 dist。"""
    live = ROOT / app / "dist"
    backup = ROOT / app / "dist.__bak"
    shutil.rmtree(backup, ignore_errors=True)
    if live.exists():
        live.rename(backup)
    out_dir.rename(live)
    _log(job_id, f"{app}: 前端产物已换入 dist（旧版备份 dist.__bak）")


def _prepare_frontends(
    job: UpgradeJob,
    from_ref: str | None,
    to_ref: str | None,
    *,
    skip: bool,
    strict: bool,
) -> list[tuple[str, Path]]:
    """构建受影响的前端到临时目录。

    strict=False 时构建失败只告警并返回空列表（回滚场景：优先恢复代码，
    线上 dist 保持原样总比停在半途好）。
    """
    if skip:
        _log(job.id, "已跳过前端构建（skip_frontend）")
        return []
    apps = _changed_frontend_apps(from_ref, to_ref)
    if not apps:
        _log(job.id, "前端源码无改动，跳过构建")
        return []
    _log(job.id, "需要重建的前端：" + "、".join(apps))
    built: list[tuple[str, Path]] = []
    for app in apps:
        try:
            built.append((app, _build_frontend(app, job.id)))
        except Exception as exc:  # noqa: BLE001 - 清理临时产物后按 strict 决定是否中止
            for _, tmp in built:
                shutil.rmtree(tmp, ignore_errors=True)
            if strict:
                raise
            _log(job.id, f"[警告] {exc}；继续执行，线上 dist 保持原样")
            return []
    return built


def _promote_frontends(built: list[tuple[str, Path]], job_id: int, *, strict: bool) -> None:
    for app, out_dir in built:
        try:
            _promote_frontend(app, out_dir, job_id)
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(out_dir, ignore_errors=True)
            if strict:
                raise
            _log(job_id, f"[警告] {app} 产物换入失败：{exc}")


def _do_upgrade(db, job: UpgradeJob, skip_frontend: bool = False) -> None:
    jid = job.id

    # 1) 数据库备份：失败立即中止
    _set(db, job, stage="backup", status="running")
    _log(jid, "步骤 1/8 备份数据库")
    backup = _backup_database(job)
    job.backup_path = str(backup)
    db.commit()
    _log(jid, f"备份完成：{backup}")

    # 2) fetch
    _set(db, job, stage="fetch")
    _log(jid, "步骤 2/8 git fetch --tags")
    res = _run_cmd(["git", "-C", str(ROOT), "fetch", "--tags"], timeout=300)
    if res.returncode != 0:
        raise RuntimeError(f"git fetch 失败：{(res.stderr or '').strip()[:500]}")
    _log(jid, "fetch 完成")

    # 3) checkout
    if not job.from_ref:
        job.from_ref = _current_git_ref()
        db.commit()
    _assert_clean_tree("升级")
    _set(db, job, stage="checkout")
    _log(jid, f"步骤 3/8 git checkout {job.to_version}（回滚点 {job.from_ref}）")
    res = _run_cmd(["git", "-C", str(ROOT), "checkout", job.to_version], timeout=300)
    if res.returncode != 0:
        raise RuntimeError(
            f"git checkout {job.to_version} 失败：{(res.stderr or res.stdout).strip()[:500]}"
        )
    _log(jid, "checkout 完成，VERSION=" + read_local_version())

    # 4) 依赖：失败跳过但记警告
    _set(db, job, stage="deps")
    _log(jid, "步骤 4/8 安装依赖 backend/requirements.txt")
    py = _venv_python()
    res = _run_cmd([str(py), "-m", "pip", "install", "-r", str(BACKEND_DIR / "requirements.txt")], timeout=1800)
    _log(jid, (res.stdout or "")[-3000:])
    if res.returncode != 0:
        _log(jid, f"[警告] 依赖安装失败，已跳过：{(res.stderr or '').strip()[:500]}")
    else:
        _log(jid, "依赖安装完成")

    # 5) 前端：先构建到临时目录；失败则中止（dist 与数据库都保持原样）
    _set(db, job, stage="build")
    _log(jid, "步骤 5/8 构建前端（仅源码有改动的应用）")
    built = _prepare_frontends(
        job, job.from_ref, job.to_version, skip=skip_frontend, strict=True
    )

    try:
        # 6) 迁移
        _set(db, job, stage="migrate")
        _log(jid, "步骤 6/8 alembic upgrade head")
        res = _run_cmd(
            [str(py), "-c", "from alembic.config import main; main(['upgrade', 'head'])"],
            cwd=BACKEND_DIR,
            timeout=900,
        )
        if res.returncode != 0:
            raise RuntimeError(f"数据库迁移失败：{(res.stderr or res.stdout).strip()[:500]}")
        _log(jid, "迁移完成")

        # 7) 换入前端产物（迁移失败时临时目录会被清掉，线上 dist 不动）
        if built:
            _log(jid, "步骤 7/8 换入前端产物")
            _promote_frontends(built, jid, strict=True)
    except Exception:
        for _, tmp in built:
            shutil.rmtree(tmp, ignore_errors=True)
        raise

    # 8) 重启：交给重启守护脚本（它会杀掉本进程），后续状态由 reconcile_restarts() 收尾
    _set(db, job, stage="restart")
    _log(jid, "步骤 8/8 重启后端")
    if not _spawn_restart_guard(jid, job.to_version):
        _log(jid, "重启脚本启动失败，停在 awaiting_restart，请手动重启后端后点「健康校验」")
        _set(db, job, status="awaiting_restart", stage="restart")
        return
    _log(jid, "由守护脚本做健康校验；本进程即将退出，任务最终状态约 60~180s 后回写")
    db.commit()


def _do_rollback(db, job: UpgradeJob, restore_db: bool, skip_frontend: bool = False) -> None:
    jid = job.id
    ref = job.from_ref
    if not ref:
        raise RuntimeError("该任务未记录回滚点 from_ref，无法回滚")

    _assert_clean_tree("回滚")
    _set(db, job, stage="checkout", status="running")
    current_ref = _current_git_ref()
    _log(jid, f"git checkout -f {ref}")
    res = _run_cmd(["git", "-C", str(ROOT), "checkout", "-f", ref], timeout=300)
    if res.returncode != 0:
        raise RuntimeError(f"git checkout -f 失败：{(res.stderr or res.stdout).strip()[:500]}")
    _log(jid, "代码已回滚，VERSION=" + read_local_version())

    # 回滚同样要重建前端；失败只告警，优先保证代码恢复
    _set(db, job, stage="build")
    built = _prepare_frontends(job, ref, current_ref, skip=skip_frontend, strict=False)

    if restore_db:
        if not job.backup_path:
            raise RuntimeError("未找到数据库备份文件，无法恢复数据")
        _set(db, job, stage="migrate")
        _log(jid, f"恢复数据库：{job.backup_path}")
        _restore_database(job)
        _log(jid, "数据库恢复完成")

    if built:
        _promote_frontends(built, jid, strict=False)

    _set(db, job, stage="restart")
    if not _spawn_restart_guard(jid, job.to_version):
        _log(jid, "重启脚本启动失败，请手动重启后端后点「健康校验」")
        job.status = "rolled_back"
        db.commit()
        return
    _log(jid, "代码与数据已回滚，由守护脚本重启并校验；最终状态约 60~180s 后回写")
    db.commit()


# ── 备份 / 恢复 / 重启 / 校验 ────────────────────────────────────────


def _backup_database(job: UpgradeJob) -> Path:
    url = _read_db_url()
    if not url:
        raise RuntimeError("backend/.env 未配置 DB_URL，无法备份数据库")
    conn = _parse_db_url(url)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"{ts}_{job.from_version}.sql.gz"
    env = os.environ.copy()
    env["MYSQL_PWD"] = conn["password"]
    cmd = (
        "set -o pipefail; mysqldump --single-transaction --routines --default-character-set=utf8mb4 "
        f"-h {shlex.quote(conn['host'])} -P {shlex.quote(conn['port'])} "
        f"-u {shlex.quote(conn['user'])} {shlex.quote(conn['db'])} | gzip -c > {shlex.quote(str(path))}"
    )
    res = subprocess.run(["bash", "-c", cmd], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=3600)
    if res.returncode != 0 or not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"mysqldump 备份失败：{(res.stderr or '').strip()[:500]}")
    return path


def _restore_database(job: UpgradeJob) -> None:
    url = _read_db_url()
    if not url:
        raise RuntimeError("backend/.env 未配置 DB_URL，无法恢复数据库")
    conn = _parse_db_url(url)
    path = Path(job.backup_path or "")
    if not path.exists():
        raise RuntimeError(f"备份文件不存在：{path}")
    env = os.environ.copy()
    env["MYSQL_PWD"] = conn["password"]
    cmd = (
        "set -o pipefail; gunzip -c "
        f"{shlex.quote(str(path))} | mysql -h {shlex.quote(conn['host'])} "
        f"-P {shlex.quote(conn['port'])} -u {shlex.quote(conn['user'])} {shlex.quote(conn['db'])}"
    )
    res = subprocess.run(["bash", "-c", cmd], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=3600)
    if res.returncode != 0:
        raise RuntimeError(f"数据库恢复失败：{(res.stderr or '').strip()[:500]}")


def _restart_result_path(job_id: int) -> Path:
    return RESTART_RESULT_DIR / f"cenkormes-upgrade-restart-{job_id}.json"


def _listener_pid(port: int = BACKEND_PORT) -> int | None:
    """监听指定端口的进程 pid。本服务以 www 用户运行，能看自己的进程即可。"""
    try:
        out = subprocess.run(["ss", "-lntpH"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        if f":{port} " not in line:
            continue
        m = re.search(r"pid=(\d+)", line)
        if m:
            return int(m.group(1))
    return None


def _build_restart_script(job_id: int, target_version: str, pid: int | None, py: Path, custom: str) -> str:
    """生成重启守护脚本正文（独立会话执行，负责杀进程/重启/校验/落盘）。"""
    log = _log_path(job_id)
    result = _restart_result_path(job_id)
    custom_path = LOG_DIR / f"restart_custom_{job_id}.sh"
    return f"""#!/bin/bash
JOB={job_id}
TARGET='{target_version}'
LOG='{log}'
RESULT='{result}'
PORT='{BACKEND_PORT}'
PID='{pid or ""}'
PY='{py}'
CUSTOM='{custom_path if custom else ""}'
export H='{HEALTH_URL}'
ts() {{ date '+%Y-%m-%d %H:%M:%S'; }}
say() {{ echo "[$(ts)] $*" >> "$LOG"; }}

say "重启守护脚本启动：旧 pid=${{PID:-无}}，目标版本 $TARGET"
rm -f '{LOCK_FILE}'
sleep 2

for u in cenkormes-celery cenkormes-beat; do
  if sudo -n systemctl restart "$u" >/dev/null 2>&1; then
    say "已重启 $u"
  else
    say "[警告] $u 未能自动重启（需给 www 用户 sudo 白名单），请手动执行 systemctl restart $u"
  fi
done

if [ -n "$CUSTOM" ]; then
  say "执行自定义重启命令：$CUSTOM"
  bash "$CUSTOM" >> "$LOG" 2>&1 || say "[警告] 自定义重启命令返回非 0"
  sleep 3
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    say "旧进程仍在，兜底 kill -TERM $PID"
    kill -TERM "$PID" >/dev/null 2>&1 || true
  fi
elif [ -n "$PID" ]; then
  say "kill -TERM $PID（等面板项目守护进程拉起新进程）"
  kill -TERM "$PID" >/dev/null 2>&1 || true
  for i in $(seq 1 20); do
    ss -lnt 2>/dev/null | grep -q ":$PORT " || break
    sleep 1
  done
  if ss -lnt 2>/dev/null | grep -q ":$PORT "; then
    say "[警告] 20s 内端口未释放，kill -9 $PID"
    kill -9 "$PID" >/dev/null 2>&1 || true
    sleep 3
  fi
else
  say "端口 $PORT 未监听，交由面板守护进程拉起"
fi

OK=0
ACTUAL=''
for i in $(seq 1 60); do
  ACTUAL=$("$PY" -c 'import json,os,urllib.request;d=json.load(urllib.request.urlopen(os.environ["H"],timeout=5));print((d.get("data") or dict()).get("version") or "")' 2>/dev/null)
  if [ "$ACTUAL" = "$TARGET" ]; then OK=1; break; fi
  sleep 3
done

if [ "$OK" = "1" ]; then
  say "健康校验通过，当前版本 $ACTUAL"
else
  say "健康校验未通过：期望 $TARGET，实际 ${{ACTUAL:-无响应}}"
fi
{{
  echo "ok=$OK"
  echo "version=$ACTUAL"
  echo "finished_at=$(ts)"
}} > "$RESULT"
"""


def _spawn_restart_guard(job_id: int, target_version: str) -> bool:
    """写并启动重启守护脚本（独立会话，不会被本进程退出牵连）。

    脚本负责：清理升级锁 → 重启 celery → 执行自定义重启命令或杀掉旧后端（交给
    宝塔面板「项目守护进程」拉起）→ 轮询 /api/health 直到版本匹配 → 结果落盘。
    因为重启必然杀掉本进程，任务最终状态由 reconcile_restarts() 依据结果文件回写。
    """
    pid = _listener_pid()
    py = _venv_python()
    log = _log_path(job_id)
    result = _restart_result_path(job_id)
    script = LOG_DIR / f"restart_{job_id}.sh"
    custom = RESTART_CMD.strip()
    custom_path = LOG_DIR / f"restart_custom_{job_id}.sh"

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        result.unlink(missing_ok=True)
        if custom:
            custom_path.write_text(custom + "\n", encoding="utf-8")
    except OSError as exc:
        _log(job_id, f"准备重启脚本失败：{exc}")
        return False

    body = _build_restart_script(job_id, target_version, pid, py, custom)

    try:
        script.write_text(body, encoding="utf-8")
        script.chmod(0o755)
    except OSError as exc:
        _log(job_id, f"写入重启脚本失败：{exc}")
        return False

    _log(
        job_id,
        f"启动重启守护脚本 {script}（{'自定义命令' if custom else '杀进程 + 面板守护拉起'}模式）",
    )
    try:
        with open(log, "a", encoding="utf-8") as out:
            # 独立会话：本进程被 kill 后，子进程仍继续执行重启与校验
            subprocess.Popen(
                ["bash", str(script)],
                cwd=str(ROOT),
                stdout=out,
                stderr=out,
                start_new_session=True,
                close_fds=True,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        _log(job_id, f"启动重启脚本失败：{exc}")
        return False
    return True


def _read_restart_result(path: Path) -> dict[str, str] | None:
    """读取守护脚本结果；finished_at 未出现说明脚本还没跑完。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if "finished_at=" not in text:
        return None
    data: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def reconcile_restarts(db) -> None:
    """把重启守护脚本落盘的结果回写到任务表。

    重启会杀掉本进程，执行线程随之消失，任务会停在 running/restart；
    服务恢复后由任务接口（或启动钩子）调用本函数收尾。幂等，可反复调用。
    """
    rows = db.execute(
        select(UpgradeJob).where(UpgradeJob.status == "running", UpgradeJob.stage == "restart")
    ).scalars().all()
    for job in rows:
        data = _read_restart_result(_restart_result_path(job.id))
        if data is None:
            # 重启阶段最多几分钟；超过 15 分钟仍无结果，视为守护脚本异常，置失败解锁
            started = job.started_at
            if started and (datetime.now() - started).total_seconds() > 900:
                job.status = "failed"
                job.stage = "done"
                job.error = "重启阶段超时（未收到守护脚本结果），请检查后端是否已启动，必要时执行回滚"
                job.finished_at = datetime.now()
                _log(job.id, job.error)
                db.add(job)
                db.commit()
                try:
                    LOCK_FILE.unlink(missing_ok=True)
                except OSError:
                    pass
            continue
        actual = data.get("version") or None
        if data.get("ok") == "1":
            job.status = "rolled_back" if job.action == "rollback" else "success"
            job.stage = "done"
            job.error = None
            _log(job.id, f"守护脚本回报：健康校验通过，当前版本 {actual}")
        else:
            job.status = "failed"
            job.stage = "done"
            job.error = (
                f"重启后健康校验失败：期望 {job.to_version}，实际 {actual or '无响应'}；"
                f"请查看升级日志，必要时执行回滚"
            )
            _log(job.id, job.error)
        job.finished_at = datetime.now()
        db.add(job)
        db.commit()
        try:
            LOCK_FILE.unlink(missing_ok=True)  # 旧进程已被替换，残留锁一并清掉
        except OSError:
            pass


def _probe_health(timeout: float = 5.0) -> dict | None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        data = payload.get("data") if isinstance(payload, dict) else None
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _wait_healthy(expected: str, seconds: int) -> tuple[bool, str | None]:
    deadline = time.time() + seconds
    actual = None
    while time.time() < deadline:
        data = _probe_health()
        if data:
            actual = data.get("version")
            if actual == expected:
                return True, actual
        time.sleep(3)
    return False, actual


# ── 对外：回滚 / 单次校验 ────────────────────────────────────────────


def rollback_job(db, job_id: int, restore_db: bool = False, skip_frontend: bool = False) -> UpgradeJob:
    """基于某个已执行任务的回滚点，新建一个 rollback 任务并异步执行。"""
    src = db.get(UpgradeJob, job_id)
    if src is None:
        raise ValueError("任务不存在")
    if not src.from_ref:
        raise ValueError("该任务没有记录回滚点（from_ref），无法回滚")
    if working_tree_dirty():
        raise ValueError("工作区有未提交改动，请先提交或 stash 后再回滚")

    active = db.execute(
        select(UpgradeJob).where(UpgradeJob.status.in_(ACTIVE_STATUSES))
    ).scalars().first()
    if active is not None:
        raise ValueError(f"已有进行中的任务 #{active.id}（{active.status}），请等待其结束")

    job = UpgradeJob(
        action="rollback",
        from_version=read_local_version(),
        to_version=src.from_version,
        status="pending",
        stage="checkout",
        from_ref=src.from_ref,
        alembic_rev=_current_alembic_rev(db),
        backup_path=src.backup_path,
        operator_id=src.operator_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job.log_path = str(_log_path(job.id))
    db.add(job)
    db.commit()
    db.refresh(job)
    _log(
        job.id,
        f"回滚任务创建：基于 #{src.id}，目标 {job.to_version}，"
        f"restore_db={restore_db}，skip_frontend={skip_frontend}",
    )
    run_job(job.id, restore_db=restore_db, skip_frontend=skip_frontend)
    return job


def verify_job(db, job_id: int) -> dict:
    """单独的健康校验入口：用于 awaiting_restart 后手动确认。"""
    job = db.get(UpgradeJob, job_id)
    if job is None:
        raise ValueError("任务不存在")
    ok_, actual = _wait_healthy(job.to_version, 20)
    result = {
        "job_id": job.id,
        "expected": job.to_version,
        "actual": actual,
        "healthy": ok_,
        "status": job.status,
    }
    if job.status == "awaiting_restart":
        if ok_:
            job.status = "success"
            job.stage = "done"
            job.finished_at = datetime.now()
            _log(job.id, f"手动健康校验通过，版本 {actual}")
        else:
            job.status = "failed"
            job.stage = "done"
            job.error = f"健康校验失败：期望 {job.to_version}，实际 {actual or '无响应'}"
            job.finished_at = datetime.now()
            _log(job.id, job.error)
        db.commit()
        result["status"] = job.status
    return result
