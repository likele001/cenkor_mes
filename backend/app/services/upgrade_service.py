# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""后台在线升级 / 回滚服务。

设计要点：
- 所有重活放在守护线程里跑，HTTP 请求只负责建任务和下指令；
- 每一步都写文件日志（backend/data/upgrade_logs/{job_id}.log）并回写 DB 的 stage，
  前端靠轮询任务表 + 读日志展示进度；
- 数据库备份失败立即中止，绝不带病继续；
- 未配置 CENKORMES_RESTART_CMD 时停在 awaiting_restart，由运维手动重启，
  避免「重启进程 = 杀掉本线程」导致任务永远停在 running。
"""
from __future__ import annotations

import json
import os
import re
import shlex
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
VERIFY_TIMEOUT = 90

VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
ACTIVE_STATUSES = ("pending", "running")


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


def check_update() -> dict:
    """当前版本 / 远端最新版本 / 是否可更新 / 重启命令是否配置 / 磁盘余量。"""
    current = read_local_version()
    tags = list_remote_tags()          # 远端不可达时抛 RuntimeError，由路由转 400
    latest = tags[-1] if tags else current
    if tags and VERSION_RE.match(current):
        has_update = _tag_key(latest) > _tag_key(current)
    else:
        has_update = bool(tags) and latest != current
    return {
        "current": current,
        "latest": latest,
        "has_update": has_update,
        "restart_configured": bool(RESTART_CMD.strip()),
        "disk_free_gb": _disk_free_gb(),
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


def run_job(job_id: int, restore_db: bool = False) -> threading.Thread:
    """守护线程执行任务；进程退出即中断（需要真重启时由 awaiting_restart 兜住）。"""
    t = threading.Thread(target=_execute, args=(job_id, restore_db), daemon=True)
    t.start()
    return t


def _execute(job_id: int, restore_db: bool) -> None:
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
            _do_rollback(db, job, restore_db)
        else:
            _do_upgrade(db, job)
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


def _do_upgrade(db, job: UpgradeJob) -> None:
    jid = job.id

    # 1) 数据库备份：失败立即中止
    _set(db, job, stage="backup", status="running")
    _log(jid, "步骤 1/7 备份数据库")
    backup = _backup_database(job)
    job.backup_path = str(backup)
    db.commit()
    _log(jid, f"备份完成：{backup}")

    # 2) fetch
    _set(db, job, stage="fetch")
    _log(jid, "步骤 2/7 git fetch --tags")
    res = _run_cmd(["git", "-C", str(ROOT), "fetch", "--tags"], timeout=300)
    if res.returncode != 0:
        raise RuntimeError(f"git fetch 失败：{(res.stderr or '').strip()[:500]}")
    _log(jid, "fetch 完成")

    # 3) checkout
    if not job.from_ref:
        job.from_ref = _current_git_ref()
        db.commit()
    _set(db, job, stage="checkout")
    _log(jid, f"步骤 3/7 git checkout {job.to_version}（回滚点 {job.from_ref}）")
    res = _run_cmd(["git", "-C", str(ROOT), "checkout", job.to_version], timeout=300)
    if res.returncode != 0:
        raise RuntimeError(
            f"git checkout {job.to_version} 失败：{(res.stderr or res.stdout).strip()[:500]}"
        )
    _log(jid, "checkout 完成，VERSION=" + read_local_version())

    # 4) 依赖：失败跳过但记警告
    _set(db, job, stage="deps")
    _log(jid, "步骤 4/7 安装依赖 backend/requirements.txt")
    py = _venv_python()
    res = _run_cmd([str(py), "-m", "pip", "install", "-r", str(BACKEND_DIR / "requirements.txt")], timeout=1800)
    _log(jid, (res.stdout or "")[-3000:])
    if res.returncode != 0:
        _log(jid, f"[警告] 依赖安装失败，已跳过：{(res.stderr or '').strip()[:500]}")
    else:
        _log(jid, "依赖安装完成")

    # 5) 迁移
    _set(db, job, stage="migrate")
    _log(jid, "步骤 5/7 alembic upgrade head")
    res = _run_cmd(
        [str(py), "-c", "from alembic.config import main; main(['upgrade', 'head'])"],
        cwd=BACKEND_DIR,
        timeout=900,
    )
    if res.returncode != 0:
        raise RuntimeError(f"数据库迁移失败：{(res.stderr or res.stdout).strip()[:500]}")
    _log(jid, "迁移完成")

    # 6) 重启
    _set(db, job, stage="restart")
    _log(jid, "步骤 6/7 重启后端")
    if not _restart_backend(jid):
        _log(jid, "未配置 CENKORMES_RESTART_CMD，停在 awaiting_restart，请手动重启后端后点「健康校验」")
        _set(db, job, status="awaiting_restart", stage="restart")
        return

    # 7) 健康校验
    _set(db, job, stage="verify")
    _log(jid, f"步骤 7/7 健康校验 {HEALTH_URL}（最多 {VERIFY_TIMEOUT}s）")
    ok_, actual = _wait_healthy(job.to_version, VERIFY_TIMEOUT)
    if ok_:
        _log(jid, f"健康校验通过，版本 {actual}")
        _set(db, job, status="success", stage="done")
    else:
        msg = f"健康校验失败：期望 {job.to_version}，实际 {actual or '无响应'}；建议执行回滚"
        _log(jid, msg)
        job.error = msg
        _set(db, job, status="failed", stage="done")
    job.finished_at = datetime.now()
    db.commit()


def _do_rollback(db, job: UpgradeJob, restore_db: bool) -> None:
    jid = job.id
    ref = job.from_ref
    if not ref:
        raise RuntimeError("该任务未记录回滚点 from_ref，无法回滚")

    _set(db, job, stage="checkout", status="running")
    _log(jid, f"git checkout -f {ref}")
    res = _run_cmd(["git", "-C", str(ROOT), "checkout", "-f", ref], timeout=300)
    if res.returncode != 0:
        raise RuntimeError(f"git checkout -f 失败：{(res.stderr or res.stdout).strip()[:500]}")
    _log(jid, "代码已回滚，VERSION=" + read_local_version())

    if restore_db:
        if not job.backup_path:
            raise RuntimeError("未找到数据库备份文件，无法恢复数据")
        _set(db, job, stage="migrate")
        _log(jid, f"恢复数据库：{job.backup_path}")
        _restore_database(job)
        _log(jid, "数据库恢复完成")

    _set(db, job, stage="restart")
    if not _restart_backend(jid):
        _log(jid, "未配置 CENKORMES_RESTART_CMD，请手动重启后端后点「健康校验」")
        job.status = "rolled_back"
        db.commit()
        return

    _set(db, job, stage="verify")
    ok_, actual = _wait_healthy(job.to_version, VERIFY_TIMEOUT)
    if ok_:
        _log(jid, f"回滚后健康校验通过，版本 {actual}")
        job.status = "rolled_back"
        job.stage = "done"
    else:
        msg = f"回滚后健康校验失败：期望 {job.to_version}，实际 {actual or '无响应'}"
        _log(jid, msg)
        job.status = "failed"
        job.error = msg
        job.stage = "done"
    job.finished_at = datetime.now()
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


def _restart_backend(job_id: int) -> bool:
    """执行重启命令；未配置返回 False（调用方置 awaiting_restart）。"""
    cmd = RESTART_CMD.strip()
    if not cmd:
        return False
    _log(job_id, f"执行重启命令：{cmd}")
    # 独立会话启动：即便重启命令杀掉当前进程，子进程也不会被一起收走
    with open(_log_path(job_id), "a", encoding="utf-8") as out:
        subprocess.Popen(["bash", "-c", cmd], cwd=str(ROOT), stdout=out, stderr=out, start_new_session=True)
    return True


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


def rollback_job(db, job_id: int, restore_db: bool = False) -> UpgradeJob:
    """基于某个已执行任务的回滚点，新建一个 rollback 任务并异步执行。"""
    src = db.get(UpgradeJob, job_id)
    if src is None:
        raise ValueError("任务不存在")
    if not src.from_ref:
        raise ValueError("该任务没有记录回滚点（from_ref），无法回滚")

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
    _log(job.id, f"回滚任务创建：基于 #{src.id}，目标 {job.to_version}，restore_db={restore_db}")
    run_job(job.id, restore_db=restore_db)
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
