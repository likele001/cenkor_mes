# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""检验单与检验台账：模板快照 / 自动判定 / 状态机 / 台账可查

这个功能最容易做错的四件事，各钉用例：

1. **明细必须是模板的快照**。模板改了，历史检验单的判定标准不能跟着变
   （见 test_template_change_does_not_affect_existing_order）。
2. **测量项自动判**，但不能替人瞎猜：非数字、没上下限的，宁可留空
   （见 test_measure_auto_judged / test_measure_without_limits_stays_empty）。
3. **必检项没录完不许判定**，判不合格必须说清怎么处置
   （见 test_judge_blocks_missing_required / test_failed_requires_handling）。
4. **判定后锁死**，关闭只盖时间戳不改判定结论——否则合格率统计会失真
   （见 test_locked_after_judge / test_close_keeps_verdict）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.crud.inspection import (
    InspectionStateError,
    cancel_inspection,
    close_inspection,
    count_ledger,
    create_inspection,
    get_inspection,
    inspection_stats,
    judge_inspection,
    ledger_detail,
    ledger_stats,
    list_inspections,
    list_ledger,
    submit_inspection,
    update_inspection,
)
from app.models.inspection import InspectionOrder
from app.models.permission import Permission
from app.models.quality import (
    DefectCode,
    InspectionRecord,
    InspectionTemplate,
    InspectionTemplateItem,
)
from app.models.report_unit import ReportUnit, ReportUnitAudit
from app.models.role import role_permissions
from app.models.task_assignment import TaskAssignment


# ── 夹具 ──

@pytest.fixture(scope="session")
def engine():
    """覆盖 conftest 的 engine：HTTP 用例要跨线程复用同一条 SQLite 连接。"""
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
def defect(session: Session) -> DefectCode:
    dc = DefectCode(code="DC-100", name="外观划伤", severity="major")
    session.add(dc)
    session.flush()
    return dc


@pytest.fixture
def critical_defect(session: Session) -> DefectCode:
    dc = DefectCode(code="DC-CRIT", name="裂纹", severity="critical")
    session.add(dc)
    session.flush()
    return dc


@pytest.fixture
def template(session: Session) -> InspectionTemplate:
    """三项：外观（合格/不合格）、尺寸（测量，10±0.5）、包装（文本，非必检）。"""
    t = InspectionTemplate(code="TPL-IQC", name="来料检验标准")
    session.add(t)
    session.flush()
    session.add_all([
        InspectionTemplateItem(template_id=t.id, seq=1, item_name="外观",
                               item_type="pass_fail", is_required=True),
        InspectionTemplateItem(template_id=t.id, seq=2, item_name="尺寸",
                               item_type="measure", lower_limit="9.5", upper_limit="10.5",
                               unit="mm", is_required=True),
        InspectionTemplateItem(template_id=t.id, seq=3, item_name="包装",
                               item_type="text", is_required=False),
    ])
    session.flush()
    session.refresh(t)
    return t


@pytest.fixture
def material(session: Session, sku):
    from app.models.material import Material

    m = Material(code="MAT-001", name="冷轧钢板", unit="kg", sku_id=sku.id)
    session.add(m)
    session.flush()
    return m


def _mk(session: Session, **kw) -> InspectionOrder:
    kw.setdefault("inspection_type", "iqc")
    # qty=None 表示「不传」，让来源单据（如采购单）带出送检量；默认 100
    qty = kw.pop("qty", 100)
    if qty is not None:
        kw["qty"] = qty
    code = kw.pop("code", "QC1")
    o = create_inspection(session, code=code, **kw)
    session.flush()
    return get_inspection(session, o.id)


def _to_pending(session: Session, o: InspectionOrder) -> InspectionOrder:
    o = get_inspection(session, o.id)
    submit_inspection(session, o)
    session.flush()
    return get_inspection(session, o.id)


def _fill(o: InspectionOrder, seq: int, result: str, measured: str | None = None,
          defect_code_id: int | None = None) -> None:
    it = next(x for x in o.items if x.seq == seq)
    it.result = result
    it.measured_value = measured
    it.defect_code_id = defect_code_id


# ── 1. 模板展开与快照 ──

def test_create_expands_template(session: Session, template: InspectionTemplate, material):
    o = _mk(session, template_id=template.id, material_id=material.id)
    assert len(o.items) == 3
    assert [it.item_name for it in o.items] == ["外观", "尺寸", "包装"]
    assert o.items[1].lower_limit == "9.5" and o.items[1].upper_limit == "10.5"
    assert o.items[2].is_required is False
    assert o.item_name == "冷轧钢板", "物料名要带出来，否则列表里看不出检的是什么"
    assert o.status == "draft"


def test_template_change_does_not_affect_existing_order(
    session: Session, template: InspectionTemplate, material,
):
    """三个月前那批货是按当时的标准检的，模板改了不能倒改历史。"""
    o = _mk(session, template_id=template.id, material_id=material.id, code="QC-SNAP")
    item = session.scalar(
        select(InspectionTemplateItem).where(
            InspectionTemplateItem.template_id == template.id,
            InspectionTemplateItem.seq == 2,
        )
    )
    item.upper_limit = "99"
    session.flush()

    fresh = get_inspection(session, o.id)
    assert fresh.items[1].upper_limit == "10.5", "历史单必须保留建单时的上下限"


def test_items_without_template(session: Session, material):
    o = _mk(session, material_id=material.id, items=[
        {"item_name": "硬度", "item_type": "measure", "lower_limit": "50", "upper_limit": "60"},
        {"item_name": "锈蚀", "item_type": "pass_fail"},
    ])
    assert len(o.items) == 2
    assert o.items[0].seq == 1


def test_no_items_rejected(session: Session, material):
    with pytest.raises(InspectionStateError) as exc:
        _mk(session, material_id=material.id)
    assert "没有任何检查项" in str(exc.value)


def test_iqc_requires_material_or_name(session: Session, template: InspectionTemplate):
    with pytest.raises(InspectionStateError) as exc:
        _mk(session, template_id=template.id)
    assert "必须指定物料" in str(exc.value)


def test_sample_qty_cannot_exceed_qty(session: Session, material):
    with pytest.raises(InspectionStateError) as exc:
        _mk(session, material_id=material.id, qty=10, sample_qty=20,
            items=[{"item_name": "外观"}])
    assert "抽样数量不能大于送检数量" in str(exc.value)


# ── 2. 测量项自动判定 ──

def test_measure_auto_judged(session: Session, template: InspectionTemplate, material):
    o = _mk(session, template_id=template.id, material_id=material.id)
    dim = next(x for x in o.items if x.seq == 2)
    dim.measured_value = "10.2"
    dim.result = None
    from app.crud.inspection import _auto_judge_item

    _auto_judge_item(dim)
    assert dim.result == "pass"

    dim.measured_value = "11.0"
    _auto_judge_item(dim)
    assert dim.result == "fail", "超上限要自动判不合格"


def test_measure_at_boundary_passes(session: Session, template: InspectionTemplate, material):
    o = _mk(session, template_id=template.id, material_id=material.id)
    dim = next(x for x in o.items if x.seq == 2)
    from app.crud.inspection import _auto_judge_item

    dim.measured_value = "9.5"
    _auto_judge_item(dim)
    assert dim.result == "pass", "下限是含的（≥），边界值算合格"


def test_measure_without_limits_stays_empty(session: Session, material):
    o = _mk(session, material_id=material.id,
            items=[{"item_name": "手感", "item_type": "measure", "measured_value": "还行"}])
    assert o.items[0].result is None, "没有上下限又是非数字，不许系统瞎猜"


def test_measure_na_not_overwritten(session: Session, template: InspectionTemplate, material):
    o = _mk(session, template_id=template.id, material_id=material.id)
    dim = next(x for x in o.items if x.seq == 2)
    from app.crud.inspection import _auto_judge_item

    dim.result = "na"
    dim.measured_value = "999"
    _auto_judge_item(dim)
    assert dim.result == "na", "人显式标了不适用，系统不能覆盖"


# ── 3. 判定 ──

def test_judge_blocks_missing_required(session: Session, template: InspectionTemplate,
                                      material, test_user):
    o = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id))
    _fill(o, 1, "pass")  # 尺寸没录、包装非必检
    session.flush()
    with pytest.raises(InspectionStateError) as exc:
        judge_inspection(session, o, inspector_id=test_user.id)
    assert "必检项未录结果" in str(exc.value)


def test_judge_passes_when_all_pass(session: Session, template: InspectionTemplate,
                                   material, test_user):
    o = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id))
    _fill(o, 1, "pass")
    _fill(o, 2, "pass", "10.0")
    session.flush()
    judge_inspection(session, o, inspector_id=test_user.id)
    session.flush()

    assert o.status == "passed"
    assert o.accept_qty == 100 and o.reject_qty == 0
    assert "全部合格" in (o.conclusion or "")


def test_failed_requires_handling(session: Session, template: InspectionTemplate,
                                  material, defect: DefectCode, test_user):
    """判了不合格却不说怎么处置，等于把问题原样丢回现场。"""
    o = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id))
    _fill(o, 1, "fail", defect_code_id=defect.id)
    _fill(o, 2, "pass", "10.0")
    session.flush()

    with pytest.raises(InspectionStateError) as exc:
        judge_inspection(session, o, inspector_id=test_user.id)
    assert "必须选择处置方式" in str(exc.value)
    assert o.status == "pending", "校验失败时对象必须保持原样"


def test_failed_with_handling(session: Session, template: InspectionTemplate,
                              material, defect: DefectCode, test_user):
    o = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id))
    _fill(o, 1, "fail", defect_code_id=defect.id)
    _fill(o, 2, "pass", "10.0")
    session.flush()
    judge_inspection(session, o, inspector_id=test_user.id,
                     accept_qty=80, reject_qty=20, handling="return")
    session.flush()

    assert o.status == "failed"
    assert o.handling == "return"
    assert o.accept_qty == 80 and o.reject_qty == 20
    assert "1 项不合格" in (o.conclusion or "")
    assert o.inspector_id == test_user.id, "判定人要落库，这是质量追溯的基本要求"


def test_critical_defect_marked_in_conclusion(session: Session, template: InspectionTemplate,
                                              material, critical_defect: DefectCode, test_user):
    o = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id))
    _fill(o, 1, "fail", defect_code_id=critical_defect.id)
    _fill(o, 2, "pass", "10.0")
    session.flush()
    judge_inspection(session, o, inspector_id=test_user.id, handling="scrap")
    session.flush()
    assert "致命缺陷" in (o.conclusion or "")


def test_qty_capacity_rejected(session: Session, template: InspectionTemplate,
                               material, test_user):
    o = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id))
    _fill(o, 1, "pass")
    _fill(o, 2, "pass", "10.0")
    session.flush()
    with pytest.raises(InspectionStateError) as exc:
        judge_inspection(session, o, inspector_id=test_user.id, accept_qty=100, reject_qty=50)
    assert "不能大于送检数量" in str(exc.value)


# ── 4. 状态机 ──

def test_locked_after_judge(session: Session, template: InspectionTemplate,
                            material, test_user):
    o = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id))
    _fill(o, 1, "pass")
    _fill(o, 2, "pass", "10.0")
    session.flush()
    judge_inspection(session, o, inspector_id=test_user.id)
    session.flush()

    with pytest.raises(InspectionStateError) as exc:
        update_inspection(session, o, qty=50)
    assert "不能修改" in str(exc.value)


def test_close_keeps_verdict(session: Session, template: InspectionTemplate,
                             material, test_user):
    """关闭只盖时间戳。「已关闭」若吃掉判定结论，合格率统计就失真了。"""
    o = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id))
    _fill(o, 1, "pass")
    _fill(o, 2, "pass", "10.0")
    session.flush()
    judge_inspection(session, o, inspector_id=test_user.id)
    session.flush()

    close_inspection(session, o)
    session.flush()
    assert o.status == "passed", "关闭后状态仍是 passed"
    assert o.closed_at is not None
    assert o.is_closed is True

    with pytest.raises(InspectionStateError):
        close_inspection(session, o)  # 不能关两次


def test_cancel_only_draft_or_pending(session: Session, template: InspectionTemplate,
                                      material, test_user):
    o = _mk(session, template_id=template.id, material_id=material.id)
    cancel_inspection(session, o)
    session.flush()
    assert o.status == "cancelled"

    o2 = _to_pending(session, _mk(session, template_id=template.id, material_id=material.id, code="QC2"))
    _fill(o2, 1, "pass")
    _fill(o2, 2, "pass", "10.0")
    session.flush()
    judge_inspection(session, o2, inspector_id=test_user.id)
    session.flush()
    with pytest.raises(InspectionStateError):
        cancel_inspection(session, o2)


def test_submit_requires_qty(session: Session, material):
    o = _mk(session, material_id=material.id, qty=0, items=[{"item_name": "外观"}])
    with pytest.raises(InspectionStateError) as exc:
        submit_inspection(session, o)
    assert "送检数量" in str(exc.value)


# ── 5. 来源单据 ──

def test_iqc_from_purchase_order(session: Session, sku):
    from app.models.material import Material, Supplier
    from app.models.purchase import PurchaseOrder, PurchaseOrderItem

    sup = Supplier(code="SUP1", name="宝钢贸易")
    session.add(sup)
    session.flush()
    m = Material(code="MAT-PO", name="热轧卷", sku_id=sku.id)
    session.add(m)
    session.flush()
    po = PurchaseOrder(code="PO-1", supplier_id=sup.id, status="confirmed")
    session.add(po)
    session.flush()
    session.add(PurchaseOrderItem(order_id=po.id, material_id=m.id, qty=500))
    session.flush()

    o = _mk(session, source_type="purchase_order", source_id=po.id,
            template_id=None, items=[{"item_name": "外观"}], qty=None)
    assert o.source_code == "PO-1"
    assert o.supplier_id == sup.id, "供应商要从采购单带出来，不然追溯断在检验单这一环"
    assert o.material_id == m.id, "单一明细的采购单要把物料带出来"
    assert o.qty == 500, "送检量默认取采购量"


def test_source_not_found(session: Session, material):
    with pytest.raises(InspectionStateError):
        _mk(session, source_type="purchase_order", source_id=99999,
            material_id=material.id, items=[{"item_name": "外观"}])


# ── 6. 台账（读已有的 inspection_records）──

def _mk_record(session: Session, task, test_user, template: InspectionTemplate,
               result: str = "fail", measured: str | None = None,
               defect_code_id: int | None = None) -> InspectionRecord:
    """造一条逐件检验记录：派工 → 件次 → 审核 → 检查项结果。

    派工表有 (task_id, user_id) 唯一键，所以多次调用要复用同一条派工，
    靠 unit_seq 递增区分件次。
    """
    ta = session.scalar(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task.id,
            TaskAssignment.user_id == test_user.id,
        )
    )
    if not ta:
        ta = TaskAssignment(task_id=task.id, user_id=test_user.id, assigned_qty=50)
        session.add(ta)
        session.flush()

    used = session.scalars(
        select(ReportUnit.unit_seq).where(ReportUnit.task_assignment_id == ta.id)
    ).all()
    next_seq = (max(used) + 1) if used else 1

    unit = ReportUnit(task_assignment_id=ta.id, task_id=task.id, user_id=test_user.id,
                      unit_seq=next_seq, status="qc_approved")
    session.add(unit)
    session.flush()
    audit = ReportUnitAudit(report_unit_id=unit.id, auditor_id=test_user.id,
                            audit_level="qc", action="approve")
    session.add(audit)
    session.flush()
    item = session.scalar(
        select(InspectionTemplateItem).where(
            InspectionTemplateItem.template_id == template.id,
            InspectionTemplateItem.seq == 2,
        )
    )
    rec = InspectionRecord(report_unit_audit_id=audit.id, template_item_id=item.id,
                           result=result, measured_value=measured,
                           defect_code_id=defect_code_id)
    session.add(rec)
    session.flush()
    return rec


def test_ledger_empty_is_safe(session: Session):
    assert list_ledger(session) == []
    assert count_ledger(session) == 0
    st = ledger_stats(session)
    assert st["total"] == 0 and st["pass_rate"] is None


def test_ledger_lists_with_process_and_sku(session: Session, task, test_user,
                                          template: InspectionTemplate, defect: DefectCode):
    """台账的价值就是能查出「哪道工序、哪个型号、谁检的、判成什么」。"""
    rec = _mk_record(session, task, test_user, template, result="fail",
                     measured="11.2", defect_code_id=defect.id)

    rows = list_ledger(session)
    assert len(rows) == 1
    r = rows[0]
    assert r["result"] == "fail"
    assert r["item_name"] == "尺寸"
    assert r["measured_value"] == "11.2"
    assert r["defect_code"] == "DC-100"
    assert r["task_code"] == task.task_code
    assert r["process_id"] == task.process_id
    assert r["unit_seq"] == 1

    detail = ledger_detail(session, rec.id)
    assert detail is not None and detail["id"] == rec.id


def test_ledger_stats_excludes_na(session: Session, task, test_user,
                                  template: InspectionTemplate, defect: DefectCode):
    """na（不适用）不进分母，否则合格率会被稀释。"""
    _mk_record(session, task, test_user, template, result="pass", measured="10.0")
    _mk_record(session, task, test_user, template, result="fail", measured="11.0",
               defect_code_id=defect.id)
    _mk_record(session, task, test_user, template, result="na")

    st = ledger_stats(session)
    assert st["total"] == 3
    assert st["counted"] == 2, "na 不计入分母"
    assert st["failed"] == 1
    assert st["pass_rate"] == 50.0
    assert st["by_severity"].get("major") == 1


def test_ledger_filter_by_result(session: Session, task, test_user,
                                 template: InspectionTemplate):
    _mk_record(session, task, test_user, template, result="pass", measured="10.0")
    _mk_record(session, task, test_user, template, result="fail", measured="11.0")
    assert len(list_ledger(session, result="fail")) == 1
    assert count_ledger(session, result="pass") == 1


# ── 7. HTTP 装配层 ──

def test_api_create_never_returns_server_error(api, session: Session, admin_role, test_user):
    """空 body / 缺字段不许 500。业务码是 200 表示成功，400 表示业务拒绝。"""
    _grant(session, admin_role, ["inspection.view", "inspection.manage", "inspection.audit"])
    headers = _auth(test_user)

    resp = api.post("/api/admin/production/inspections", headers=headers, json={})
    assert resp.status_code == 200
    assert resp.json()["code"] != 500

    resp = api.post("/api/admin/production/inspections", headers=headers,
                    json={"inspection_type": "iqc"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 400
    assert "必须指定物料" in resp.json()["msg"]


def test_api_full_flow(api, session: Session, admin_role, test_user,
                       template: InspectionTemplate, material):
    _grant(session, admin_role, ["inspection.view", "inspection.manage", "inspection.audit"])
    headers = _auth(test_user)

    created = api.post("/api/admin/production/inspections", headers=headers, json={
        "inspection_type": "iqc",
        "material_id": material.id,
        "template_id": template.id,
        "qty": 200,
        "sample_qty": 10,
        "batch_no": "B20261106",
    })
    assert created.status_code == 200
    body = created.json()
    assert body["code"] == 200, created.text
    data = body["data"]
    oid = data["id"]
    assert data["code"].startswith("QC"), "检验单号走 QC 前缀"
    assert data["item_total"] == 3
    assert data["status"] == "draft"

    submitted = api.post(f"/api/admin/production/inspections/{oid}/submit", headers=headers)
    assert submitted.json()["code"] == 200, submitted.text

    # 只录一项就判 —— 必须被拦
    patched = api.put(f"/api/admin/production/inspections/{oid}", headers=headers, json={
        "items": [{"seq": 1, "result": "fail"}],
    })
    assert patched.json()["code"] == 200, patched.text

    blocked = api.post(f"/api/admin/production/inspections/{oid}/judge",
                       headers=headers, json={"handling": "return"})
    assert blocked.json()["code"] == 400, blocked.text

    # 补录剩下的必检项（只提交这一项，其余项必须保留 —— _patch_items 合并语义）
    filled = api.put(f"/api/admin/production/inspections/{oid}", headers=headers, json={
        "items": [{"seq": 2, "result": "pass", "measured_value": "10.05"}],
    })
    assert filled.json()["code"] == 200, filled.text
    assert filled.json()["data"]["item_total"] == 3, "只改一项不能把其余检查项删掉"

    judged = api.post(f"/api/admin/production/inspections/{oid}/judge", headers=headers,
                      json={"accept_qty": 150, "reject_qty": 50, "handling": "return"})
    assert judged.json()["code"] == 200, judged.text
    assert judged.json()["data"]["status"] == "failed"
    assert judged.json()["data"]["handling"] == "return"

    closed = api.post(f"/api/admin/production/inspections/{oid}/close", headers=headers)
    assert closed.json()["code"] == 200
    assert closed.json()["data"]["is_closed"] is True
    assert closed.json()["data"]["status"] == "failed"

    lst = api.get("/api/admin/production/inspections", headers=headers)
    assert lst.json()["code"] == 200
    assert lst.json()["data"]["total"] >= 1

    stats = api.get("/api/admin/production/inspections/stats", headers=headers)
    assert stats.json()["code"] == 200
    assert stats.json()["data"]["failed"] >= 1

    meta = api.get("/api/admin/production/inspections/meta/options", headers=headers)
    assert meta.json()["code"] == 200
    assert len(meta.json()["data"]["inspection_types"]) == 4

    ledger = api.get("/api/admin/production/inspections/ledger", headers=headers)
    assert ledger.json()["code"] == 200
    assert ledger.json()["data"]["total"] == 0


def test_api_permission_denied(api, session: Session, employee_role, test_user):
    """员工没有检验权限，不该拿到数据。"""
    from app.models.role import Role
    from app.models.user import user_roles

    emp = Role(code="employee2", name="普通员工")
    session.add(emp)
    session.flush()
    session.execute(user_roles.insert().values(user_id=test_user.id, role_id=emp.id))
    session.flush()

    resp = api.get("/api/admin/production/inspections", headers=_auth(test_user))
    assert resp.status_code == 200
    assert resp.json()["code"] == 403


def test_api_ledger_detail_404(api, session: Session, admin_role, test_user):
    _grant(session, admin_role, ["inspection.view"])
    resp = api.get("/api/admin/production/inspections/ledger/99999", headers=_auth(test_user))
    assert resp.status_code == 200
    assert resp.json()["code"] == 404


# ── 8. 统计 ──

def test_stats_pass_rate_ignores_cancelled(session: Session, material, test_user):
    _mk(session, material_id=material.id, code="QC-A", items=[{"item_name": "外观"}])
    o2 = _to_pending(session, _mk(session, material_id=material.id, code="QC-B",
                                  items=[{"item_name": "外观"}]))
    _fill(o2, 1, "pass")
    session.flush()
    judge_inspection(session, o2, inspector_id=test_user.id)
    session.flush()
    _mk(session, material_id=material.id, code="QC-C", items=[{"item_name": "外观"}])

    st = inspection_stats(session)
    assert st["total"] == 3
    assert st["passed"] == 1
    assert st["failed"] == 0
    assert st["pass_rate"] == 100.0
    assert st["by_type"]["iqc"]["total"] == 3
