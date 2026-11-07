# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""基础台账 API：返工单 / 物料替代 / ECN / 停机记录 / 供应商评分

路由顺序有讲究：`/stats`、`/meta`、`/suggest`、`/options` 这类静态路径
必须注册在 `/{id}` 之前，否则会被当成 id 解析成 422（检验单模块踩过这个坑）。

写端点的 payload 一律可选（`XxxIn | None = None`）：空 body 会走 crud 的业务校验
返回 400，而不是让 FastAPI 抛 422、更不能在 API 装配层炸出 500。
既有单测曾经全部直调 crud 跳过装配层，结果写端点真实请求全是 500 —— 这条纪律别退化。
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_any_permissions
from app.core.response import ok
from app.crud import basics as c
from app.crud.basics import BasicStateError
from app.models.basics import (
    DOWNTIME_REASONS,
    ECN_STATUSES,
    ECN_TYPES,
    REWORK_STATUSES,
    SCORE_GRADES,
)
from app.models.equipment import Equipment
from app.models.material import Material, Supplier
from app.models.material import MaterialBom
from app.models.process import Process
from app.models.sku import Sku
from app.models.user import User


router = APIRouter()
_WRITE_DEPS = {
    "rework": [Depends(require_any_permissions(["rework.manage"]))],
    "substitute": [Depends(require_any_permissions(["substitute.manage"]))],
    "ecn": [Depends(require_any_permissions(["ecn.manage"]))],
    "ecn_approve": [Depends(require_any_permissions(["ecn.approve"]))],
    "downtime": [Depends(require_any_permissions(["downtime.manage"]))],
    "score": [Depends(require_any_permissions(["supplier_score.manage"]))],
}


def _bad(e: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


def _load(db: Session, model, oid: int, label: str):
    o = db.get(model, int(oid))
    if not o:
        raise HTTPException(status_code=400, detail=f"{label}不存在")
    return o


def _p(payload, cls):
    return payload if payload is not None else cls()


# ── 通用下拉选项（前端弹窗选设备/物料/供应商/工序/BOM）──

@router.get("/options", dependencies=[Depends(require_any_permissions([
    "rework.view", "substitute.view", "ecn.view", "downtime.view", "supplier_score.view",
]))])
def options_api(
    type: str = Query(description="equipment / material / supplier / process / bom / sku"),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mapping = {
        "equipment": (Equipment, "code", "name"),
        "material": (Material, "code", "name"),
        "supplier": (Supplier, "code", "name"),
        "process": (Process, "code", "name"),
        "bom": (MaterialBom, "id", "name"),
        "sku": (Sku, "code", "name"),
    }
    if type not in mapping:
        raise _bad(ValueError(f"选项类型必须是 {'/'.join(mapping)}"))
    model, code_field, name_field = mapping[type]
    stmt = select(model).order_by(model.id.desc()).limit(limit)
    out = []
    for o in db.scalars(stmt).all():
        code = str(getattr(o, code_field, "") or "") if code_field != "id" else str(o.id)
        name = str(getattr(o, name_field, "") or "") or code
        if keyword and keyword.strip().lower() not in f"{code}{name}".lower():
            continue
        out.append({"id": o.id, "code": code, "name": name, "label": f"{code} · {name}"})
    return ok(out)


# ────────────────────────────── 返工单 ──────────────────────────────

reworks_router = APIRouter(
    prefix="/reworks",
    dependencies=[Depends(require_any_permissions(["rework.view", "rework.manage"]))],
)


class ReworkStartIn(BaseModel):
    assigned_user_id: int | None = None


class ReworkCompleteIn(BaseModel):
    done_qty: int | None = None


class ReworkCancelIn(BaseModel):
    reason: str | None = None


@reworks_router.get("/stats")
def rework_stats_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(c.rework_stats(db))


@reworks_router.get("/meta")
def rework_meta_api(user: User = Depends(get_current_user)):
    return ok({"statuses": list(REWORK_STATUSES)})


@reworks_router.get("/by-disposition/{disposition_id}")
def reworks_by_disposition_api(
    disposition_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ok([c.rework_out(db, r) for r in c.reworks_for_disposition(db, disposition_id)])


@reworks_router.get("")
def rework_list_api(
    status: str | None = Query(default=None),
    process_id: int | None = Query(default=None),
    disposition_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = dict(status=status, process_id=process_id, disposition_id=disposition_id, keyword=keyword)
    return ok({
        "items": [c.rework_out(db, r) for r in c.list_reworks(db, offset=offset, limit=limit, **filters)],
        "total": c.count_reworks(db, **filters),
    })


@reworks_router.get("/{rework_id}")
def rework_get_api(rework_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = _load(db, c.ReworkOrder, rework_id, "返工单")
    return ok(c.rework_out(db, r))


@reworks_router.post("/{rework_id}/start", dependencies=_WRITE_DEPS["rework"])
def rework_start_api(
    rework_id: int,
    payload: ReworkStartIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = _load(db, c.ReworkOrder, rework_id, "返工单")
    try:
        c.start_rework(db, r, assigned_user_id=_p(payload, ReworkStartIn).assigned_user_id)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.rework_out(db, r))


@reworks_router.post("/{rework_id}/complete", dependencies=_WRITE_DEPS["rework"])
def rework_complete_api(
    rework_id: int,
    payload: ReworkCompleteIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = _load(db, c.ReworkOrder, rework_id, "返工单")
    try:
        c.complete_rework(db, r, done_qty=_p(payload, ReworkCompleteIn).done_qty)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.rework_out(db, r))


@reworks_router.post("/{rework_id}/cancel", dependencies=_WRITE_DEPS["rework"])
def rework_cancel_api(
    rework_id: int,
    payload: ReworkCancelIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r = _load(db, c.ReworkOrder, rework_id, "返工单")
    try:
        c.cancel_rework(db, r, reason=_p(payload, ReworkCancelIn).reason)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.rework_out(db, r))


# ──────────────────────────── 物料替代 ────────────────────────────

substitutes_router = APIRouter(
    prefix="/substitutes",
    dependencies=[Depends(require_any_permissions(["substitute.view", "substitute.manage"]))],
)


class SubstituteIn(BaseModel):
    material_id: int | None = None
    substitute_material_id: int | None = None
    bom_id: int | None = None
    ratio: float = 1
    priority: int = 0
    reason: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    is_active: bool = True
    remark: str | None = None


@substitutes_router.get("/meta")
def substitute_meta_api(user: User = Depends(get_current_user)):
    return ok({"note": "替代关系只做建议，不自动改写 BOM 行"})


@substitutes_router.get("/suggest")
def substitute_suggest_api(
    material_id: int = Query(...),
    bom_id: int | None = Query(default=None),
    on_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return ok(c.substitute_suggestions(db, material_id=material_id, bom_id=bom_id, on_date=on_date))
    except (BasicStateError, ValueError) as e:
        raise _bad(e)


@substitutes_router.get("")
def substitute_list_api(
    material_id: int | None = Query(default=None),
    bom_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = dict(material_id=material_id, bom_id=bom_id, is_active=is_active)
    return ok({
        "items": [c.substitute_out(db, s) for s in c.list_substitutes(db, offset=offset, limit=limit, **filters)],
        "total": c.count_substitutes(db, **filters),
    })


@substitutes_router.post("", dependencies=_WRITE_DEPS["substitute"])
def substitute_create_api(
    payload: SubstituteIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        o = c.create_substitute(db, _p(payload, SubstituteIn).model_dump(), created_by=user.id)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.substitute_out(db, o))


@substitutes_router.get("/{substitute_id}")
def substitute_get_api(substitute_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _load(db, c.MaterialSubstitute, substitute_id, "替代关系")
    return ok(c.substitute_out(db, s))


@substitutes_router.put("/{substitute_id}", dependencies=_WRITE_DEPS["substitute"])
def substitute_update_api(
    substitute_id: int,
    payload: SubstituteIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = _load(db, c.MaterialSubstitute, substitute_id, "替代关系")
    try:
        data = {k: v for k, v in _p(payload, SubstituteIn).model_dump(exclude_unset=True).items() if v is not None}
        c.update_substitute(db, s, data)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.substitute_out(db, s))


@substitutes_router.delete("/{substitute_id}", dependencies=_WRITE_DEPS["substitute"])
def substitute_delete_api(substitute_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _load(db, c.MaterialSubstitute, substitute_id, "替代关系")
    db.delete(s)
    db.commit()
    return ok({"id": substitute_id, "deleted": True})


# ──────────────────────────── 工程变更 ECN ────────────────────────────

ecn_router = APIRouter(
    prefix="/ecn",
    dependencies=[Depends(require_any_permissions(["ecn.view", "ecn.manage", "ecn.approve"]))],
)


class EcnIn(BaseModel):
    code: str | None = None
    title: str | None = None
    change_type: str = "bom"
    product_id: int | None = None
    sku_id: int | None = None
    bom_id: int | None = None
    reason: str | None = None
    description: str | None = None
    before_snapshot: str | None = None
    after_snapshot: str | None = None
    effective_date: str | None = None
    remark: str | None = None


class EcnReasonIn(BaseModel):
    reason: str | None = None


@ecn_router.get("/stats")
def ecn_stats_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(c.ecn_stats(db))


@ecn_router.get("/meta")
def ecn_meta_api(user: User = Depends(get_current_user)):
    return ok({"types": list(ECN_TYPES), "statuses": list(ECN_STATUSES)})


@ecn_router.get("")
def ecn_list_api(
    status: str | None = Query(default=None),
    change_type: str | None = Query(default=None),
    sku_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = dict(status=status, change_type=change_type, sku_id=sku_id, keyword=keyword)
    return ok({
        "items": [c.ecn_out(db, o) for o in c.list_ecns(db, offset=offset, limit=limit, **filters)],
        "total": c.count_ecns(db, **filters),
    })


@ecn_router.post("", dependencies=_WRITE_DEPS["ecn"])
def ecn_create_api(
    payload: EcnIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        o = c.create_ecn(db, _p(payload, EcnIn).model_dump(), created_by=user.id)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.ecn_out(db, o))


@ecn_router.get("/{ecn_id}")
def ecn_get_api(ecn_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(c.ecn_out(db, _load(db, c.EngineeringChange, ecn_id, "变更单")))


@ecn_router.put("/{ecn_id}", dependencies=_WRITE_DEPS["ecn"])
def ecn_update_api(
    ecn_id: int,
    payload: EcnIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _load(db, c.EngineeringChange, ecn_id, "变更单")
    try:
        data = {k: v for k, v in _p(payload, EcnIn).model_dump(exclude_unset=True).items() if v is not None}
        c.update_ecn(db, o, data)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.ecn_out(db, o))


def _ecn_flow_endpoint(ecn_id: int, p, db, user, allowed, target, *, need_reason=False, approve=False):
    o = _load(db, c.EngineeringChange, ecn_id, "变更单")
    try:
        c._ecn_flow(db, o, allowed, target, actor_id=user.id,
                    reason=getattr(p, "reason", None) if need_reason else None)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.ecn_out(db, o))


@ecn_router.post("/{ecn_id}/submit", dependencies=_WRITE_DEPS["ecn"])
def ecn_submit_api(ecn_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _ecn_flow_endpoint(ecn_id, None, db, user, ("draft", "rejected"), "pending")


@ecn_router.post("/{ecn_id}/approve", dependencies=_WRITE_DEPS["ecn_approve"])
def ecn_approve_api(ecn_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _ecn_flow_endpoint(ecn_id, None, db, user, ("pending",), "approved", approve=True)


@ecn_router.post("/{ecn_id}/reject", dependencies=_WRITE_DEPS["ecn_approve"])
def ecn_reject_api(
    ecn_id: int,
    payload: EcnReasonIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _ecn_flow_endpoint(ecn_id, _p(payload, EcnReasonIn), db, user,
                              ("pending",), "rejected", need_reason=True)


@ecn_router.post("/{ecn_id}/implement", dependencies=_WRITE_DEPS["ecn"])
def ecn_implement_api(ecn_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _ecn_flow_endpoint(ecn_id, None, db, user, ("approved",), "implemented")


@ecn_router.post("/{ecn_id}/cancel", dependencies=_WRITE_DEPS["ecn"])
def ecn_cancel_api(ecn_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _ecn_flow_endpoint(ecn_id, None, db, user, ("draft", "pending"), "cancelled")


@ecn_router.delete("/{ecn_id}", dependencies=_WRITE_DEPS["ecn"])
def ecn_delete_api(ecn_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _load(db, c.EngineeringChange, ecn_id, "变更单")
    if o.status != "draft":
        raise _bad(BasicStateError("只有草稿状态的变更单可以删除"))
    db.delete(o)
    db.commit()
    return ok({"id": ecn_id, "deleted": True})


# ──────────────────────────── 设备停机记录 ────────────────────────────

downtimes_router = APIRouter(
    prefix="/downtimes",
    dependencies=[Depends(require_any_permissions(["downtime.view", "downtime.manage"]))],
)


class DowntimeIn(BaseModel):
    code: str | None = None
    equipment_id: int | None = None
    task_id: int | None = None
    reason_code: str = "breakdown"
    started_at: str | None = None
    ended_at: str | None = None
    description: str | None = None
    responsible_id: int | None = None


class DowntimeCloseIn(BaseModel):
    ended_at: str | None = None


@downtimes_router.get("/stats")
def downtime_stats_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ok(c.downtime_stats(db, date_from=date_from, date_to=date_to))


@downtimes_router.get("/meta")
def downtime_meta_api(user: User = Depends(get_current_user)):
    return ok({"reasons": list(DOWNTIME_REASONS), "statuses": ["open", "closed"]})


@downtimes_router.get("")
def downtime_list_api(
    equipment_id: int | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = dict(equipment_id=equipment_id, reason_code=reason_code, status=status,
                   date_from=date_from, date_to=date_to)
    return ok({
        "items": [c.downtime_out(db, o) for o in c.list_downtimes(db, offset=offset, limit=limit, **filters)],
        "total": c.count_downtimes(db, **filters),
    })


@downtimes_router.post("", dependencies=_WRITE_DEPS["downtime"])
def downtime_create_api(
    payload: DowntimeIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        o = c.create_downtime(db, _p(payload, DowntimeIn).model_dump(), created_by=user.id)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.downtime_out(db, o))


@downtimes_router.get("/{downtime_id}")
def downtime_get_api(downtime_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(c.downtime_out(db, _load(db, c.EquipmentDowntime, downtime_id, "停机记录")))


@downtimes_router.put("/{downtime_id}", dependencies=_WRITE_DEPS["downtime"])
def downtime_update_api(
    downtime_id: int,
    payload: DowntimeIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _load(db, c.EquipmentDowntime, downtime_id, "停机记录")
    try:
        data = {k: v for k, v in _p(payload, DowntimeIn).model_dump(exclude_unset=True).items() if v is not None}
        c.update_downtime(db, o, data)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.downtime_out(db, o))


@downtimes_router.post("/{downtime_id}/close", dependencies=_WRITE_DEPS["downtime"])
def downtime_close_api(
    downtime_id: int,
    payload: DowntimeCloseIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _load(db, c.EquipmentDowntime, downtime_id, "停机记录")
    try:
        c.close_downtime(db, o, ended_at=_p(payload, DowntimeCloseIn).ended_at)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.downtime_out(db, o))


@downtimes_router.delete("/{downtime_id}", dependencies=_WRITE_DEPS["downtime"])
def downtime_delete_api(downtime_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _load(db, c.EquipmentDowntime, downtime_id, "停机记录")
    if o.status == "closed":
        raise _bad(BasicStateError("已结束的停机记录是统计依据，不能删除"))
    db.delete(o)
    db.commit()
    return ok({"id": downtime_id, "deleted": True})


# ──────────────────────────── 供应商评分 ────────────────────────────

scores_router = APIRouter(
    prefix="/supplier-scores",
    dependencies=[Depends(require_any_permissions(["supplier_score.view", "supplier_score.manage"]))],
)


class ScoreIn(BaseModel):
    supplier_id: int | None = None
    period: str | None = None
    quality_score: float = 0
    delivery_score: float = 0
    price_score: float = 0
    service_score: float = 0
    evaluated_at: str | None = None
    remark: str | None = None


@scores_router.get("/stats")
def score_stats_api(
    supplier_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ok(c.score_stats(db, supplier_id=supplier_id))


@scores_router.get("/meta")
def score_meta_api(user: User = Depends(get_current_user)):
    return ok({
        "grades": list(SCORE_GRADES),
        "weights": c.SCORE_WEIGHTS,
        "cutoffs": {g: cut for cut, g in c.GRADE_CUTOFFS},
    })


@scores_router.get("")
def score_list_api(
    supplier_id: int | None = Query(default=None),
    period: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = dict(supplier_id=supplier_id, period=period, grade=grade)
    return ok({
        "items": [c.score_out(db, o) for o in c.list_scores(db, offset=offset, limit=limit, **filters)],
        "total": c.count_scores(db, **filters),
    })


@scores_router.post("", dependencies=_WRITE_DEPS["score"])
def score_create_api(
    payload: ScoreIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        o = c.create_score(db, _p(payload, ScoreIn).model_dump(), created_by=user.id)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.score_out(db, o))


@scores_router.get("/{score_id}")
def score_get_api(score_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(c.score_out(db, _load(db, c.SupplierScore, score_id, "评分记录")))


@scores_router.put("/{score_id}", dependencies=_WRITE_DEPS["score"])
def score_update_api(
    score_id: int,
    payload: ScoreIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _load(db, c.SupplierScore, score_id, "评分记录")
    try:
        data = {k: v for k, v in _p(payload, ScoreIn).model_dump(exclude_unset=True).items() if v is not None}
        c.update_score(db, o, data)
        db.commit()
    except (BasicStateError, ValueError) as e:
        raise _bad(e)
    return ok(c.score_out(db, o))


@scores_router.delete("/{score_id}", dependencies=_WRITE_DEPS["score"])
def score_delete_api(score_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _load(db, c.SupplierScore, score_id, "评分记录")
    db.delete(o)
    db.commit()
    return ok({"id": score_id, "deleted": True})


router.include_router(reworks_router, tags=["admin-production-reworks"])
router.include_router(substitutes_router, tags=["admin-production-substitutes"])
router.include_router(ecn_router, tags=["admin-production-ecn"])
router.include_router(downtimes_router, tags=["admin-production-downtimes"])
router.include_router(scores_router, tags=["admin-production-supplier-scores"])
