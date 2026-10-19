# 演示扩展：事件钩子（hook_demo）
# 挂载路径前缀：/api/extensions/hook_demo/
#
# 本样例展示扩展如何「挂到核心业务上」，而不是只做独立功能：
#   - 通知型 report.submitted：每次报工提交（commit 成功）后，往扩展自有表写一行统计。
#   - 拦截型 report.submitting：报工提交（commit 之前）同步校验，可否决本次提交。
#
# 四条铁律（详见 docs/EXTENSIONS.md 第十章）：
#   1. register_events 在「模块导入期」被调用 —— 只做订阅，禁止任何 DB / 网络 IO。
#   2. 通知 handler 在 commit 后于「另一线程」执行，请求 session 已失效 ——
#      取数一律用 bus.open_session()（独立 session），绝不要触碰请求 session。
#   3. payload 只含 JSON 原语（ID / 数量 / 字符串），拿不到 ORM 对象；
#      需要详情就按 payload 里的 ID 回查。
#   4. 拦截 handler 必须「只读 + 秒回」（默认 5s 预算，超时 fail-open 放行），
#      且看不到本次请求尚未提交的数据 —— 判断依据只能是 payload + 已提交状态。
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.response import ok
from app.extension_host.events import EventBus, InterceptDecision

router = APIRouter()


@router.get("/ping")
def ping():
    """扩展存活检查。"""
    return ok({"ok": True, "extension": "hook_demo"})


@router.get("/report-log")
def list_report_log(db: Session = Depends(get_db)):
    """读取本扩展记录的报工统计（由 report.submitted 钩子写入 ext_hook_demo_report_log）。"""
    rows = db.execute(
        text(
            "SELECT id, task_code, report_id, good_qty, bad_qty, logged_at "
            "FROM ext_hook_demo_report_log ORDER BY id DESC LIMIT 50"
        )
    ).mappings().all()
    return ok({"items": [dict(r) for r in rows]})


def register_events(bus: EventBus) -> None:
    """订阅核心业务事件。宿主在扩展加载期调用一次；热重载会先按 key 反注册再调用本函数。

    这里只创建闭包并登记订阅，不做任何 IO —— 真正的 DB 访问发生在事件触发时。
    """

    def on_report_submitted(event) -> None:
        # 通知型：commit 后于后台线程执行。用独立 session 写自有表；
        # 若此处抛异常，总线会逐个隔离并记日志，绝不影响已提交的核心业务。
        p = event.payload
        with bus.open_session() as db:
            db.execute(
                text(
                    "INSERT INTO ext_hook_demo_report_log "
                    "(task_code, report_id, good_qty, bad_qty, logged_at) "
                    "VALUES (:tc, :rid, :g, :b, CURRENT_TIMESTAMP)"
                ),
                {
                    "tc": str(p.get("task_code") or ""),
                    "rid": int(p.get("report_id") or 0),
                    "g": int(p.get("good_qty") or 0),
                    "b": int(p.get("bad_qty") or 0),
                },
            )
            db.commit()

    def guard_report_submitting(event):
        # 拦截型：commit 前同步执行。返回 InterceptDecision(allow=False) 即否决本次报工，
        # 否决原因会原样拼进 API 错误文案（HTTP 200 + body.code=400）。返回 None 即放行。
        # 演示规则：报工含不良品（bad_qty>0）却未填备注 → 拦下，要求说明原因。
        p = event.payload
        bad = int(p.get("bad_qty") or 0)
        remark = str(p.get("remark") or "").strip()
        if bad > 0 and not remark:
            return InterceptDecision(allow=False, reason=f"报工含 {bad} 件不良品，必须在备注中说明原因")
        return None

    bus.subscribe("hook_demo", "report.submitted", on_report_submitted)
    bus.subscribe_intercept("hook_demo", "report.submitting", guard_report_submitting)
