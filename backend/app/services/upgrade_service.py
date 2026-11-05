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
  reconcile_restarts() 回写最终状态，任务不会永远停在 running。结果回报 ok=0 时
  还会再实测一次 /api/health，避免「脚本窗口不够但服务其实已恢复」的误判。

两种升级模式（CENKORMES_UPGRADE_MODE）：
- artifact（默认）：从 GitHub Release 下载发布产物包（含预构建 dist），校验
  SHA256 后解包覆盖。客户机不需要 git、不需要 SSH key、不需要 node/npm。
- git：git fetch + checkout，仅适用于「开发机即生产机」的场景，需要有 .git 与
  远端读权限。

为什么默认改成 artifact：原实现靠 git checkout，对客户机是走不通的。
  - 客户拿到的是 zip/tarball，根本没有 .git，ls-remote 与 checkout 全部失败；
  - .gitignore 忽略了 dist/ 与 node_modules/，checkout 只换源码，前端产物必须
    在客户机上 npm ci + build 重建，客户机没 node 或连不上 registry 就当场炸；
  - 客户现场改过一个 tracked 文件，_assert_clean_tree 就直接拒绝升级。
  加上 remote 是 git@github.com: 形式时还需要每台机器配 deploy key，这条路
  本质上是「开发者自用」，不能当产品分发通道。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import threading
import time
import urllib.error
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
# 升级后要一并重启的 celery / beat 单元名。做成可配置是因为守护脚本里的服务名
# 是全局的：同机再跑一套预发实例时，两个实例若共用同一组名称，升级预发会连带
# 重启生产 worker（旧 worker 会继续跑旧代码，且打乱在生产跑的任务）。
CELERY_UNITS = os.environ.get("CENKORMES_CELERY_UNITS", "cenkormes-celery cenkormes-beat")

BACKEND_DIR = ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env"
HEALTH_URL = os.environ.get("CENKORMES_HEALTH_URL", "http://127.0.0.1:8500/api/health")
BACKEND_PORT = urlsplit(HEALTH_URL).port or 8500
# 宝塔 Python 项目管理器自愈实测 3m36s / 3m38s（2026-11-05 v2.2.3 升级+回滚）。
# 旧窗口 180s 会早 26~27s 放弃，把实际健康的服务误判为 failed。420s 留足一轮
# 自愈 + 应用启动 + 余量；面板策略变化时可用 CENKORMES_VERIFY_TIMEOUT 覆盖。
VERIFY_TIMEOUT = int(os.environ.get("CENKORMES_VERIFY_TIMEOUT", "420"))
RESTART_RESULT_DIR = Path("/tmp")

VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
ACTIVE_STATUSES = ("pending", "running")
# nginx 直接服务 dist，代码升级后必须重建；只重建源码有改动的应用
FRONTEND_APPS = (("frontend-admin-pro", "管理后台"), ("frontend-h5", "H5"))

# ── 产物包升级（artifact 模式）─────────────────────────────────────────
# GitHub 仓库标识与 API 入口。公开仓库匿名即可读 Releases，不需要任何令牌，
# 这也正是客户机能用的通道——不能用需要授权的接口。
REPO_SLUG = os.environ.get("CENKORMES_REPO", "likele001/cenkor_mes")
GITHUB_API = os.environ.get("CENKORMES_GITHUB_API", "https://api.github.com").rstrip("/")
# artifact = 下载发布产物包（默认，客户机用）；git = fetch + checkout（开发机用）
# 留空或 auto 时按是否存在 .git 自动选择，便于同一份代码在两处都跑得起来。
UPGRADE_MODE_ENV = os.environ.get("CENKORMES_UPGRADE_MODE", "artifact").strip().lower()
# 产物包与解包目录放在 backend/data 下：该目录已被 git 忽略，且和项目在同一个
# 文件系统上，改名/复制不会跨挂载点。
CACHE_DIR = BACKEND_DIR / "data/upgrade_cache"
# 记录上一版装过哪些文件，用于安全地判断「哪些文件已被上游删除」。
# 没有它就只能保守地不删任何文件（宁可留垃圾，不能删客户文件）。
MANIFEST_NAME = ".release-manifest.txt"
# 这些路径永远不被产物包覆盖，也不会被「清理废弃文件」删掉：
# .env 是现场配置，backend/data 下是客户数据（上传件、备份、扩展、模型）。
PROTECTED_PREFIXES = (
    "backend/data/",
    ".git/",
    "node_modules/",
    "backend/node_modules/",
    "backend/.venv/",
    "backend/venv/",
    ".venv/",
    "venv/",
    "logs/",
)
PROTECTED_SUFFIX_DIRS = ("dist.__bak/", ".dist-build-", ".dist-new-")
# Release 里没有 SHA256 摘要时是否仍允许安装。默认拒绝：升级包是直接覆盖代码的，
# 校验不了完整性就等于把「下载被中间人替换」的风险敞口全部打开。
ALLOW_UNVERIFIED = os.environ.get("CENKORMES_ALLOW_UNVERIFIED", "") == "1"
# 发布列表缓存时间：匿名 GitHub API 每小时 60 次，About 页轮询很容易打满
RELEASE_CACHE_TTL = int(os.environ.get("CENKORMES_RELEASE_CACHE_TTL", "300"))
_release_cache: dict[str, object] = {"at": 0.0, "rows": []}

# 每个阶段允许的最长执行时间（秒）。用于识别「进程已死但任务还挂在 running」的僵尸任务。
# backup 给 90 分钟：大库 mysqldump 本身就要很久，绝不能按短超时误杀。
STAGE_TIMEOUTS = {
    "backup": 5400,
    "fetch": 1800,     # artifact 模式这里是下载产物包
    "checkout": 1800,  # artifact 模式这里是逐文件覆盖 + 前端换入
    "deps": 2400,
    "build": 3600,     # npm ci + build 两个前端（仅 git 模式）
    "migrate": 1800,
    "restart": 900,  # 重启另有守护脚本结果文件兜底，这里只是最后防线
}
DEFAULT_STAGE_TIMEOUT = 3600

# 升级/回滚开始前要求的最小可用空间（字节）。
# 11-02 任务 #7 就是磁盘满导致前端产物换入失败，与其跑到一半炸，不如开工前拒绝。
MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

# 本进程正在执行的任务 id。进程重启后该集合为空——这正是判定僵尸任务的关键依据：
# 任务标记为 running，却不在本进程的执行集合里，说明执行线程已随旧进程消失。
# 前提是单 worker 部署（宝塔 Python 项目为 uvicorn 单进程），多 worker 需改用 DB 心跳。
_RUNNING_JOBS: set[int] = set()


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


def upgrade_mode() -> str:
    """当前生效的升级模式："artifact" 或 "git"。

    Returns:
        "artifact"（下载发布产物包）或 "git"（fetch + checkout）。

    Raises:
        RuntimeError: 显式要求 git 模式但目录不是 git 仓库。
    """
    mode = UPGRADE_MODE_ENV
    has_git = (ROOT / ".git").exists()
    if mode == "auto":
        return "git" if has_git else "artifact"
    if mode == "git" and not has_git:
        raise RuntimeError(
            "已配置 CENKORMES_UPGRADE_MODE=git，但当前目录不是 git 仓库；"
            "请改为 artifact 模式（默认），或重新 clone 后再升级"
        )
    return "git" if mode == "git" else "artifact"


def _http_get_json(url: str, timeout: int = 30) -> dict | list:
    """匿名 GET JSON。公开仓库的 Releases 接口无需任何凭据。"""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "cenkormes-upgrade",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_remote_releases(*, refresh: bool = False) -> list[dict]:
    """列出远端已发布版本（不含草稿与预发布），按语义版本升序。

    返回结构::

        [{"version": "v2.2.1", "published_at": "...", "assets": [{"name","url","size","digest"}]}]

    Args:
        refresh: 忽略缓存强制刷新。

    Returns:
        版本信息列表，升序。

    Raises:
        RuntimeError: 接口不可达或返回非列表。
    """
    now = time.time()
    cached = _release_cache.get("rows") or []
    if not refresh and cached and now - float(_release_cache.get("at") or 0) < RELEASE_CACHE_TTL:
        return list(cached)  # type: ignore[arg-type]

    rows: list[dict] = []
    # per_page=30 够用：升级只需要「最新版」与「上一版」，翻太多反而慢
    data = _http_get_json(f"{GITHUB_API}/repos/{REPO_SLUG}/releases?per_page=30")
    if not isinstance(data, list):
        raise RuntimeError(f"Releases 接口返回异常：{str(data)[:200]}")
    for rel in data:
        tag = (rel.get("tag_name") or "").strip()
        if not VERSION_RE.match(tag) or rel.get("draft") or rel.get("prerelease"):
            continue
        assets = [
            {
                "name": a.get("name") or "",
                "url": a.get("browser_download_url") or "",
                "size": a.get("size") or 0,
                "digest": a.get("digest") or "",
            }
            for a in rel.get("assets") or []
        ]
        rows.append(
            {"version": tag, "published_at": rel.get("published_at") or "", "assets": assets}
        )
    rows.sort(key=lambda r: _tag_key(r["version"]))
    if not rows:
        raise RuntimeError(
            f"仓库 {REPO_SLUG} 没有任何带产物包的正式 Release；"
            "请先按发版流程打 tag 并等待 Release 工作流完成"
        )
    _release_cache["at"] = now
    _release_cache["rows"] = rows
    return rows


def _find_release(version: str) -> dict:
    """取指定版本的 Release 信息。

    Raises:
        RuntimeError: 该版本没有发布产物包。
    """
    for rel in list_remote_releases():
        if rel["version"] == version:
            return rel
    raise RuntimeError(f"远端没有 {version} 的正式 Release，无法安装该版本")


def _pick_asset(rel: dict, suffix: str) -> dict | None:
    for a in rel["assets"]:
        if a["name"].endswith(suffix):
            return a
    return None


def _asset_sha256(rel: dict, asset: dict) -> str:
    """取产物包的 SHA256：优先接口自带的 digest，其次同名 .sha256 文件。

    Raises:
        RuntimeError: 两种来源都拿不到，且未显式允许未校验安装。
    """
    digest = (asset.get("digest") or "").strip()
    if digest.startswith("sha256:"):
        return digest[len("sha256:") :].strip().lower()

    sha_asset = _pick_asset(rel, ".sha256")
    if sha_asset:
        try:
            body = urllib.request.urlopen(sha_asset["url"], timeout=30).read().decode("utf-8", "replace")
            first = body.strip().split()[0] if body.strip() else ""
            if re.fullmatch(r"[0-9a-fA-F]{64}", first):
                return first.lower()
        except (urllib.error.URLError, OSError):
            pass

    if ALLOW_UNVERIFIED:
        return ""
    raise RuntimeError(
        f"{asset['name']} 没有可用的 SHA256 摘要，已拒绝安装（无法校验完整性）。"
        "确认来源可信时可设 CENKORMES_ALLOW_UNVERIFIED=1 跳过校验"
    )


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
    """tracked 文件是否有未提交改动（新日志/备份/构建产物均为 untracked，不阻塞升级）。

    非 git 部署（客户拿产物包安装，没有 .git）恒为 False：没有「工作区」这个概念，
    也就没有会被 checkout 覆盖的本地改动。
    """
    if not (ROOT / ".git").exists():
        return False
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
    mode = upgrade_mode()
    if mode == "artifact":
        # 产物包模式只认「有正式 Release 且有包」的版本：只有 tag 没有包的版本
        # 点了升级也装不上，不该在界面上提示可更新。
        versions = [r["version"] for r in list_remote_releases() if _pick_asset(r, ".tar.gz")]
    else:
        versions = list_remote_tags()  # 远端不可达时抛 RuntimeError，由路由转 400
    latest = versions[-1] if versions else current
    if versions and VERSION_RE.match(current):
        has_update = _tag_key(latest) > _tag_key(current)
    else:
        has_update = bool(versions) and latest != current
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
        "upgrade_mode": mode,
        "repo": REPO_SLUG if mode == "artifact" else None,
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


def _pid_alive(pid: int) -> bool:
    """判断 pid 对应的进程是否还活着（不发送真实信号，只做存在性探测）。

    Returns:
        True 表示进程存在（含「存在但属于其他用户」的情况，保守处理）。
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 进程存在，只是当前用户没权限发信号
    except OSError:
        return False
    return True


def _lock_holder_pid() -> int | None:
    """读锁文件里记录的持有者 pid（_acquire_lock 写入的就是 os.getpid()）。

    Returns:
        持有者 pid；锁不存在或内容不是整数时返回 None。
    """
    try:
        raw = LOCK_FILE.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


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
    mode = upgrade_mode()
    if mode == "git":
        # git 模式靠 checkout 换代码，本地改动会被带进新版本
        if working_tree_dirty():
            raise ValueError("工作区有未提交改动，请先提交或 stash 后再升级")
    else:
        # artifact 模式先确认远端真有这个版本的包，避免建了任务才发现装不上
        rel = _find_release(to_version)
        if not _pick_asset(rel, ".tar.gz"):
            raise ValueError(f"{to_version} 的 Release 里没有 .tar.gz 产物包，无法升级")

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
        # 先登记再改状态：reconcile_jobs() 靠这个集合区分「本进程在跑」与「旧进程僵尸」
        _RUNNING_JOBS.add(job_id)
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
        _RUNNING_JOBS.discard(job_id)
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
    """换入产物：线上 dist 先改名为 dist.__bak，再把临时产物改名为 dist。

    两次 rename 之间线上 dist 并不存在，因此第二次失败（disk full / inode 耗尽）
    必须立刻把 dist.__bak 改回去，否则站点会直接 404。
    11-02 任务 #7 的「产物换入失败：disk full」正踩在这里。
    """
    live = ROOT / app / "dist"
    backup = ROOT / app / "dist.__bak"
    shutil.rmtree(backup, ignore_errors=True)
    moved_away = False
    if live.exists():
        live.rename(backup)
        moved_away = True
    try:
        out_dir.rename(live)
    except OSError as exc:
        if moved_away and not live.exists() and backup.exists():
            try:
                backup.rename(live)
                _log(job_id, f"[错误] {app} 产物换入失败，线上 dist 已还原：{exc}")
            except OSError as restore_exc:
                _log(
                    job_id,
                    f"[严重] {app} 产物换入失败且还原失败，站点可能已 404："
                    f"{exc}；{restore_exc}；请手动执行 mv {backup} {live}",
                )
        else:
            _log(job_id, f"[错误] {app} 产物换入失败：{exc}")
        raise
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


def _promote_frontends(
    built: list[tuple[str, Path]], job_id: int, *, strict: bool
) -> list[str]:
    """换入产物；返回已换入的应用名，供失败时回退。"""
    promoted: list[str] = []
    for app, out_dir in built:
        try:
            _promote_frontend(app, out_dir, job_id)
            promoted.append(app)
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(out_dir, ignore_errors=True)
            if strict:
                raise
            _log(job_id, f"[警告] {app} 产物换入失败：{exc}")
    return promoted


def _restore_frontend(app: str, job_id: int) -> None:
    """把线上 dist 退回升级前的 dist.__bak（仅对已换入的应用调用）。"""
    live = ROOT / app / "dist"
    backup = ROOT / app / "dist.__bak"
    if not backup.exists():
        _log(job_id, f"[警告] {app} 未找到 dist.__bak，前端产物未回退")
        return
    try:
        if live.exists():
            shutil.rmtree(live, ignore_errors=True)
        backup.rename(live)
        _log(job_id, f"{app}: 前端产物已回退为升级前版本")
    except OSError as exc:
        _log(job_id, f"[错误] {app} 前端产物回退失败：{exc}；请手动从 dist.__bak 恢复")


def _restore_code(job: UpgradeJob, job_id: int) -> None:
    """升级失败后把代码退回 from_ref。

    只回代码：MySQL DDL 无法事务回滚，已执行的迁移不会退回，
    日志里明确提示，由人工决定是否用备份恢复数据库。
    """
    ref = job.from_ref
    if not ref:
        _log(job_id, "[警告] 任务未记录回滚点 from_ref，无法自动恢复代码，请手动处理")
        return
    res = _run_cmd(["git", "-C", str(ROOT), "checkout", "-f", ref], timeout=300)
    if res.returncode != 0:
        _log(
            job_id,
            f"[错误] 代码自动恢复失败，请手动执行 git checkout -f {ref}："
            f"{(res.stderr or res.stdout).strip()[:300]}",
        )
        return
    _log(
        job_id,
        f"代码已恢复到 {ref}（仅代码；已执行的数据库迁移未回滚，"
        f"如需恢复数据请使用备份 {job.backup_path or '-'}）",
    )


def _check_disk_space(job_id: int) -> None:
    """开工前检查可用空间，不足则拒绝升级。

    磁盘满是「跑到一半才炸」的典型失败模式：mysqldump 写一半、前端产物换入
    失败、dist 与 dist.__bak 与临时构建目录同时占空间。前置检查成本几乎为零。
    """
    try:
        usage = shutil.disk_usage(ROOT)
    except OSError as exc:  # 拿不到磁盘信息不该阻断升级
        _log(job_id, f"[警告] 无法获取磁盘信息（{exc}），跳过空间检查")
        return
    need_mb = MIN_FREE_BYTES // (1024 * 1024)
    free_mb = usage.free // (1024 * 1024)
    _log(job_id, f"磁盘可用 {free_mb} MB（要求至少 {need_mb} MB）")
    if usage.free < MIN_FREE_BYTES:
        raise RuntimeError(
            f"磁盘可用空间不足：仅 {free_mb} MB，至少需要 {need_mb} MB"
            f"（数据库备份 + 前端构建产物 + 换入占位）。请先清理后重试"
        )


def _deps_satisfied(py: Path, req: Path) -> tuple[bool, str]:
    """pip install 失败后的复核：现有环境是否已满足 requirements。

    只依赖 --dry-run 的退出码与「Would install」关键字，不解析具体包名——
    requirements 里的环境标记、VCS 依赖、嵌套 -r 都会把解析逻辑写脆。

    Args:
        py: 虚拟环境 python 路径。
        req: requirements.txt 路径。

    Returns:
        (是否已满足, 说明文本)。
    """
    res = _run_cmd([str(py), "-m", "pip", "install", "-r", str(req), "--dry-run"], timeout=900)
    out = f"{res.stdout or ''}\n{res.stderr or ''}".strip()
    if res.returncode != 0:
        return False, f"dry-run 复核失败：{out[:300]}"
    if "Would install" in out:
        return False, "仍有未满足依赖：" + out.split("Would install", 1)[1].strip()[:300]
    return True, "already satisfied"


def _install_deps(job_id: int, py: Path) -> None:
    """安装依赖；失败后复核环境，确认不满足则中止。

    旧实现里 pip install 非 0 只写一行警告就继续，任务最后可能仍显示 success，
    但进程可能起不来、或跑到某个功能才炸。现在区分两种失败：
      - 环境其实已满足（多为网络/源抖动）→ 记明理由后放行
      - 环境仍不满足，或复核本身失败 → 抛错，由调用方回退代码

    Raises:
        RuntimeError: 依赖安装失败且环境不满足。
    """
    req = BACKEND_DIR / "requirements.txt"
    if not req.exists():
        _log(job_id, f"[警告] {req} 不存在，跳过依赖安装")
        return
    res = _run_cmd([str(py), "-m", "pip", "install", "-r", str(req)], timeout=1800)
    _log(job_id, (res.stdout or "")[-3000:])
    if res.returncode == 0:
        _log(job_id, "依赖安装完成")
        return

    _log(job_id, f"[警告] 依赖安装失败：{(res.stderr or '').strip()[:500]}")
    ok, detail = _deps_satisfied(py, req)
    if ok:
        _log(job_id, "复核结论：当前环境已满足 requirements.txt（失败疑似网络抖动），继续升级")
        return
    raise RuntimeError(f"依赖安装失败且环境不满足 requirements.txt：{detail}")


def _do_upgrade(db, job: UpgradeJob, skip_frontend: bool = False) -> None:
    """按当前模式分派：artifact 下载产物包覆盖，git 走 fetch + checkout。"""
    if upgrade_mode() == "artifact":
        _do_upgrade_artifact(db, job, skip_frontend)
    else:
        _do_upgrade_git(db, job, skip_frontend)


def _do_upgrade_git(db, job: UpgradeJob, skip_frontend: bool = False) -> None:
    jid = job.id

    # 0) 前置体检：空间不足直接拒绝，此时还没有任何东西被改动过
    _set(db, job, stage="preflight", status="running")
    _check_disk_space(jid)

    # 1) 数据库备份：失败立即中止
    _set(db, job, stage="backup")
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

    # 4)~7) 从 checkout 之后统一纳入回退保护：任一步失败都把代码退回 from_ref。
    # 依赖失败曾经在保护范围之外，结果是「磁盘上是新代码、进程里是旧代码、
    # 依赖还缺着」，重启后服务起不来，比直接中止危险得多。
    py = _venv_python()
    built: list[tuple[str, Path]] = []
    promoted: list[str] = []

    try:
        # 4) 依赖：失败先复核环境是否已满足，不满足则中止
        _set(db, job, stage="deps")
        _log(jid, "步骤 4/8 安装依赖 backend/requirements.txt")
        _install_deps(jid, py)

        # 5) 前端：先构建到临时目录；失败则中止（dist 与数据库都保持原样）
        _set(db, job, stage="build")
        _log(jid, "步骤 5/8 构建前端（仅源码有改动的应用）")
        built = _prepare_frontends(
            job, job.from_ref, job.to_version, skip=skip_frontend, strict=True
        )

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
            promoted = _promote_frontends(built, jid, strict=True)
    except Exception:
        # 构建/迁移/换入失败：代码回退到升级前，已换入的前端产物一并回退，
        # 避免出现「新前端 + 旧后端」或「新代码 + 旧库」的错位
        _log(jid, "升级步骤失败，开始回退代码与前端产物")
        for _, tmp in built:
            shutil.rmtree(tmp, ignore_errors=True)
        for app in reversed(promoted):
            _restore_frontend(app, jid)
        _restore_code(job, jid)
        raise

    # 8) 重启：交给重启守护脚本（它会杀掉本进程），后续状态由 reconcile_restarts() 收尾
    _set(db, job, stage="restart")
    _log(jid, "步骤 8/8 重启后端")
    if not _spawn_restart_guard(jid, job.to_version):
        _log(jid, "重启脚本启动失败，停在 awaiting_restart，请手动重启后端后点「健康校验」")
        _set(db, job, status="awaiting_restart", stage="restart")
        return
    _log(jid, f"由守护脚本做健康校验；本进程即将退出，任务最终状态最长 {VERIFY_TIMEOUT}s 内回写")
    db.commit()


def _do_rollback(db, job: UpgradeJob, restore_db: bool, skip_frontend: bool = False) -> None:
    if upgrade_mode() == "artifact":
        _do_rollback_artifact(db, job, restore_db, skip_frontend)
    else:
        _do_rollback_git(db, job, restore_db, skip_frontend)


def _do_rollback_git(db, job: UpgradeJob, restore_db: bool, skip_frontend: bool = False) -> None:
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


# ── 产物包升级 / 回滚（客户机路径：无 git、无 SSH、无 node）──────────────


def _sha256_of(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _is_protected(rel: str) -> bool:
    """该相对路径是否属于「现场资产」或由别的逻辑专门处理，永不被覆盖/删除。"""
    if rel == MANIFEST_NAME:
        return True
    name = rel.rsplit("/", 1)[-1]
    if name == ".env" or name.startswith(".env."):
        return True
    if rel.startswith(PROTECTED_PREFIXES):
        return True
    # 前端产物由 _promote_frontend 整体原子换入，不走逐文件覆盖
    if any(rel.startswith(f"{app}/dist/") for app, _ in FRONTEND_APPS):
        return True
    # 临时产物目录与旧产物备份
    return any(tag in rel for tag in PROTECTED_SUFFIX_DIRS)


def _read_manifest() -> set[str] | None:
    """读上一版安装清单；不存在时返回 None（首次以产物包升级）。"""
    f = ROOT / MANIFEST_NAME
    if not f.exists():
        return None
    try:
        rows = {ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except (OSError, UnicodeDecodeError):
        return None
    return rows or None


def _write_manifest(rels: set[str]) -> None:
    """原子写清单：先写临时文件再改名，避免中途失败留下半截清单。"""
    f = ROOT / MANIFEST_NAME
    tmp = f.with_suffix(".tmp")
    tmp.write_text("\n".join(sorted(rels)) + "\n", encoding="utf-8")
    tmp.replace(f)


def _seed_manifest_from_git() -> set[str] | None:
    """首次升级时若目录仍是 git 仓库，用 git ls-files 反推上一版清单。

    这样从「git 部署」切到「产物包部署」的第一跳也能精确算出哪些文件被上游
    删除，而不是因为缺清单就永久不清理。
    """
    if not (ROOT / ".git").exists():
        return None
    res = _run_cmd(["git", "-C", str(ROOT), "-c", "core.quotePath=false", "ls-files"], timeout=120)
    if res.returncode != 0:
        return None
    rows = {ln.strip() for ln in res.stdout.splitlines() if ln.strip()}
    return rows or None


def _download_package(rel: dict, job_id: int) -> Path:
    """下载产物包并校验 SHA256；本地缓存摘要一致时跳过下载。

    Args:
        rel: list_remote_releases() 的一项。
        job_id: 任务号，用于写日志。

    Returns:
        本地产物包路径。

    Raises:
        RuntimeError: 无产物包、下载失败或摘要不匹配。
    """
    asset = _pick_asset(rel, ".tar.gz")
    if not asset:
        raise RuntimeError(f"{rel['version']} 的 Release 里没有 .tar.gz 产物包")
    expected = _asset_sha256(rel, asset)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / f"{rel['version']}.tar.gz"
    if dest.exists() and dest.stat().st_size > 0:
        if not expected or _sha256_of(dest) == expected:
            _log(job_id, f"命中本地缓存：{dest.name}（{dest.stat().st_size // 1024} KB）")
            return dest
        _log(job_id, f"本地缓存 {dest.name} 摘要不匹配，重新下载")
        dest.unlink(missing_ok=True)

    part = dest.with_suffix(".part")
    _log(job_id, f"下载产物包：{asset['url']}")
    try:
        with urllib.request.urlopen(asset["url"], timeout=120) as resp, part.open("wb") as out:
            total = int(resp.headers.get("Content-Length") or asset.get("size") or 0)
            done = 0
            next_mark = 25
            while True:
                block = resp.read(1024 * 256)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if total and done * 100 // total >= next_mark:
                    _log(job_id, f"下载进度 {next_mark}%（{done // 1024} / {total // 1024} KB）")
                    next_mark += 25
    except (urllib.error.URLError, OSError) as exc:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"下载产物包失败：{exc}") from exc

    if part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        raise RuntimeError("下载到的产物包为空")

    if expected:
        actual = _sha256_of(part)
        if actual != expected:
            part.unlink(missing_ok=True)
            raise RuntimeError(
                f"SHA256 校验失败：期望 {expected[:16]}…，实际 {actual[:16]}…（下载可能被截断或篡改）"
            )
        _log(job_id, f"SHA256 校验通过：{expected[:16]}…")
    else:
        _log(job_id, "[警告] 该 Release 未提供摘要，已按 CENKORMES_ALLOW_UNVERIFIED=1 跳过校验")

    part.replace(dest)
    _log(job_id, f"产物包就绪：{dest.name}（{dest.stat().st_size // 1024} KB）")
    return dest


def _package_root(extract_dir: Path) -> Path:
    """定位包含 VERSION 的包根目录（兼容有无顶层目录两种打包方式）。"""
    if (extract_dir / "VERSION").is_file():
        return extract_dir
    subs = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(subs) == 1 and (subs[0] / "VERSION").is_file():
        return subs[0]
    raise RuntimeError("产物包结构异常：找不到 VERSION 文件（应含 backend/、frontend-*/ 与 VERSION）")


def _extract_dir(job_id: int) -> Path:
    """解包工作目录（按任务号隔离，便于失败时定向清理）。"""
    return CACHE_DIR / f"extract-{job_id}"


def _extract_package(pkg: Path, job_id: int) -> Path:
    """解包到独立目录，返回包根。

    Raises:
        RuntimeError: 包损坏或结构不对。
    """
    target = _extract_dir(job_id)
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    _log(job_id, f"解包到 {target}")
    try:
        with tarfile.open(pkg, "r:gz") as tf:
            try:
                # filter="data" 拦截绝对路径与 ../ 穿越、拒绝设备文件，py3.12+
                tf.extractall(target, filter="data")
            except TypeError:  # 老版本 Python 没有 filter 参数
                tf.extractall(target)
    except (tarfile.TarError, OSError) as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(f"解包失败：{exc}") from exc
    return _package_root(target)


def _verify_package(root: Path, version: str, job_id: int) -> None:
    """校验包内容与目标版本一致、关键文件齐全。

    Raises:
        RuntimeError: 版本不符或关键文件缺失。
    """
    try:
        ver = (root / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"读取包内 VERSION 失败：{exc}") from exc
    if ver != version:
        raise RuntimeError(f"包内 VERSION={ver} 与目标版本 {version} 不一致，已中止")
    required = ("backend/app/main.py", "backend/requirements.txt")
    missing = [r for r in required if not (root / r).is_file()]
    if missing:
        raise RuntimeError("产物包缺少关键文件：" + "、".join(missing))
    for app, label in FRONTEND_APPS:
        if not (root / app / "dist" / "index.html").is_file():
            _log(job_id, f"[警告] 包内缺少 {label} 前端产物（{app}/dist），将保留线上现有 dist")
    _log(job_id, f"产物包校验通过：VERSION={ver}")


def _collect_package_files(root: Path) -> tuple[list[str], dict[str, Path]]:
    """列出包内需要覆盖的文件，前端 dist 单独返回以便原子换入。

    Returns:
        (普通文件相对路径列表, {前端应用: 包内 dist 目录})
    """
    dist_dirs = {app: root / app / "dist" for app, _ in FRONTEND_APPS if (root / app / "dist").is_dir()}
    dist_prefixes = tuple(f"{app}/dist/" for app in dist_dirs)
    files: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(dist_prefixes):
            continue
        if _is_protected(rel):
            continue
        files.append(rel)
    return files, dist_dirs


class PreflightError(RuntimeError):
    """开工前体检未通过：项目目录尚未被任何写操作改动，不需要回灌。"""


def _perm_bits(path: Path, *, uid: int, gids: frozenset[int]) -> int:
    """返回指定身份对 path 的 rwx 位。

    不用 ``os.access``：以 root 跑单测时它恒为 True，测不出 www 的权限问题。
    直接看 mode 位 + 注入 uid/gids，生产与单测行为一致。

    Args:
        path: 已存在的路径。
        uid: 生效 uid；None 由调用方解析为 os.geteuid()。
        gids: 补充组 gid 集合。

    Returns:
        0o0~0o7 的权限位；root 视为拥有全部权限。
    """
    if uid == 0:
        return 0o7
    st = path.stat()
    if st.st_uid == uid:
        return (st.st_mode >> 6) & 0o7
    if st.st_gid in gids:
        return (st.st_mode >> 3) & 0o7
    return st.st_mode & 0o7


def _nearest_existing_dir(path: Path) -> Path | None:
    """找 path 最近的已存在祖先目录；链断裂或祖先是文件时返回 None。"""
    cur = path
    while not cur.exists():
        if cur == cur.parent:
            return None
        cur = cur.parent
    return cur if cur.is_dir() else None


def _preflight_writable(
    files: list[str],
    dist_dirs: dict[str, Path],
    job_id: int,
    *,
    uid: int | None = None,
    gids: frozenset[int] | None = None,
) -> None:
    """覆盖前检查全部目标路径对服务运行身份可写，fail-fast 不留半新半旧代码。

    2026-11-05 任务 #4 的教训：项目里 66304 个文件属主是 root，产物包覆盖
    第 1 个文件就 PermissionError，连自动回灌也被同一权限挡住。磁盘体检只管
    空间，管不了属主，所以必须在**动第一个文件之前**把整批路径扫一遍。
    前端 dist 是整目录 rename + rmtree，删除只需父目录可写，因此目录树里
    每一层目录都要有 wx 位（光看顶层会漏掉 root 拥有的子目录）。

    Args:
        files: 待覆盖的普通文件相对路径（已由 _collect_package_files 过滤）。
        dist_dirs: 待原子换入的前端 dist 目录，键为应用目录名。
        job_id: 任务号，仅用于写日志。
        uid: 判定用的 uid；None 表示 os.geteuid()，单测可注入模拟 www。
        gids: 判定用的 gid 集合；None 表示当前进程的组集合。

    Raises:
        PreflightError: 任一路径不可写。此时项目目录完全未被改动，外层不应回灌。
    """
    eff_uid = os.geteuid() if uid is None else uid
    eff_gids = (
        frozenset(set(os.getgroups()) | {os.getegid()}) if gids is None else gids
    )
    problems: list[str] = []

    def dir_ok(directory: Path, label: str) -> None:
        cur = _nearest_existing_dir(directory)
        if cur is None:
            problems.append(f"{label}：父目录链不存在或祖先不是目录")
            return
        if (_perm_bits(cur, uid=eff_uid, gids=eff_gids) & 0o3) != 0o3:
            problems.append(f"{label}：目录 {cur} 缺写/执行权限")

    for rel in files:
        dst = ROOT / rel
        if dst.is_dir():
            problems.append(f"{rel}：目标是目录，包内却是文件")
        elif dst.exists():
            if not (_perm_bits(dst, uid=eff_uid, gids=eff_gids) & 0o2):
                problems.append(f"{rel}：已存在但当前身份不可写")
        else:
            dir_ok(dst.parent, rel)

    for app in dist_dirs:
        app_dir = ROOT / app
        dir_ok(app_dir, f"{app}/dist 换入")
        for label, live in (("dist", app_dir / "dist"), ("dist.__bak", app_dir / "dist.__bak")):
            if not live.is_dir():
                continue
            for sub in (live, *(x for x in live.rglob("*") if x.is_dir())):
                if (_perm_bits(sub, uid=eff_uid, gids=eff_gids) & 0o3) != 0o3:
                    problems.append(
                        f"{app}/{label} 内目录 {sub.name} 不可写（旧产物无法清理/换入）"
                    )
                    break

    if problems:
        preview = "；".join(problems[:5])
        more = f"（另有 {len(problems) - 5} 项）" if len(problems) > 5 else ""
        raise PreflightError(
            f"目录可写性预检未通过（{len(problems)} 项）：{preview}{more}。"
            f"请以服务运行身份修复属主后重试：chown -R www:www {ROOT}"
        )
    _log(job_id, f"可写性预检通过（{len(files)} 个文件 + {len(dist_dirs)} 个前端产物）")


def _apply_package(root: Path, job_id: int, *, replace_dist: bool = True) -> list[str]:
    """把包内容覆盖到项目目录。

    覆盖是逐文件 copy2（不删目录、不用外部命令），因此不需要 rsync；
    受保护路径（.env、backend/data、node_modules、.git）一律跳过。
    上游已删除的文件按「旧清单 − 新清单」精确清理，不用清单就不删。

    Args:
        root: 包根目录。
        job_id: 任务号。
        replace_dist: 是否换入前端 dist（skip_frontend 时为 False）。

    Returns:
        已换入 dist 的前端应用名列表，供失败回退。

    Raises:
        PreflightError: 覆盖前可写性预检未通过，项目目录未被改动。
        RuntimeError: 覆盖过程中写文件失败。
    """
    files, dist_dirs = _collect_package_files(root)
    _preflight_writable(files, dist_dirs, job_id)
    _log(job_id, f"准备覆盖 {len(files)} 个文件")
    for rel in files:
        src = root / rel
        dst = ROOT / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        except OSError as exc:
            raise RuntimeError(f"写入 {rel} 失败：{exc}") from exc
    _log(job_id, "代码文件覆盖完成")

    promoted: list[str] = []
    if replace_dist:
        for app, dist_src in dist_dirs.items():
            staged = ROOT / app / f".dist-new-{job_id}"
            shutil.rmtree(staged, ignore_errors=True)
            shutil.copytree(dist_src, staged)
            _promote_frontend(app, staged, job_id)
            promoted.append(app)
    elif dist_dirs:
        _log(job_id, "已跳过前端产物换入（skip_frontend）")

    # 清单必须在覆盖成功之后才写：中途失败时旧清单仍然有效，便于下次比对
    new_manifest = set(files)
    for app, _ in FRONTEND_APPS:
        for p in (ROOT / app / "dist").rglob("*"):
            if p.is_file():
                new_manifest.add(p.relative_to(ROOT).as_posix())
    old_manifest = _read_manifest()
    if old_manifest is None:
        old_manifest = _seed_manifest_from_git()
        if old_manifest:
            _log(job_id, f"首次以产物包升级，用 git ls-files 反推上一版清单（{len(old_manifest)} 项）")
    if old_manifest:
        _prune_removed_files(old_manifest, new_manifest, job_id)
    else:
        _log(job_id, "[警告] 无上一版清单，跳过废弃文件清理（宁可留垃圾，不删无法确认的文件）")
    _write_manifest(new_manifest)
    _log(job_id, f"安装清单已更新（{len(new_manifest)} 项）")
    return promoted


def _prune_removed_files(old: set[str], new: set[str], job_id: int) -> None:
    """删除「上一版有、这一版没有」且不在受保护路径下的文件。"""
    root_abs = ROOT.resolve()
    removed = 0
    for rel in sorted(old - new):
        if _is_protected(rel):
            continue
        p = ROOT / rel
        try:
            if not p.resolve().is_relative_to(root_abs):  # 防御清单被篡改
                _log(job_id, f"[警告] 拒绝删除项目目录外的路径：{rel}")
                continue
            if p.is_file() or p.is_symlink():
                p.unlink()
                removed += 1
        except OSError as exc:
            _log(job_id, f"[警告] 删除已废弃文件 {rel} 失败：{exc}")
    if removed:
        _log(job_id, f"清理上游已删除的文件：{removed} 个")


def _reinstall_version(version: str, job_id: int, note: str) -> None:
    """重新安装指定版本（失败回灌用）。

    Raises:
        RuntimeError: 该版本不可获取或安装失败。
    """
    rel = _find_release(version)
    pkg = _download_package(rel, job_id)
    try:
        root = _extract_package(pkg, job_id)
        _verify_package(root, version, job_id)
        _apply_package(root, job_id, replace_dist=True)
    finally:
        shutil.rmtree(_extract_dir(job_id), ignore_errors=True)
    _log(job_id, note)


def _do_upgrade_artifact(db, job: UpgradeJob, skip_frontend: bool = False) -> None:
    """产物包升级主流程：备份 → 下载校验 → 解包 → 覆盖 → 依赖 → 迁移 → 重启。"""
    jid = job.id
    target = job.to_version

    # 0) 前置体检：空间不足直接拒绝，此时没有任何东西被改动
    _set(db, job, stage="preflight", status="running")
    _log(jid, f"升级模式：产物包（仓库 {REPO_SLUG}），无需 git / SSH / node")
    _check_disk_space(jid)

    # 1) 数据库备份：失败立即中止
    _set(db, job, stage="backup")
    _log(jid, "步骤 1/7 备份数据库")
    backup = _backup_database(job)
    job.backup_path = str(backup)
    db.commit()
    _log(jid, f"备份完成：{backup}")

    # 2) 下载 + 校验
    _set(db, job, stage="fetch")
    _log(jid, f"步骤 2/7 获取 {target} 产物包")
    rel = _find_release(target)
    pkg = _download_package(rel, jid)

    # 3) 解包 + 校验（放在 try 内，失败也走统一清理）
    py = _venv_python()
    promoted: list[str] = []
    applied = False
    try:
        _set(db, job, stage="checkout")
        _log(jid, "步骤 3/7 解包并校验产物内容")
        root = _extract_package(pkg, jid)
        _verify_package(root, target, jid)

        # 4) 覆盖代码（前端 dist 原子换入）
        _log(jid, "步骤 4/7 覆盖代码（保留 .env 与 backend/data）")
        applied = True  # 一旦开始写盘就不能再假定目录是干净的
        promoted = _apply_package(root, jid, replace_dist=not skip_frontend)
        _log(jid, "代码已更新，VERSION=" + read_local_version())

        # 5) 依赖：包内已带预构建前端，不再需要 node/npm
        _set(db, job, stage="deps")
        _log(jid, "步骤 5/7 安装后端依赖")
        _install_deps(jid, py)

        # 6) 迁移
        _set(db, job, stage="migrate")
        _log(jid, "步骤 6/7 alembic upgrade head")
        res = _run_cmd(
            [str(py), "-c", "from alembic.config import main; main(['upgrade', 'head'])"],
            cwd=BACKEND_DIR,
            timeout=900,
        )
        if res.returncode != 0:
            raise RuntimeError(f"数据库迁移失败：{(res.stderr or res.stdout).strip()[:500]}")
        _log(jid, "迁移完成")
    except PreflightError:
        # 预检跑在 _apply_package 的第一个 copy2 之前，此时 applied 位虽然已经
        # 置上（防止中途失败时不回灌），但磁盘分毫未动，绝不能去下载旧包回灌。
        _log(jid, "可写性预检未通过，项目目录未被改动，无需回灌")
        raise
    except Exception:
        if not applied:
            _log(jid, "失败发生在写盘之前，项目目录未被改动，无需回灌")
            raise
        _log(jid, "安装步骤失败，开始回灌升级前版本")
        for app in reversed(promoted):
            _restore_frontend(app, jid)
        prev = job.from_version
        if VERSION_RE.match(prev or ""):
            try:
                _reinstall_version(
                    prev,
                    jid,
                    f"代码已回灌到 {prev}（数据库迁移不会自动回退，"
                    f"如需恢复数据请用备份 {job.backup_path or '-'}）",
                )
            except Exception as exc:  # noqa: BLE001 - 回灌失败只能如实告警
                _log(
                    jid,
                    f"[严重] 回灌 {prev} 失败：{exc}；"
                    f"请手动安装该版本，或使用备份 {job.backup_path or '-'} 恢复",
                )
        else:
            _log(jid, f"[严重] 无法确定升级前版本号（{prev}），请手动处理")
        raise
    finally:
        shutil.rmtree(_extract_dir(jid), ignore_errors=True)

    # 7) 重启：交给守护脚本（它会杀掉本进程）
    _set(db, job, stage="restart")
    _log(jid, "步骤 7/7 重启后端")
    if not _spawn_restart_guard(jid, target):
        _log(jid, "重启脚本启动失败，停在 awaiting_restart，请手动重启后端后点「健康校验」")
        _set(db, job, status="awaiting_restart", stage="restart")
        return
    _log(jid, f"由守护脚本做健康校验；本进程即将退出，任务最终状态最长 {VERIFY_TIMEOUT}s 内回写")
    db.commit()


def _do_rollback_artifact(db, job: UpgradeJob, restore_db: bool, skip_frontend: bool = False) -> None:
    """回滚 = 重新安装上一版产物包（不再依赖本地 git 里还留着旧 commit）。"""
    jid = job.id
    target = job.to_version
    if not VERSION_RE.match(target or ""):
        raise RuntimeError(f"回滚目标版本号无效：{target}")

    _set(db, job, stage="preflight", status="running")
    _log(jid, f"回滚模式：重新安装 {target} 产物包（当前 {job.from_version}）")
    _check_disk_space(jid)

    _set(db, job, stage="fetch")
    _log(jid, f"步骤 1/4 获取 {target} 产物包")
    rel = _find_release(target)
    pkg = _download_package(rel, jid)

    _set(db, job, stage="checkout")
    _log(jid, "步骤 2/4 解包并覆盖代码")
    try:
        root = _extract_package(pkg, jid)
        _verify_package(root, target, jid)
        _apply_package(root, jid, replace_dist=not skip_frontend)
    finally:
        shutil.rmtree(_extract_dir(jid), ignore_errors=True)
    _log(jid, "代码已回滚，VERSION=" + read_local_version())

    if restore_db:
        if not job.backup_path:
            raise RuntimeError("未找到数据库备份文件，无法恢复数据")
        _set(db, job, stage="migrate")
        _log(jid, f"步骤 3/4 恢复数据库：{job.backup_path}")
        _restore_database(job)
        _log(jid, "数据库恢复完成")
    else:
        _log(jid, "步骤 3/4 跳过数据库恢复（未勾选）")

    _set(db, job, stage="restart")
    _log(jid, "步骤 4/4 重启后端")
    if not _spawn_restart_guard(jid, target):
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
MAX_WAIT='{VERIFY_TIMEOUT}'
PID='{pid or ""}'
PY='{py}'
CUSTOM='{custom_path if custom else ""}'
UNITS='{CELERY_UNITS}'
export H='{HEALTH_URL}'
ts() {{ date '+%Y-%m-%d %H:%M:%S'; }}
say() {{ echo "[$(ts)] $*" >> "$LOG"; }}

say "重启守护脚本启动：旧 pid=${{PID:-无}}，目标版本 $TARGET"
say "健康校验最长等待 ${{MAX_WAIT}}s（面板守护自愈实测约 216s）"
rm -f '{LOCK_FILE}'
sleep 2

for u in $UNITS; do
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
SEEN=0
DEADLINE=$(( $(date +%s) + MAX_WAIT ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  ACTUAL=$("$PY" -c 'import json,os,urllib.request;d=json.load(urllib.request.urlopen(os.environ["H"],timeout=5));print((d.get("data") or dict()).get("version") or "")' 2>/dev/null)
  if [ -n "$ACTUAL" ]; then
    if [ "$SEEN" = "0" ]; then
      SEEN=1
      say "健康端点已响应（当前版本 $ACTUAL），继续等待目标版本 $TARGET"
    fi
    if [ "$ACTUAL" = "$TARGET" ]; then OK=1; break; fi
  fi
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


def _reconcile_restart_jobs(db) -> None:
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
            # 守护脚本的窗口可能不够（面板自愈偶发 >3min），结果文件是在它放弃的
            # 那一刻写的；这里通常更晚（新进程 startup 钩子），实测一次再说。
            # 只在版本精确匹配时纠正，避免把「服务起来了但代码没换」误判为成功。
            live = _probe_health()
            live_version = (live or {}).get("version")
            if live_version == job.to_version:
                job.status = "rolled_back" if job.action == "rollback" else "success"
                job.stage = "done"
                job.error = None
                _log(
                    job.id,
                    f"守护脚本窗口内未等到（回报 {actual or '无响应'}），但复核 /api/health "
                    f"实测 {live_version}，判定为成功",
                )
            else:
                job.status = "failed"
                job.stage = "done"
                job.error = (
                    f"重启后健康校验失败：期望 {job.to_version}，实际 {live_version or actual or '无响应'}；"
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


# ── 僵尸任务收尸 ─────────────────────────────────────────────────────

# pending 状态的宽限期（秒）：任务创建后线程需要一点时间接管，
# 这段时间内不能判死，否则会误杀刚点下升级的任务。
PENDING_GRACE_SECONDS = 300


def _job_created_at(job: UpgradeJob) -> datetime | None:
    """任务的创建时间近似值：优先 started_at，其次日志文件 mtime。"""
    if job.started_at is not None:
        return job.started_at
    try:
        return datetime.fromtimestamp(_log_path(job.id).stat().st_mtime)
    except OSError:
        return None


def _job_dead_reason(job: UpgradeJob) -> str | None:
    """判断一个「进行中」任务是否已是僵尸。

    判据组合（宁可漏判，不误杀）：
      1. 在本进程执行集合里 → 还活着，直接放过；
      2. 锁由另一个**存活**进程持有且未超时 → 保守放过（多 worker 场景）；
      3. 其余情况（无人持锁 / 锁持有者已退出 / 已超阶段时限）→ 判死。

    pid 存活不能单独作为「还活着」的证据（pid 会被系统复用），
    因此额外用「阶段超时」作为交叉验证。

    Returns:
        判死原因文本；仍存活时返回 None。
    """
    if job.id in _RUNNING_JOBS:
        return None

    holder = _lock_holder_pid()
    holder_is_other_alive = (
        holder is not None and holder != os.getpid() and _pid_alive(holder)
    )

    stage = job.stage or "未知"
    limit = STAGE_TIMEOUTS.get(stage, DEFAULT_STAGE_TIMEOUT)
    created = _job_created_at(job)
    elapsed = (datetime.now() - created).total_seconds() if created else None
    overtime = elapsed is not None and elapsed > limit

    if holder_is_other_alive and not overtime:
        return None
    if holder_is_other_alive and overtime:
        return f"{stage} 阶段已超过 {limit // 60} 分钟仍未结束"

    if job.status == "pending":
        if elapsed is None:
            return None  # 无任何时间线索，不动
        if elapsed <= PENDING_GRACE_SECONDS:
            return None  # 线程可能正在接管
        return f"任务创建后 {int(elapsed // 60)} 分钟仍未开始执行"

    suffix = f"，且已超过 {limit // 60} 分钟" if overtime else ""
    return f"执行进程已退出（无存活持锁者），任务停在 {stage} 阶段{suffix}"


def _release_stale_lock() -> None:
    """清掉上次进程残留的锁；仅当持锁进程确实不存在时才删。

    锁持有者是本进程或另一个存活进程时一律不动，避免把正在跑的任务锁删掉。
    """
    holder = _lock_holder_pid()
    if holder is None:
        return
    if holder == os.getpid() or _pid_alive(holder):
        return
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _reap_zombie_jobs(db) -> None:
    """把「进程已死但任务仍是 running」的任务置为 failed，解除升级/回滚阻塞。

    这是 11-02 之后补上的兜底：reconcile 原先只收 restart 阶段，其余阶段被
    中断（重启、OOM、面板重启）的任务会永久停在 running，而 create_job 与
    rollback_job 都有 active 拦截 —— 升级被挡、回滚也被挡，只能登库手改状态。
    """
    rows = db.execute(
        select(UpgradeJob).where(UpgradeJob.status.in_(ACTIVE_STATUSES))
    ).scalars().all()
    for job in rows:
        if job.stage == "restart":
            continue  # 重启阶段由 _reconcile_restart_jobs 按守护脚本结果处理
        reason = _job_dead_reason(job)
        if reason is None:
            continue
        job.status = "failed"
        job.stage = "done"
        job.error = f"任务已中止：{reason}。请查看升级日志后重试或回滚"
        job.finished_at = datetime.now()
        db.add(job)
        db.commit()
        _log(job.id, f"[收尸] {reason}；已置为 failed 以解除升级/回滚阻塞")
    _release_stale_lock()


def reconcile_jobs(db) -> None:
    """任务状态自愈入口：重启阶段收尾 + 僵尸任务收尸。

    幂等，任务接口、详情接口与服务启动钩子都可以反复调用。
    """
    _reconcile_restart_jobs(db)
    _reap_zombie_jobs(db)


# 兼容旧调用点（api_upgrade.py / main.py 已改用 reconcile_jobs）
def reconcile_restarts(db) -> None:
    """已废弃别名，等价于 reconcile_jobs()。"""
    reconcile_jobs(db)


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
    if upgrade_mode() == "git":
        if not src.from_ref:
            raise ValueError("该任务没有记录回滚点（from_ref），无法回滚")
        if working_tree_dirty():
            raise ValueError("工作区有未提交改动，请先提交或 stash 后再回滚")
    else:
        target_ver = src.from_version
        if not VERSION_RE.match(target_ver or ""):
            raise ValueError(f"该任务未记录升级前版本号（{target_ver or '空'}），无法确定回滚目标")
        if not _pick_asset(_find_release(target_ver), ".tar.gz"):
            raise ValueError(f"{target_ver} 的 Release 里没有产物包，无法回滚到该版本")

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


def force_fail_job(db, job_id: int, reason: str = "", operator: str = "-") -> UpgradeJob:
    """人工把卡住的任务强制置为失败，解除升级/回滚阻塞。

    正常路径下 _reap_zombie_jobs 会自动收尸，本函数只用于自动判定失灵时
    （例如锁被外部进程长期占用）的紧急解锁，避免只能登库改状态。

    Raises:
        ValueError: 任务不存在，或当前状态本就不是「进行中」。
    """
    job = db.get(UpgradeJob, job_id)
    if job is None:
        raise ValueError("任务不存在")
    if job.status not in ACTIVE_STATUSES:
        raise ValueError(f"任务 #{job_id} 当前状态为 {job.status}，无需强制结束")
    job.status = "failed"
    job.stage = "done"
    job.error = (reason.strip() or "由管理员强制结束")[:2000]
    job.finished_at = datetime.now()
    db.add(job)
    db.commit()
    _log(job_id, f"[强制结束] 操作人={operator}；{job.error}")
    _release_stale_lock()
    return job


def verify_job(db, job_id: int) -> dict:
    """健康校验入口：awaiting_restart 定终态，或纠正守护窗口误判的 failed。

    纠正 failed 有严格前提，防止把真失败的任务洗成成功：
      1. 实测 /api/health 版本必须精确等于 ``job.to_version``；
      2. 任务必须真的走到过重启守护阶段（结果文件存在、stage 已是 done）；
      3. 只纠正状态与错误文案，不触碰任何代码、数据库备份或日志。

    Args:
        db: 数据库会话。
        job_id: 任务号。

    Returns:
        含 job_id / expected / actual / healthy / status / corrected 的字典。

    Raises:
        ValueError: 任务不存在。
    """
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
        "corrected": False,
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
    elif job.status == "failed" and ok_ and job.stage == "done":
        # 结果文件是「走到过重启阶段」的物证；失败在 checkout / 备份阶段的任务
        # 没有它，即使版本号碰巧一致也不会被误纠正。
        if _read_restart_result(_restart_result_path(job.id)) is not None:
            job.status = "rolled_back" if job.action == "rollback" else "success"
            job.stage = "done"
            job.error = None
            job.finished_at = datetime.now()
            _log(job.id, f"人工健康校验纠正误判：实测版本 {actual}，任务状态改为 {job.status}")
            db.commit()
            result["status"] = job.status
            result["corrected"] = True
    return result
