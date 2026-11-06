# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""不良品处置：额度校验 / 状态机 / 不越界改库存与报工

这个功能最容易做错的三件事，各钉一到两个用例：

1. **同一批不良不能被处置两次**。额度以报工 `bad_qty` 为上限，
   已驳回/已作废的单据不占额度（见 test_capacity_* / test_rejected_releases_capacity）。
2. **状态机单向**：draft → pending → approved → closed，批准之后不能作废
   （见 test_state_machine_*）。
3. **不越界**：处置单不写 stock_logs、不回写 reports.good_qty
   （见 test_never_touches_stock_or_report）——报废实物出库走仓储出库单，
   报工是既成事实，改了会连带影响工资与良率。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.crud.disposition import (
    DispositionStateError,
    approve_disposition,
    cancel_disposition,
    close_disposition,
    create_disposition,
    disposition_stats,
    get_disposition,
    list_dispositions,
    reject_disposition,
    report_options,
    submit_disposition,
    update_disposition,
    used_qty,
)
from app.models.permission import Permission
from app.models.quality import DefectCode
from app.models.report import Report
from app.models.role import role_permissions
from app.models.warehouse import StockLog


# ── 夹具 ──

@pytest.fixture(scope="session")
def engine():
    """覆盖 conftest 的 engine：HTTP 用例要跨线程复用同一条 SQLite 连接，
    否则 TestClient 的请求线程碰到主线程创建的连接会报 ProgrammingError。"""
    from app.models.base import Base

    e = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(e, "connect")
    def _fk(dbapi_connection, connection_record):  # noqa: ANN001
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(e)
    return e


@pytest.fixture
def api(session):
    from app.main import app

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _grant(session: Session, role, codes: list[str]) -> None:
    for code in codes:
        p = session.scalar(select(Permission).where(Permission.code == code))
        if not p:
            p = Permission(code=code, name=code)
            session.add(p)
            session.flush()
        session.execute(role_permissions.insert().values(role_id=role.id, permission_id=p.id))
    session.flush()


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.fixture
def defect_code(session: Session) -> DefectCode:
    dc = DefectCode(code="DC-001", name="尺寸超差", severity="major")
    session.add(dc)
    session.flush()
    return dc


@pytest.fixture
def report(session: Session, task, test_user) -> Report:
    """报工：良品 90，不良 10。"""
    r = Report(task_id=task.id, report_user_id=test_user.id, good_qty=90, bad_qty=10, status="leader_approved")
    session.add(r)
    session.flush()
    return r


def _mk(session: Session, report: Report, code: str, items: list[dict]):
    d = create_disposition(session, code=code, report_id=report.id, items=items)
    session.flush()
    return get_disposition(session, d.id)


def _item(d, idx: int = 0):
    return d.items[idx]


def _advance_to_pending(session: Session, d):
    d = get_disposition(session, d.id)
    submit_disposition(session, d, submitted_by=1)
    session.flush()
    return get_disposition(session, d.id)


def _advance_to_approved(session: Session, d):
    d = get_disposition(session, d.id)
    if d.status in ("draft", "rejected"):
        submit_disposition(session, d, submitted_by=1)
        session.flush()
        d = get_disposition(session, d.id)
    approve_disposition(session, d, approved_by=1)
    session.flush()
    return get_disposition(session, d.id)


# ── 1. 制单与额度 ──

def test_create_snapshots_report_bad_qty(session: Session, report: Report, defect_code: DefectCode):
    d = _mk(session, report, "CZ1", [
        {"method": "scrap", "qty": 3, "defect_code_id": defect_code.id, "cost_amount": 120},
        {"method": "rework", "qty": 5},
    ])

    assert d.status == "draft"
    assert d.bad_qty == 10, "报工不良量要快照下来，之后报工变了好知道当初判的是多少"
    assert d.total_qty == 8
    assert d.scrap_cost == 120, "损失金额只算报废行，返修/让步不计入报废损失"
    assert len(d.items) == 2
    assert d.report_id == report.id


def test_capacity_rejects_overflow(session: Session, report: Report):
    _mk(session, report, "CZ2", [{"method": "scrap", "qty": 6}])
    with pytest.raises(ValueError) as exc:
        _mk(session, report, "CZ3", [{"method": "rework", "qty": 6}])
    assert "超出可处置数量" in str(exc.value)


def test_capacity_counts_drafts_not_just_approved(session: Session, report: Report):
    """两张草稿一起把额度吃超，第二张建单就该被拦下来。"""
    _mk(session, report, "CZ4", [{"method": "scrap", "qty": 10}])
    assert used_qty(session, report.id) == 10
    with pytest.raises(ValueError):
        _mk(session, report, "CZ5", [{"method": "concede", "qty": 1}])


def test_capacity_rechecks_on_submit(session: Session, report: Report):
    """草稿堆着不动的时候，别的单可能已经占了额度——提交时必须再校验一次。"""
    first = _mk(session, report, "CZ6", [{"method": "scrap", "qty": 5}])
    d = _mk(session, report, "CZ7", [{"method": "rework", "qty": 5}])
    assert d.total_qty == 5

    d.items[0].qty = 8  # 模拟绕过改单校验直接改了数量
    session.flush()
    with pytest.raises(ValueError) as exc:
        submit_disposition(session, get_disposition(session, d.id), submitted_by=1)
    assert "超出可处置数量" in str(exc.value)
    assert first.status == "draft"


def test_rejected_releases_capacity(session: Session, report: Report):
    d = _mk(session, report, "CZ8", [{"method": "scrap", "qty": 10}])
    d = _advance_to_pending(session, d)
    reject_disposition(session, d, "判定依据不足")
    session.flush()
    assert d.status == "rejected"
    assert used_qty(session, report.id) == 0, "被驳回的单据不该继续占额度"

    # 额度释放后，新单能建满 10
    _mk(session, report, "CZ9", [{"method": "rework", "qty": 10}])


def test_cancelled_releases_capacity(session: Session, report: Report):
    d = _mk(session, report, "CZ10", [{"method": "concede", "qty": 10}])
    cancel_disposition(session, d)
    session.flush()
    assert used_qty(session, report.id) == 0


def test_rejects_report_without_bad_qty(session: Session, task, test_user):
    clean = Report(task_id=task.id, report_user_id=test_user.id, good_qty=100, bad_qty=0)
    session.add(clean)
    session.flush()
    with pytest.raises(ValueError) as exc:
        create_disposition(session, code="CZ11", report_id=clean.id, items=[{"method": "scrap", "qty": 1}])
    assert "没有不良品" in str(exc.value)


def test_rejects_unknown_method_and_zero_qty(session: Session, report: Report):
    with pytest.raises(ValueError):
        _mk(session, report, "CZ12", [{"method": "burn", "qty": 1}])
    with pytest.raises(ValueError):
        _mk(session, report, "CZ13", [{"method": "scrap", "qty": 0}])


def test_rejects_unknown_defect_code(session: Session, report: Report):
    with pytest.raises(ValueError):
        _mk(session, report, "CZ14", [{"method": "scrap", "qty": 1, "defect_code_id": 99999}])


# ── 2. 改单 ──

def test_update_replaces_items_and_revalidates(session: Session, report: Report, defect_code: DefectCode):
    d = _mk(session, report, "CZ15", [{"method": "scrap", "qty": 2}])
    update_disposition(
        session, d,
        items=[{"method": "rework", "qty": 7, "defect_code_id": defect_code.id}],
        reason="复判改为返修",
    )
    session.flush()
    d = get_disposition(session, d.id)

    assert d.total_qty == 7
    assert [it.method for it in d.items] == ["rework"]
    assert d.reason == "复判改为返修"

    with pytest.raises(ValueError):
        update_disposition(session, d, items=[{"method": "scrap", "qty": 11}])


def test_update_blocked_after_submit(session: Session, report: Report):
    d = _advance_to_pending(session, _mk(session, report, "CZ16", [{"method": "scrap", "qty": 3}]))
    with pytest.raises(DispositionStateError):
        update_disposition(session, d, items=[{"method": "scrap", "qty": 1}])


def test_update_on_rejected_returns_to_draft(session: Session, report: Report):
    d = _advance_to_pending(session, _mk(session, report, "CZ17", [{"method": "scrap", "qty": 3}]))
    reject_disposition(session, d, "数量不对")
    session.flush()

    update_disposition(session, d, items=[{"method": "scrap", "qty": 2}])
    session.flush()
    assert d.status == "draft", "驳回后改完单应该回到草稿，重新走提交"


# ── 3. 状态机 ──

def test_state_machine_full_path(session: Session, report: Report):
    d = _mk(session, report, "CZ18", [{"method": "rework", "qty": 4}, {"method": "scrap", "qty": 2}])
    d = _advance_to_pending(session, d)
    assert d.status == "pending" and d.submitted_at is not None

    d = _advance_to_approved(session, d)
    assert d.status == "approved" and d.approved_by == 1

    close_disposition(session, d, note="返修 4 件已回线，2 件报废", closed_by=1)
    session.flush()
    d = get_disposition(session, d.id)
    assert d.status == "closed"
    assert d.close_note == "返修 4 件已回线，2 件报废"
    # 未显式填写的明细默认按全量执行
    assert [it.done_qty for it in d.items] == [4, 2]


def test_cannot_close_before_approve(session: Session, report: Report):
    d = _advance_to_pending(session, _mk(session, report, "CZ19", [{"method": "scrap", "qty": 1}]))
    with pytest.raises(DispositionStateError):
        close_disposition(session, d)


def test_cannot_submit_twice(session: Session, report: Report):
    d = _advance_to_pending(session, _mk(session, report, "CZ20", [{"method": "scrap", "qty": 1}]))
    with pytest.raises(DispositionStateError):
        submit_disposition(session, d)


def test_cannot_cancel_approved(session: Session, report: Report):
    d = _advance_to_approved(session, _mk(session, report, "CZ21", [{"method": "scrap", "qty": 1}]))
    with pytest.raises(DispositionStateError):
        cancel_disposition(session, d)


def test_reject_requires_reason(session: Session, report: Report):
    d = _advance_to_pending(session, _mk(session, report, "CZ22", [{"method": "scrap", "qty": 1}]))
    with pytest.raises(ValueError):
        reject_disposition(session, d, "   ")


def test_close_rejects_done_qty_out_of_range(session: Session, report: Report):
    d = _advance_to_approved(session, _mk(session, report, "CZ23", [{"method": "rework", "qty": 3}]))
    with pytest.raises(ValueError):
        close_disposition(session, d, done_items=[{"item_id": d.items[0].id, "done_qty": 4}])
    with pytest.raises(ValueError):
        close_disposition(session, d, done_items=[{"item_id": d.items[0].id, "done_qty": -1}])


def test_close_partial_execution_recorded(session: Session, report: Report):
    d = _advance_to_approved(session, _mk(session, report, "CZ24", [{"method": "rework", "qty": 5}]))
    close_disposition(session, d, done_items=[{"item_id": d.items[0].id, "done_qty": 2, "remark": "3 件返修失败转报废"}])
    session.flush()
    d = get_disposition(session, d.id)
    assert d.items[0].done_qty == 2


# ── 4. 不越界：不写库存、不改报工 ──

def test_never_touches_stock_or_report(session: Session, report: Report, sku):
    d = _mk(session, report, "CZ25", [{"method": "scrap", "qty": 5, "cost_amount": 500}])
    d = _advance_to_approved(session, d)
    close_disposition(session, d)
    session.flush()

    logs = list(session.scalars(select(StockLog).where(StockLog.sku_id == sku.id)).all())
    assert logs == [], "处置单不碰库存：报废实物出库走仓储出库单，直改 stocks 会让流水断链"

    session.refresh(report)
    assert report.good_qty == 90, "闭环只登记执行结果，绝不回写报工的良品数"
    assert report.bad_qty == 10


# ── 5. 统计与可选报工 ──

def test_stats_aggregates_by_method_and_defect(session: Session, report: Report, defect_code: DefectCode):
    _mk(session, report, "CZ26", [
        {"method": "scrap", "qty": 3, "defect_code_id": defect_code.id, "cost_amount": 300},
        {"method": "rework", "qty": 4},
    ])
    dropped = _mk(session, report, "CZ27", [{"method": "return_process", "qty": 3}])
    cancel_disposition(session, dropped)
    session.flush()

    stats = disposition_stats(session)
    assert stats["by_method"]["scrap"]["qty"] == 3
    assert stats["by_method"]["scrap"]["cost"] == 300
    assert stats["by_method"]["rework"]["qty"] == 4
    assert stats["by_method"]["return_process"]["qty"] == 0, "作废的单据不计入方式统计"
    assert stats["total_qty"] == 7
    assert stats["scrap_cost"] == 300
    assert stats["top_defects"][0]["code"] == "DC-001"
    assert stats["by_status"]["draft"] == 1
    assert stats["by_status"]["cancelled"] == 1


def test_report_options_skips_fully_disposed(session: Session, report: Report):
    options = report_options(session)
    assert [o["report_id"] for o in options] == [report.id]
    assert options[0]["remaining_qty"] == 10

    _mk(session, report, "CZ28", [{"method": "scrap", "qty": 10}])
    session.flush()
    assert report_options(session) == [], "不良量处置完的报工不该再出现在候选里"


def test_list_filters_by_status_and_method(session: Session, report: Report):
    _mk(session, report, "CZ29", [{"method": "scrap", "qty": 2}])
    d2 = _mk(session, report, "CZ30", [{"method": "rework", "qty": 3}])
    _advance_to_pending(session, d2)
    session.flush()

    assert len(list_dispositions(session)) == 2
    assert [d.code for d in list_dispositions(session, status="pending")] == ["CZ30"]
    assert [d.code for d in list_dispositions(session, method="scrap")] == ["CZ29"]
    assert [d.code for d in list_dispositions(session, keyword="CZ30")] == ["CZ30"]


# ── 6. HTTP 装配层 ──

def test_api_create_never_returns_server_error(api, session: Session, admin_role, test_user, report: Report):
    """空 body 打写接口，业务码不能是 500/501——这是 API 层与 crud 签名错位的护栏。"""
    _grant(session, admin_role, ["disposition.view", "disposition.manage", "disposition.approve"])
    headers = _auth(test_user)

    resp = api.post("/api/admin/production/dispositions", headers=headers, json={})
    assert resp.status_code == 200
    assert resp.json()["code"] not in (500, 501)


def test_api_flow_end_to_end(api, session: Session, admin_role, test_user, report: Report, defect_code: DefectCode):
    _grant(session, admin_role, ["disposition.view", "disposition.manage", "disposition.approve"])
    headers = _auth(test_user)

    options = api.get("/api/admin/production/dispositions/report-options", headers=headers)
    assert options.json()["code"] == 200
    assert options.json()["data"]["items"][0]["report_id"] == report.id

    created = api.post(
        "/api/admin/production/dispositions",
        headers=headers,
        json={
            "report_id": report.id,
            "reason": "终检批量超差",
            "items": [
                {"method": "scrap", "qty": 3, "defect_code_id": defect_code.id, "cost_amount": 300},
                {"method": "rework", "qty": 5},
            ],
        },
    )
    assert created.json()["code"] == 200, created.text
    doc = created.json()["data"]
    assert doc["code"].startswith("CZ"), "留空单号要自动生成 CZ 前缀"
    assert doc["total_qty"] == 8 and doc["status"] == "draft"
    disposition_id = doc["id"]

    submitted = api.post(f"/api/admin/production/dispositions/{disposition_id}/submit", headers=headers)
    assert submitted.json()["code"] == 200, submitted.text
    approved = api.post(f"/api/admin/production/dispositions/{disposition_id}/approve", headers=headers)
    assert approved.json()["code"] == 200, approved.text

    closed = api.post(
        f"/api/admin/production/dispositions/{disposition_id}/close",
        headers=headers,
        json={"note": "已完成"},
    )
    assert closed.json()["code"] == 200
    assert closed.json()["data"]["status"] == "closed"

    detail = api.get(f"/api/admin/production/dispositions/{disposition_id}", headers=headers)
    assert detail.json()["data"]["items"][1]["done_qty"] == 5

    stats = api.get("/api/admin/production/dispositions/stats", headers=headers)
    assert stats.json()["data"]["by_method"]["scrap"]["qty"] == 3


def test_api_business_error_is_400_not_500(api, session: Session, admin_role, test_user, report: Report):
    _grant(session, admin_role, ["disposition.view", "disposition.manage", "disposition.approve"])
    headers = _auth(test_user)

    resp = api.post(
        "/api/admin/production/dispositions",
        headers=headers,
        json={"report_id": report.id, "items": [{"method": "scrap", "qty": 99}]},
    )
    # 响应包装：HTTP 一律 200，业务码在 body 的 code，错误信息在 msg
    assert resp.status_code == 200
    assert resp.json()["code"] == 400, resp.text
    assert "超出可处置数量" in resp.json()["msg"]


def test_api_requires_permission(api, session: Session, employee_role, test_user, report: Report):
    _grant(session, employee_role, ["report.submit"])
    resp = api.get("/api/admin/production/dispositions", headers=_auth(test_user))
    assert resp.status_code == 200
    assert resp.json()["code"] == 403, "没给处置权限就不该拿到数据"
