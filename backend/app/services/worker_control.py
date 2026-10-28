# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""Celery Worker / Beat 运维（管理后台「定时任务」页）。

Worker 重启：经 celery 控制通道广播 `shutdown`，worker 跑完在飞任务后优雅退出，
由进程管理器（systemd，Restart=always）拉起新代码。web 层不直接 kill 进程；按
`CELERY_WORKER_PREFIX` 主机名前缀定向，不会误伤同机其它项目的 worker。

Beat 重启：往 Redis 写退出信号（`celery:beat:shutdown`）。Beat 的
DatabaseScheduler 每 10 秒检查一次信号，收到后自行退出，由 systemd
（Restart=always）拉起新进程。web 与 Beat 同机共享 REDIS_URL，全程不需要
systemctl 写权限（不依赖 polkit/sudo），且 Beat 未运行时拒绝重启而不是误报成功。
"""

from __future__ import annotations

import re
import subprocess
import time
from datetime import datetime

import redis as redis_lib

from app.celery_app import celery
from app.core.config import settings
from app.schedulers.database import SHUTDOWN_KEY

DEFAULT_TIMEOUT = 4.0
# systemctl show 的超时（秒），避免 web 请求被阻塞过久
BEAT_SYSTEMCTL_TIMEOUT = 5.0
# 退出信号发出后等待新进程上线的轮询上限（beat 每 ~10s 检查信号 + systemd 拉起耗时）。
# 必须低于现网 nginx 的 proxy_read_timeout（60s），否则失败场景会先被 nginx 掐成 504，
# 用户看不到后端返回的明确错误信息。
BEAT_RESTART_WAIT_TIMEOUT = 45.0
# 退出信号的自毁 TTL（秒）：Beat 失联时残留信号不应对未来的启动生效
BEAT_SHUTDOWN_SIGNAL_TTL = 120

_SYSTEMD_TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")


def _worker_prefix() -> str:
    """托管 Worker 的主机名前缀；留空表示本实例不使用 Worker 管理。"""
    return (settings.CELERY_WORKER_PREFIX or "").strip()


def _worker_service() -> str:
    return (settings.CELERY_WORKER_SERVICE or "").strip()


def _beat_unit() -> str:
    return (settings.BEAT_SERVICE_NAME or "").strip()


def _parse_systemd_time(raw: str | None) -> datetime | None:
    """解析 systemd 时间串（如 `Tue 2026-10-20 08:00:00 CST`）为本地 naive datetime。

    用正则提取日期时间部分，避开 %a/%Z 的 locale 兼容问题；失败返回 None。
    """
    m = _SYSTEMD_TIME_RE.search(raw or "")
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _online_workers(timeout: float) -> list[str]:
    replies = celery.control.inspect(timeout=timeout).ping() or {}
    hosts = sorted(str(h) for h in replies)
    prefix = _worker_prefix()
    # 前缀为空时不做全量托管，避免 shutdown 广播误伤同 broker 的其它项目
    if not prefix:
        return []
    return [h for h in hosts if h.startswith(prefix)]


def get_worker_status(timeout: float = DEFAULT_TIMEOUT) -> dict:
    """worker 在线状态与正在执行的任务；broker 异常返回 ok=False 而不抛出。"""
    server_time = datetime.now().isoformat(timespec="seconds")
    prefix = _worker_prefix()
    if not prefix:
        return {
            "ok": True,
            "workers": [],
            "prefix": "",
            "configured": False,
            "service": _worker_service(),
            "server_time": server_time,
        }
    try:
        hosts = _online_workers(timeout)
        active: dict = {}
        if hosts:
            active = celery.control.inspect(timeout=timeout).active() or {}
    except Exception as e:
        return {
            "ok": False,
            "error": f"无法连接消息队列：{e}",
            "workers": [],
            "prefix": prefix,
            "configured": True,
            "service": _worker_service(),
            "server_time": server_time,
        }

    workers = []
    for host in hosts:
        tasks = active.get(host) or []
        workers.append(
            {
                "hostname": host,
                "active_count": len(tasks),
                "active_tasks": [
                    {"name": t.get("name"), "time_start": t.get("time_start")} for t in tasks[:5]
                ],
            }
        )
    return {
        "ok": True,
        "workers": workers,
        "prefix": prefix,
        "configured": True,
        "service": _worker_service(),
        "server_time": server_time,
    }


def request_worker_restart(timeout: float = DEFAULT_TIMEOUT) -> dict:
    """广播优雅停机（进程管理器自动拉起）。返回 {ok, hosts} 或 {ok: False, error}。"""
    prefix = _worker_prefix()
    if not prefix:
        return {
            "ok": False,
            "error": "未配置 Worker 主机名前缀（CELERY_WORKER_PREFIX），Worker 管理已停用",
        }
    try:
        hosts = _online_workers(timeout)
        if not hosts:
            service = _worker_service() or "celery worker"
            return {
                "ok": False,
                "error": f"未发现在线的 Worker（{prefix}…），请检查 systemctl status {service}",
            }
        celery.control.broadcast("shutdown", destination=hosts, reply=False)
    except Exception as e:
        return {"ok": False, "error": f"重启指令发送失败：{e}"}
    return {"ok": True, "hosts": hosts}


def get_beat_status(timeout: float = BEAT_SYSTEMCTL_TIMEOUT) -> dict:
    """Beat（systemd 单元）状态；systemctl 不可用等异常一律降级 unknown 而不抛出。"""
    unit = _beat_unit()
    if not unit:
        return {
            "active": False,
            "state": "disabled",
            "started_at": None,
            "uptime_seconds": None,
            "unit": "",
            "configured": False,
            "installed": False,
            "load_state": "",
        }

    info: dict[str, str] = {}
    try:
        proc = subprocess.run(
            [
                "systemctl", "show", unit,
                "-p", "LoadState", "-p", "ActiveState", "-p", "SubState",
                "-p", "UnitFileState", "-p", "ActiveEnterTimestamp",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        for line in proc.stdout.splitlines():
            key, sep, value = line.partition("=")
            if sep:
                info[key.strip()] = value.strip()
    except Exception:
        return {
            "active": False,
            "state": "unknown",
            "started_at": None,
            "uptime_seconds": None,
            "unit": unit,
            "configured": True,
            "installed": None,
            "load_state": "",
        }

    state = info.get("ActiveState") or "unknown"
    load_state = info.get("LoadState") or ""
    started_at: str | None = None
    uptime_seconds: int | None = None
    started_dt = _parse_systemd_time(info.get("ActiveEnterTimestamp"))
    if state == "active":
        if started_dt:
            started_at = started_dt.isoformat(timespec="seconds")
            uptime_seconds = max(0, int((datetime.now() - started_dt).total_seconds()))
        else:
            # 解析失败原样透传原始串，前端尽力显示
            started_at = info.get("ActiveEnterTimestamp")
    return {
        "active": state == "active",
        "state": state,
        "started_at": started_at,
        "uptime_seconds": uptime_seconds,
        "unit": unit,
        "configured": True,
        "installed": load_state != "not-found",
        "load_state": load_state,
    }


def request_beat_restart(timeout: float = BEAT_RESTART_WAIT_TIMEOUT) -> dict:
    """写 Redis 退出信号让 Beat 自行退出，由 systemd（Restart=always）拉起新进程。

    信号只对**运行中**的 Beat 有效（DatabaseScheduler.tick 每 ~10s 检查）；
    Beat 未运行时直接报错，由运维在服务器上手动启动。返回 {ok, unit, started_at}。
    """
    unit = _beat_unit()
    if not unit:
        return {"ok": False, "error": "未配置 Beat 单元名（BEAT_SERVICE_NAME），Beat 管理已停用"}
    before = get_beat_status()
    if not before.get("active"):
        if before.get("installed") is False:
            return {"ok": False, "error": f"Beat 单元 {unit} 未安装（systemd LoadState=not-found）"}
        state = before.get("state") or "unknown"
        return {
            "ok": False,
            "error": f"Beat 未运行（state={state}），信号方式无法拉起停机的 Beat，请在服务器上手动启动",
        }
    old_started_at = before.get("started_at")
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            r.set(SHUTDOWN_KEY, "1", ex=BEAT_SHUTDOWN_SIGNAL_TTL)
        finally:
            r.close()
    except Exception as e:
        return {"ok": False, "error": f"无法连接 Redis 发送退出信号：{e}"}

    # beat 每 ~10s 检查一次信号；轮询等待新进程上线（started_at 变化）
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(2.0)
        st = get_beat_status()
        if st.get("active") and st.get("started_at") and st.get("started_at") != old_started_at:
            return {"ok": True, "unit": unit, "started_at": st["started_at"]}
    # 等不到新进程 = 重启失败。清掉残留信号：旧调度器不认识该信号，若不清理，
    # 之后手动/其它途径拉起的新 Beat 会在 TTL 内读到信号并立刻再退一次。
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            r.delete(SHUTDOWN_KEY)
        finally:
            r.close()
    except Exception:
        pass
    return {
        "ok": False,
        "error": f"退出信号已发送，但 {int(timeout)} 秒内未检测到 Beat 新进程，请稍后在页面刷新 Beat 状态",
    }
