# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""第二批基础台账 + 质量主线联动（0019）

最容易做错的五件事，各钉用例：

1. **返工单生成必须幂等**：批准接口重复点、事后补生成，都不能冒出第二张派工。
2. **评分口径只有一个**：总分与等级永远由权重算，前端传什么都不算数；
   同一供应商同一期间只能有一条，否则平均分会被重复评分拉偏。
3. **停机时长由起止时间算**：不接受手工时长，结束早于开始必须拦。
4. **ECN 只登记不自动改 BOM**：状态机走到 implemented 也不能把主数据悄悄改掉。
5. **写端点空 body 不许 500**：既有单测曾全部直调 crud 跳过 API 装配层，
   生产上写接口真实请求全 500 —— 这条纪律用 HTTP 用例守住。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.crud import basics as c
from app.crud.basics import BasicStateError
from app.crud.inspection import create_inspection, get_inspection, judge_inspection, submit_inspection
from app.models.basics import (
    EngineeringChange,
    EquipmentDowntime,
    MaterialSubstitute,
    ReworkOrder,
    SupplierScore,
)
from app.models.disposition import Disposition, DispositionItem
from app.models.equipment import Equipment
from app.models.material import Material, Supplier
from app.models.permission import Permission
from app.models.report import Report
from app.models.role import role_permissions


# ── 夹具 ──

@pytest.fixture(scope="session")
def engine():
    """覆盖 conftest 的 engine：HTTP 用例要跨线程复用同一条 SQLite 连接。"""
    from app.models.base import Base
    import app.models  # noqa: F401

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


_ALL_PERMS = [
    "rework.view", "rework.manage", "substitute.view", "substitute.manage",
    "ecn.view", "ecn.manage", "ecn.approve", "downtime.view", "downtime.manage",
    "supplier_score.view", "supplier_score.manage",
    "inspection.view", "inspection.manage", "inspection.audit",
    "disposition.view", "disposition.manage", "disposition.approve",
    "report.audit", "qc.approve",
]


@pytest.fixture
def mat(session, sku):
    return _material(session, sku, "MAT-A", "原料 A")


def _material(session, sku, code, name):
    m = Material(code=code, name=name, unit="kg", sku_id=sku.id)
    session.add(m)
    session.flush()
    return m


def _new_material(session, product, tag):
    """materials.sku_id 有唯一约束，一颗替代料必须配一个独立 SKU。"""
    from app.models.sku import Sku

    s = Sku(product_id=product.id, code=f"SKU-{tag}", name=f"型号{tag}")
    session.add(s)
    session.flush()
    return _material(session, s, f"MAT-{tag}", f"物料{tag}")


@pytest.fixture
def supplier(session):
    s = Supplier(code="SUP-1", name="一号供应商")
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def equipment(session):
    e = Equipment(code="EQ-1", name="注塑机 1 号", status="active")
    session.add(e)
    session.flush()
    return e


@pytest.fixture
def report(session, task, test_user):
    r = Report(task_id=task.id, report_user_id=test_user.id,
               good_qty=80, bad_qty=10, status="leader_approved")
    session.add(r)
    session.flush()
    return r


@pytest.fixture
def disposition(session, report, task, process, sku):
    d = Disposition(
        code="CZ-TEST-1", status="approved", report_id=report.id, task_id=task.id,
        sku_id=sku.id, process_id=process.id, bad_qty=10, total_qty=4,
    )
    session.add(d)
    session.flush()
    it = DispositionItem(disposition_id=d.id, method="return_process", qty=4,
                         target_process_id=process.id)
    session.add(it)
    session.flush()
    session.refresh(d)
    return d


# ── 返工单 ──

def test_generate_reworks_is_idempotent(session, disposition):
    made = c.generate_reworks_for_disposition(session, disposition, created_by=1)
    assert len(made) == 1
    assert made[0].qty == 4
    assert made[0].status == "pending"
    assert made[0].code.startswith("RW")

    again = c.generate_reworks_for_disposition(session, disposition, created_by=1)
    assert again == [], "重复生成必须一张都不新建"
    assert len(c.reworks_for_disposition(session, disposition.id)) == 1


def test_rework_complete_writes_back_to_disposition(session, disposition):
    r = c.generate_reworks_for_disposition(session, disposition)[0]
    c.start_rework(session, r, assigned_user_id=1)
    assert r.status == "in_progress"
    c.complete_rework(session, r, done_qty=3)
    assert r.status == "done" and r.done_qty == 3
    it = session.get(DispositionItem, r.disposition_item_id)
    assert it.done_qty == 3, "返工完成数要回流到处置明细，闭环才不会按全量执行抹掉"
    with pytest.raises(BasicStateError):
        c.cancel_rework(session, r, reason="误操作")


def test_rework_complete_qty_bounds(session, disposition):
    r = c.generate_reworks_for_disposition(session, disposition)[0]
    with pytest.raises(BasicStateError):
        c.complete_rework(session, r, done_qty=5)
    assert r.status == "pending"


def test_rework_stats(session, disposition):
    r = c.generate_reworks_for_disposition(session, disposition)[0]
    c.complete_rework(session, r)
    stats = c.rework_stats(session)
    assert stats["total"] == 1 and stats["done"] == 1
    assert stats["completion_rate"] == 100.0
    assert stats["done_qty"] == 4


# ── 物料替代 ──

def test_substitute_self_and_duplicate_rejected(session, mat, product):
    other = _new_material(session, product, "B")
    with pytest.raises(BasicStateError):
        c.create_substitute(session, {"material_id": mat.id, "substitute_material_id": mat.id})
    s = c.create_substitute(session, {
        "material_id": mat.id, "substitute_material_id": other.id, "ratio": 2, "priority": 5,
    })
    assert float(s.ratio) == 2
    with pytest.raises(BasicStateError):
        c.create_substitute(session, {"material_id": mat.id, "substitute_material_id": other.id})


def test_substitute_suggestion_order_and_validity(session, mat, product):
    b1 = _new_material(session, product, "B1")
    b2 = _new_material(session, product, "B2")
    c.create_substitute(session, {"material_id": mat.id, "substitute_material_id": b1.id, "priority": 1})
    c.create_substitute(session, {
        "material_id": mat.id, "substitute_material_id": b2.id, "priority": 9,
        "effective_from": "2020-01-01", "effective_to": "2020-12-31",
    })
    out = c.substitute_suggestions(session, material_id=mat.id, on_date="2026-11-07")
    assert [x["substitute_material_id"] for x in out] == [b1.id], "过期替代关系不能出现在建议里"
    assert float(out[0]["ratio"]) == 1


# ── ECN ──

def test_ecn_state_machine(session):
    o = c.create_ecn(session, {"title": "BOM 换料", "change_type": "bom"})
    assert o.code.startswith("ECN") and o.status == "draft"
    c._ecn_flow(session, o, ("draft", "rejected"), "pending")
    with pytest.raises(BasicStateError):
        c._ecn_flow(session, o, ("pending",), "rejected", reason="  ")
    c._ecn_flow(session, o, ("pending",), "approved", actor_id=7)
    assert o.approved_by == 7 and o.approved_at
    c._ecn_flow(session, o, ("approved",), "implemented")
    assert o.applied_at
    with pytest.raises(BasicStateError):
        c.update_ecn(session, o, {"title": "事后改标题"})
    assert c.ecn_stats(session)["implemented"] == 1


def test_ecn_does_not_touch_bom(session, sku):
    """ECN 只登记决定与执行结果，不自动重写 BOM 主数据。"""
    from app.models.material import MaterialBom

    bom = MaterialBom(sku_id=sku.id, name="原 BOM", version=1)
    session.add(bom)
    session.flush()
    o = c.create_ecn(session, {"title": "换料", "bom_id": bom.id,
                               "before_snapshot": '{"version":1}', "after_snapshot": '{"version":2}'})
    c._ecn_flow(session, o, ("draft", "rejected"), "pending")
    c._ecn_flow(session, o, ("pending",), "approved")
    c._ecn_flow(session, o, ("approved",), "implemented")
    session.expire(bom)
    assert bom.version == 1


# ── 停机记录 ──

def test_downtime_duration_computed_and_bounds(session, equipment):
    start = datetime(2026, 11, 7, 8, 0, 0)
    o = c.create_downtime(session, {
        "equipment_id": equipment.id, "reason_code": "breakdown",
        "started_at": start.isoformat(), "ended_at": (start + timedelta(minutes=95)).isoformat(),
    })
    assert o.status == "closed" and o.duration_minutes == 95
    with pytest.raises(BasicStateError):
        c.close_downtime(session, o)
    assert c.downtime_stats(session)["total_minutes"] == 95

    with pytest.raises(BasicStateError):
        c.create_downtime(session, {
            "equipment_id": equipment.id, "started_at": start.isoformat(),
            "ended_at": (start - timedelta(minutes=5)).isoformat(),
        })

    o3 = c.create_downtime(session, {
        "equipment_id": equipment.id, "started_at": start.isoformat(),
    })
    assert o3.status == "open" and o3.duration_minutes is None
    # 显式传 ended_at：UTC runner 的 datetime.now() 可能早于上面硬编码的 08:00，
    # 走 close_downtime 默认的 _now() 会算出负时长并抛 BasicStateError（CI 红叉根因）。
    c.close_downtime(session, o3, ended_at=(start + timedelta(minutes=30)).isoformat())
    assert o3.status == "closed" and o3.duration_minutes == 30


# ── 供应商评分 ──

def test_score_weighted_total_and_grade(session, supplier):
    o = c.create_score(session, {
        "supplier_id": supplier.id, "period": "2026-10",
        "quality_score": 90, "delivery_score": 80, "price_score": 70, "service_score": 60,
    })
    # 90*.4 + 80*.3 + 70*.2 + 60*.1 = 80
    assert float(o.total_score) == 80.0
    assert o.grade == "B"
    c.update_score(session, o, {"quality_score": 100})
    assert float(o.total_score) == 84.0
    assert o.grade == "B"


def test_score_unique_period_and_bounds(session, supplier):
    c.create_score(session, {"supplier_id": supplier.id, "period": "2026-10", "quality_score": 90})
    with pytest.raises(BasicStateError):
        c.create_score(session, {"supplier_id": supplier.id, "period": "2026-10"})
    with pytest.raises(BasicStateError):
        c.create_score(session, {"supplier_id": supplier.id, "period": "2026-11", "quality_score": 101})
    stats = c.score_stats(session)
    assert stats["total"] == 1
    assert stats["by_supplier"][0]["supplier_name"] == "一号供应商"


# ── API 装配层：空 body 与只读端点不许 500 / 501 ──

def test_api_empty_body_never_server_error(api, session, admin_role, test_user):
    _grant(session, admin_role, _ALL_PERMS)
    h = _auth(test_user)
    for path in ("/substitutes", "/ecn", "/downtimes", "/supplier-scores"):
        resp = api.post(f"/api/admin/production{path}", headers=h, json={})
        assert resp.status_code == 200, (path, resp.text)
        assert resp.json()["code"] not in (500, 501), (path, resp.text)
        assert resp.json()["code"] == 400, (path, resp.text)

    for path in (
        "/reworks/stats", "/reworks/meta", "/reworks",
        "/substitutes/meta", "/substitutes",
        "/ecn/stats", "/ecn/meta", "/ecn",
        "/downtimes/stats", "/downtimes/meta", "/downtimes",
        "/supplier-scores/stats", "/supplier-scores/meta", "/supplier-scores",
        "/options?type=equipment",
    ):
        resp = api.get(f"/api/admin/production{path}", headers=h)
        assert resp.status_code == 200, (path, resp.text)
        assert resp.json()["code"] == 200, (path, resp.text)


def test_api_create_full_flow(api, session, admin_role, test_user, mat, sku, supplier, equipment):
    _grant(session, admin_role, _ALL_PERMS)
    h = _auth(test_user)

    sub = api.post("/api/admin/production/substitutes", headers=h, json={
        "material_id": mat.id, "substitute_material_id": 999999,
    })
    assert sub.json()["code"] == 400

    ecn = api.post("/api/admin/production/ecn", headers=h, json={"title": "换料评审"})
    assert ecn.json()["code"] == 200, ecn.text
    eid = ecn.json()["data"]["id"]
    assert ecn.json()["data"]["code"].startswith("ECN")
    assert api.post(f"/api/admin/production/ecn/{eid}/submit", headers=h).json()["code"] == 200
    assert api.post(f"/api/admin/production/ecn/{eid}/approve", headers=h).json()["code"] == 200
    assert api.post(f"/api/admin/production/ecn/{eid}/implement", headers=h).json()["code"] == 200

    dt = api.post("/api/admin/production/downtimes", headers=h, json={
        "equipment_id": equipment.id, "reason_code": "changeover",
        "started_at": "2026-11-07T08:00:00", "ended_at": "2026-11-07T08:30:00",
    })
    assert dt.json()["code"] == 200, dt.text
    assert dt.json()["data"]["duration_minutes"] == 30

    sc = api.post("/api/admin/production/supplier-scores", headers=h, json={
        "supplier_id": supplier.id, "period": "2026-10",
        "quality_score": 100, "delivery_score": 100, "price_score": 100, "service_score": 100,
    })
    assert sc.json()["code"] == 200, sc.text
    assert sc.json()["data"]["grade"] == "A"

    suggest = api.get(f"/api/admin/production/substitutes/suggest?material_id={mat.id}", headers=h)
    assert suggest.json()["code"] == 200


# ── ③④⑤ 联动 ──

def test_from_report_builds_inspection_and_links_verdict(api, session, admin_role, test_user, report, task):
    _grant(session, admin_role, _ALL_PERMS)
    h = _auth(test_user)

    created = api.post("/api/admin/production/inspections/from-report", headers=h, json={
        "report_id": report.id,
        "items": [{"item_name": "外观", "item_type": "pass_fail", "is_required": True, "result": "pass"}],
    })
    assert created.json()["code"] == 200, created.text
    d = created.json()["data"]
    assert d["report_id"] == report.id
    assert d["qty"] == 80, "送检量要从报工良品数自动带出"
    assert d["process_id"] == task.process_id
    assert d["inspection_type"] == "ipqc"

    oid = d["id"]
    by_report = api.get(f"/api/admin/production/reports/{report.id}/inspections", headers=h)
    assert by_report.json()["code"] == 200
    assert any(x["id"] == oid for x in by_report.json()["data"]["items"])

    # 依据单还没判定合格 → 终审必须拒绝（拒绝路径不会走到薪资/追溯链）
    bad = api.post(f"/api/admin/production/reports/{report.id}/qc-approve", headers=h,
                   json={"inspection_id": oid})
    assert bad.json()["code"] == 400
    assert "未判定合格" in bad.json()["msg"]

    assert api.post(f"/api/admin/production/inspections/{oid}/submit", headers=h).json()["code"] == 200
    judged = api.post(f"/api/admin/production/inspections/{oid}/judge", headers=h, json={})
    assert judged.json()["code"] == 200, judged.text
    assert judged.json()["data"]["status"] == "passed"

    summary = api.get("/api/admin/production/inspections/source-summary"
                      f"?source_type=report&source_id={report.id}", headers=h)
    assert summary.json()["code"] == 200
    assert summary.json()["data"]["last_status"] == "passed"


def test_oqc_fai_source_options_carry_context(session, work_order, sku, process, task):
    from app.models.shipment import Shipment, ShipmentItem

    sh = Shipment(order_id=work_order.order_id, code="SH-TEST-1")
    session.add(sh)
    session.flush()
    session.add(ShipmentItem(shipment_id=sh.id, sku_id=sku.id, qty=25))
    session.flush()

    from app.crud.inspection import source_options

    oqc = source_options(session, inspection_type="oqc")
    hit = next(x for x in oqc if x["code"] == "SH-TEST-1")
    assert hit["qty"] == 25
    assert hit["sku_id"] == sku.id
    assert hit["customer_id"] is not None, "OQC 要从订单带出客户"

    fai = source_options(session, inspection_type="fai")
    thit = next(x for x in fai if x["id"] == task.id)
    assert thit["process_id"] == process.id
    assert thit["sku_id"] == sku.id
    assert thit["qty"] == task.planned_qty


def test_disposition_approve_generates_rework(api, session, admin_role, test_user, disposition):
    _grant(session, admin_role, _ALL_PERMS)
    h = _auth(test_user)
    disposition.status = "pending"
    session.flush()

    resp = api.post(f"/api/admin/production/dispositions/{disposition.id}/approve", headers=h)
    assert resp.json()["code"] == 200, resp.text
    assert resp.json()["data"]["reworks_generated"] == 1

    again = api.post(f"/api/admin/production/dispositions/{disposition.id}/generate-reworks", headers=h)
    assert again.json()["code"] == 200
    assert again.json()["data"]["generated"] == 0, "补生成必须幂等"

    lst = api.get("/api/admin/production/reworks", headers=h)
    assert lst.json()["code"] == 200
    assert lst.json()["data"]["total"] == 1
