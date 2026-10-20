# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展事件钩子：通知型（commit 后异步）+ 拦截型（commit 前同步）。

与 ``services/notify_dispatcher`` 的飞书 event_code 体系是**两个独立注册表**：
命名词汇对齐（如 ``report.submitted``），但本总线纯内存、不写任何表，
notify_dispatcher 行为零改动；反之飞书事件也不会进入本总线。

通知型 ``emit_after_commit``：
    emit 时刻物化 Event（payload 只允许 JSON 原语，Decimal/datetime 自动转字符串，
    **禁止 ORM 对象**——handler 在 commit 后于另一线程执行，请求 session 已失效），
    事务 commit 成功后投总线自有线程池分发；回滚不发。handler 异常逐个隔离，
    绝不影响核心业务。

拦截型 ``intercept``：
    commit 前在请求线程同步执行（经线程池以获得超时能力），**fail-open**——
    handler 异常 / 超时 / 扩展被禁用一律放行并记日志。多扩展不短路，
    全部执行后合并否决原因。拦截 handler 必须只读、必须秒回，
    且**看不到本次请求未提交的数据**（只能读已提交状态 + payload）。

扩展接入：在 ``router.py`` 可选导出 ``register_events(bus: EventBus)``，
由 loader 在模块加载后调用（先按 key 反注册，热重载幂等）。
**register_events 在 import 期被调用，不得做 DB/网络 IO。**
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

from .state import runtime

logger = logging.getLogger("uvicorn.error")


class Phase(str, Enum):
    NOTIFY = "notify"          # commit 后异步分发
    INTERCEPT = "intercept"    # commit 前同步分发


@dataclass(frozen=True)
class Event:
    name: str
    phase: Phase
    payload: dict
    actor_id: int | None = None
    tenant_id: int | None = None
    occurred_at: str = ""
    trace_id: str = ""


@dataclass(frozen=True)
class InterceptDecision:
    """拦截 handler 的返回值；返回 None 等同 allow=True。"""

    allow: bool = True
    reason: str = ""  # allow=False 时必填，会原样拼进 API 错误文案


@dataclass
class InterceptResult:
    allowed: bool
    rejections: list[tuple[str, str]] = field(default_factory=list)  # [(ext_key, reason)]
    errors: list[tuple[str, str]] = field(default_factory=list)      # fail-open 留痕 [(ext_key, error)]

    def http_detail(self) -> str:
        parts = "；".join(f"[{key}] {reason}" for key, reason in self.rejections)
        return f"扩展拦截：{parts}"


NotifyHandler = Callable[[Event], None]
InterceptHandler = Callable[[Event], "InterceptDecision | None"]


@dataclass
class _Sub:
    key: str
    handler: Callable
    phase: Phase
    timeout: float | None = None


# 事件契约表（稳定契约，只增不改）。字段说明供扩展开发者与文档生成使用。
EVENT_CATALOG: dict[str, dict] = {
    # ── 拦截型（commit 前，可否决）──
    "report.submitting": {
        "phase": Phase.INTERCEPT,
        "payload": {"report_id": "报工ID", "task_id": "任务ID", "task_code": "任务编码",
                    "report_user_id": "报工人", "good_qty": "合格数", "bad_qty": "不良数", "remark": "备注"},
    },
    "report_unit.submitting": {
        "phase": Phase.INTERCEPT,
        "payload": {"report_unit_id": "单件报工ID", "task_id": "任务ID", "task_code": "任务编码",
                    "unit_seq": "件序号", "piece_id": "追溯码ID", "result_type": "结果类型", "user_id": "报工人"},
    },
    # ── 通知型（commit 后，只读+副作用）──
    "order.created": {
        "phase": Phase.NOTIFY,
        "payload": {"order_id": "订单ID", "code": "订单号", "customer_id": "客户ID",
                    "item_count": "行数", "total_qty": "总数量", "amount": "金额(str)"},
    },
    "order.confirmed": {
        "phase": Phase.NOTIFY,
        "payload": {"order_id": "订单ID", "code": "订单号", "customer_id": "客户ID"},
    },
    "order.rejected": {
        "phase": Phase.NOTIFY,
        "payload": {"order_id": "订单ID", "code": "订单号", "reason": "驳回原因"},
    },
    "plan.created": {
        "phase": Phase.NOTIFY,
        "payload": {"plan_id": "计划ID", "order_id": "订单ID", "code": "计划号"},
    },
    "plan.auto_scheduled": {
        "phase": Phase.NOTIFY,
        "payload": {"plan_id": "计划ID", "mode": "backward/forward",
                    "start_date": "开始日期(ISO)", "end_date": "结束日期(ISO)"},
    },
    "plan.auto_dispatched": {
        "phase": Phase.NOTIFY,
        "payload": {"plan_id": "计划ID", "dispatched_count": "成功派工任务数", "task_count": "候选任务总数"},
    },
    "plan.released": {
        "phase": Phase.NOTIFY,
        "payload": {"plan_id": "计划ID"},
    },
    "task.assignments_set": {
        "phase": Phase.NOTIFY,
        "payload": {"task_id": "任务ID", "task_code": "任务编码",
                    "assignments": "[{user_id, assigned_qty}]"},
    },
    "report.submitted": {
        "phase": Phase.NOTIFY,
        "payload": {"report_id": "报工ID", "task_id": "任务ID", "task_code": "任务编码",
                    "report_user_id": "报工人", "good_qty": "合格数", "bad_qty": "不良数", "remark": "备注"},
    },
    "report_unit.submitted": {
        "phase": Phase.NOTIFY,
        "payload": {"report_unit_id": "单件报工ID", "task_id": "任务ID", "task_code": "任务编码",
                    "unit_seq": "件序号", "piece_id": "追溯码ID", "result_type": "结果类型",
                    "user_id": "报工人", "anomaly_confirmed": "异常确认"},
    },
    "report.leader_approved": {
        "phase": Phase.NOTIFY,
        "payload": {"report_id": "报工ID", "task_id": "任务ID", "approver_id": "班组长ID"},
    },
    "report.qc_approved": {
        "phase": Phase.NOTIFY,
        "payload": {"report_id": "报工ID", "task_id": "任务ID", "approver_id": "审核人ID",
                    "salary_item_ids": "生成的计件工资项ID列表"},
    },
    "report.rejected": {
        "phase": Phase.NOTIFY,
        "payload": {"report_id": "报工ID", "task_id": "任务ID", "approver_id": "审核人ID", "reason": "驳回原因"},
    },
    "report_unit.approved": {
        "phase": Phase.NOTIFY,
        "payload": {"report_unit_id": "单件报工ID", "task_id": "任务ID", "approver_id": "审核人ID",
                    "salary_item_id": "计件工资项ID", "piece_id": "追溯码ID", "stage": "审核阶段(qc=终审)"},
    },
    "report_unit.rejected": {
        "phase": Phase.NOTIFY,
        "payload": {"report_unit_id": "单件报工ID", "task_id": "任务ID", "approver_id": "审核人ID",
                    "reason": "驳回原因"},
    },
    "salary.time_items_generated": {
        "phase": Phase.NOTIFY,
        "payload": {"date_from": "开始日期", "date_to": "结束日期", "item_count": "生成条数", "total_amount": "总额(str)"},
    },
    "salary.slip_paid": {
        "phase": Phase.NOTIFY,
        "payload": {"month": "月份", "slip_ids": "工资条ID列表", "user_ids": "员工ID列表", "total_amount": "总额(str)"},
    },
    "salary.slip_signed": {
        "phase": Phase.NOTIFY,
        "payload": {"slip_id": "工资条ID", "user_id": "员工ID", "action": "sign/reject"},
    },
    # ── qcode 一物一码（扩展动态注册，此处声明供文档与 warning 过滤）──
    "qcode.scanned": {
        "phase": Phase.NOTIFY,
        "payload": {"tenant_id": "租户ID", "item_id": "码ID", "sn": "SN编码", "source": "来源"},
    },
    "qcode.form_submitted": {
        "phase": Phase.NOTIFY,
        "payload": {"tenant_id": "租户ID", "item_id": "码ID", "form_id": "表单ID", "submission_id": "提交ID"},
    },
    "qcode.status_changed": {
        "phase": Phase.NOTIFY,
        "payload": {"tenant_id": "租户ID", "item_id": "码ID", "from_status": "原状态", "to_status": "新状态"},
    },
    "qcode.item_voided": {
        "phase": Phase.NOTIFY,
        "payload": {"tenant_id": "租户ID", "item_id": "码ID", "sn": "SN编码", "reason": "作废原因"},
    },
    "qcode.approved": {
        "phase": Phase.NOTIFY,
        "payload": {"tenant_id": "租户ID", "submission_id": "提交ID", "approver_id": "审批人"},
    },
    "qcode.rejected": {
        "phase": Phase.NOTIFY,
        "payload": {"tenant_id": "租户ID", "submission_id": "提交ID", "approver_id": "审批人", "reason": "驳回原因"},
    },
    "qcode.inspection_due": {
        "phase": Phase.NOTIFY,
        "payload": {"tenant_id": "租户ID", "task_id": "巡检任务ID", "item_id": "码ID", "due_at": "到期时间"},
    },
    "qcode.inspection_overdue": {
        "phase": Phase.NOTIFY,
        "payload": {"tenant_id": "租户ID", "task_id": "巡检任务ID", "item_id": "码ID"},
    },
}


def _sanitize(value: Any) -> Any:
    """payload 物化为 JSON 原语；遇到 ORM 对象等非法类型抛 TypeError（由 emit 兜底吞掉）。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"payload 禁止非原语类型: {type(value).__name__}（ORM 对象请改为传 ID）")


class EventBus:
    """进程内扩展事件总线（纯内存，无持久化）。"""

    def __init__(self, max_workers: int = 4):
        self._subs: dict[str, list[_Sub]] = {}
        self._lock = threading.Lock()
        self._pending: set[Future] = set()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ext-evt")
        # 测试可 monkeypatch 此工厂；None 时 open_session() 延迟导入核心 SessionLocal
        self.session_factory: Callable[[], Session] | None = None

    # ---------- 订阅 ----------

    def subscribe(self, key: str, event_name: str, handler: NotifyHandler) -> None:
        self._add(_Sub(key=key, handler=handler, phase=Phase.NOTIFY), event_name)

    def subscribe_intercept(
        self, key: str, event_name: str, handler: InterceptHandler, *, timeout: float | None = None,
    ) -> None:
        self._add(_Sub(key=key, handler=handler, phase=Phase.INTERCEPT, timeout=timeout), event_name)

    def _add(self, sub: _Sub, event_name: str) -> None:
        if event_name not in EVENT_CATALOG:
            logger.warning("[ext-event] 订阅了未收录的事件名: %s（key=%s）", event_name, sub.key)
        with self._lock:
            subs = self._subs.setdefault(event_name, [])
            # 同 key+handler 幂等去重（热重载由 unsubscribe-first 兜底，这里防同包重复调用）
            # == 而非 is：绑定方法（如 list.append）每次属性访问产生新对象，但 == 按 __self__+__func__ 相等
            if any(s.key == sub.key and s.handler == sub.handler and s.phase == sub.phase for s in subs):
                return
            subs.append(sub)

    def unsubscribe_extension(self, key: str) -> int:
        """摘除某扩展的全部订阅，返回数量（热重载/禁用卸载/测试隔离用）。"""
        removed = 0
        with self._lock:
            for name in list(self._subs):
                before = len(self._subs[name])
                self._subs[name] = [s for s in self._subs[name] if s.key != key]
                removed += before - len(self._subs[name])
                if not self._subs[name]:
                    del self._subs[name]
        return removed

    # ---------- 发射 ----------

    def emit_after_commit(
        self, db: Session, event_name: str, payload: dict, *,
        actor_id: int | None = None, tenant_id: int | None = None, trace_id: str = "",
    ) -> None:
        """commit 成功后分发；回滚不发。任何内部错误只记日志，绝不上抛影响业务。"""
        try:
            ev = self._make_event(event_name, payload, Phase.NOTIFY, actor_id, tenant_id, trace_id)
        except Exception:
            logger.exception("[ext-event] %s payload 物化失败，事件丢弃", event_name)
            return
        try:
            if not db.in_transaction():
                # 调用方已 commit（或无事务上下文），立即分发
                self._dispatch(ev)
                return
            sa_event.listen(db, "after_commit", lambda _s: self._dispatch(ev), once=True)
        except Exception:
            logger.exception("[ext-event] %s 注册 after_commit 失败", event_name)

    def emit_now(
        self, event_name: str, payload: dict, *,
        actor_id: int | None = None, tenant_id: int | None = None, trace_id: str = "",
    ) -> None:
        """立即异步分发（无事务上下文 / 测试用）。错误只记日志。"""
        try:
            ev = self._make_event(event_name, payload, Phase.NOTIFY, actor_id, tenant_id, trace_id)
        except Exception:
            logger.exception("[ext-event] %s payload 物化失败，事件丢弃", event_name)
            return
        self._dispatch(ev)

    def _make_event(
        self, name: str, payload: dict, phase: Phase,
        actor_id: int | None, tenant_id: int | None, trace_id: str,
    ) -> Event:
        return Event(
            name=name,
            phase=phase,
            payload=_sanitize(payload or {}),
            actor_id=actor_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now().isoformat(timespec="seconds"),
            trace_id=trace_id,
        )

    # ---------- 通知分发 ----------

    def _snapshot(self, event_name: str, phase: Phase) -> list[_Sub]:
        with self._lock:
            return [s for s in self._subs.get(event_name, []) if s.phase == phase]

    def _dispatch(self, ev: Event) -> None:
        for sub in self._snapshot(ev.name, Phase.NOTIFY):
            # 分发时 gating：运行期禁用/吊销即时生效（订阅时不检查）
            if not runtime.is_enabled(sub.key):
                continue
            try:
                future = self._executor.submit(self._safe_call, sub, ev)
            except RuntimeError:
                logger.error("[ext-event] 线程池已关闭，%s 分发中止", ev.name)
                return
            self._track(future)

    def _safe_call(self, sub: _Sub, ev: Event) -> None:
        started = time.monotonic()
        try:
            sub.handler(ev)
        except Exception as e:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            event_recorder.record(ev, sub.key, ok=False, allowed=None,
                                  elapsed_ms=elapsed_ms, error=repr(e))
            logger.exception("[ext-event] %s handler 失败（key=%s），已隔离", ev.name, sub.key)
        else:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            event_recorder.record(ev, sub.key, ok=True, allowed=None, elapsed_ms=elapsed_ms)
            if elapsed_ms > 3000:
                logger.warning("[ext-event] %s handler 耗时 %.1fs（key=%s），请移入异步任务",
                               ev.name, elapsed_ms / 1000, sub.key)

    def _track(self, future: Future) -> None:
        with self._lock:
            self._pending.add(future)
        future.add_done_callback(self._untrack)

    def _untrack(self, future: Future) -> None:
        with self._lock:
            self._pending.discard(future)

    def wait_pending(self, timeout: float = 5.0) -> bool:
        """等待全部通知 handler 执行完毕（测试用）。返回是否清空。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if not self._pending:
                    return True
            time.sleep(0.01)
        return False

    # ---------- 拦截 ----------

    def intercept(
        self, event_name: str, payload: dict, *,
        actor_id: int | None = None, tenant_id: int | None = None, trace_id: str = "",
    ) -> InterceptResult:
        """commit 前同步执行拦截 handler。fail-open：异常/超时/禁用一律放行。

        handler 经线程池提交再 future.result(timeout=…)——不是为了并发，而是为了可超时。
        超时的 handler 线程杀不掉，任其后台跑完（约定拦截 handler 只读，最坏是白跑）。
        """
        from app.core.config import settings

        try:
            ev = self._make_event(event_name, payload, Phase.INTERCEPT, actor_id, tenant_id, trace_id)
        except Exception:
            logger.exception("[ext-event] %s payload 物化失败，fail-open 放行", event_name)
            return InterceptResult(allowed=True, errors=[("<bus>", "payload 物化失败")])

        rejections: list[tuple[str, str]] = []
        errors: list[tuple[str, str]] = []
        for sub in self._snapshot(event_name, Phase.INTERCEPT):
            if not runtime.is_enabled(sub.key):
                continue
            timeout = sub.timeout or settings.EXTENSION_HOOK_TIMEOUT
            started = time.monotonic()
            try:
                future = self._executor.submit(sub.handler, ev)
            except RuntimeError:
                errors.append((sub.key, "线程池已关闭"))
                event_recorder.record(ev, sub.key, ok=False, allowed=True,
                                      elapsed_ms=0, error="线程池已关闭")
                continue
            try:
                decision = future.result(timeout=timeout)
            except FuturesTimeout:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                errors.append((sub.key, f"超时(>{timeout}s)，fail-open 放行"))
                event_recorder.record(ev, sub.key, ok=False, allowed=True,
                                      elapsed_ms=elapsed_ms, error=f"超时(>{timeout}s)")
                logger.error("[ext-event] %s 拦截 handler 超时（key=%s，>%.1fs），fail-open 放行",
                             event_name, sub.key, timeout)
                continue
            except Exception as e:  # noqa: BLE001 - fail-open：扩展故障不阻断生产
                elapsed_ms = int((time.monotonic() - started) * 1000)
                errors.append((sub.key, repr(e)))
                event_recorder.record(ev, sub.key, ok=False, allowed=True,
                                      elapsed_ms=elapsed_ms, error=repr(e))
                logger.exception("[ext-event] %s 拦截 handler 异常（key=%s），fail-open 放行", event_name, sub.key)
                continue
            elapsed_ms = int((time.monotonic() - started) * 1000)
            rejected = decision is not None and not decision.allow
            if rejected:
                reason = decision.reason or "未提供原因"
                rejections.append((sub.key, reason))
                event_recorder.record(ev, sub.key, ok=True, allowed=False,
                                      elapsed_ms=elapsed_ms, reason=reason)
            else:
                event_recorder.record(ev, sub.key, ok=True, allowed=True,
                                      elapsed_ms=elapsed_ms)
        return InterceptResult(allowed=not rejections, rejections=rejections, errors=errors)

    # ---------- 取数 ----------

    @contextmanager
    def open_session(self):
        """handler 专用独立 session（不共享请求 session）。用完自动 close。"""
        factory = self.session_factory
        if factory is None:
            from app.core.db import SessionLocal as factory  # noqa: PLW0127 - 延迟导入避免环
        db = factory()
        try:
            yield db
        finally:
            db.close()

    # ---------- 生命周期 ----------

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

    def reset(self) -> None:
        """清空全部订阅（测试隔离；由 ExtensionRuntime.reset() 联动调用）。"""
        with self._lock:
            self._subs.clear()

    # ---------- 可视化读接口 ----------

    def snapshot_subscriptions(self) -> list[dict]:
        """枚举全部订阅：[{event_name, key, phase, timeout, handler}]，供管理端可视化。"""
        with self._lock:
            return [
                {
                    "event_name": name,
                    "key": s.key,
                    "phase": s.phase.value,
                    "timeout": s.timeout,
                    "handler": getattr(s.handler, "__qualname__", repr(s.handler)),
                    "in_catalog": name in EVENT_CATALOG,
                }
                for name, subs in self._subs.items()
                for s in subs
            ]

    def catalog(self) -> dict[str, dict]:
        """返回 EVENT_CATALOG 浅拷贝（phase 转字符串）。"""
        return {
            name: {"phase": meta["phase"].value, "payload": meta["payload"]}
            for name, meta in EVENT_CATALOG.items()
        }


@dataclass(frozen=True)
class DispatchRecord:
    """单条 handler 执行结果（通知型或拦截型）。"""

    seq: int                # 单调递增序号
    occurred_at: str        # ISO 时间
    event_name: str
    ext_key: str
    phase: str              # "notify" | "intercept"
    ok: bool                # handler 是否正常返回（拦截场景：是否未抛异常）
    allowed: bool | None    # 仅 intercept 有值：True/False/None(notify)
    elapsed_ms: int
    error: str = ""         # 异常 repr 或超时说明，正常为空
    reason: str = ""        # 拦截否决原因（allow=False 时）
    tenant_id: int | None = None
    actor_id: int | None = None
    trace_id: str = ""


class EventRecorder:
    """进程内环形缓冲，记录最近 N 条 handler 执行结果。重启清零，无持久化。"""

    def __init__(self, capacity: int = 200):
        self._buf: deque[DispatchRecord] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._seq = 0

    def record(
        self, ev: Event, ext_key: str, *, ok: bool, allowed: bool | None,
        elapsed_ms: int, error: str = "", reason: str = "",
    ) -> None:
        with self._lock:
            self._seq += 1
            self._buf.append(DispatchRecord(
                seq=self._seq, occurred_at=ev.occurred_at, event_name=ev.name,
                ext_key=ext_key, phase=ev.phase.value, ok=ok, allowed=allowed,
                elapsed_ms=elapsed_ms, error=error, reason=reason,
                tenant_id=ev.tenant_id, actor_id=ev.actor_id, trace_id=ev.trace_id,
            ))

    def snapshot(
        self, limit: int = 100, event_name: str | None = None,
        ext_key: str | None = None, phase: str | None = None,
    ) -> list[DispatchRecord]:
        with self._lock:
            items = list(self._buf)
        if phase:
            items = [r for r in items if r.phase == phase]
        if event_name:
            items = [r for r in items if r.event_name == event_name]
        if ext_key:
            items = [r for r in items if r.ext_key == ext_key]
        return list(reversed(items[-limit:]))  # 最新在前

    def stats(self) -> dict[str, dict]:
        """按 (event_name, ext_key) 聚合：total / errors / slow(>3s) / rejections / last_at。"""
        with self._lock:
            items = list(self._buf)
        out: dict[str, dict] = {}
        for r in items:
            k = f"{r.event_name}|{r.ext_key}"
            s = out.setdefault(k, {
                "event_name": r.event_name, "ext_key": r.ext_key,
                "phase": r.phase, "total": 0, "errors": 0,
                "slow": 0, "rejections": 0, "last_at": r.occurred_at,
            })
            s["total"] += 1
            if not r.ok:
                s["errors"] += 1
            if r.elapsed_ms > 3000:
                s["slow"] += 1
            if r.allowed is False:
                s["rejections"] += 1
        return out

    def reset(self) -> None:
        with self._lock:
            self._buf.clear()
            self._seq = 0


event_bus = EventBus()
event_recorder = EventRecorder()
