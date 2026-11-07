# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""基础台账 crud：返工单 / 物料替代 / ECN / 停机记录 / 供应商评分

口径集中在这里，API 层只做参数装配与提交，不自己算业务结果：

- 序列化统一走 `_row()`（按 `__table__.columns` 取值，datetime/date 转 ISO、Decimal 转 float），
  避免每个模块手写一份字段清单、加字段时漏掉返回键。
- 所有日期字段同时接受 ISO 字符串和 datetime/date 对象（前端传串、测试传对象）。
- 校验失败一律抛 `BasicStateError`，API 层转 400；**不在 API 的 except 里 rollback**
  （请求级 session 已兜底，测试共享 session 时 rollback 会把夹具数据一起卷走）。
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.basics import (
    DOWNTIME_REASONS,
    ECN_STATUSES,
    ECN_TYPES,
    REWORK_STATUSES,
    EngineeringChange,
    EquipmentDowntime,
    MaterialSubstitute,
    ReworkOrder,
    SupplierScore,
)
from app.models.equipment import Equipment
from app.models.material import Material, Supplier
from app.models.process import Process
from app.models.sku import Sku
from app.models.task import Task
from app.models.disposition import Disposition, DispositionItem
from app.services.code_generator import BizType, resolve_code

# 供应商评分权重：改这里等于改历史口径，必须同步考虑历史评分重算
SCORE_WEIGHTS = {"quality_score": 0.40, "delivery_score": 0.30,
                 "price_score": 0.20, "service_score": 0.10}
GRADE_CUTOFFS = ((90, "A"), (80, "B"), (70, "C"), (0, "D"))


class BasicStateError(ValueError):
    """状态机或口径不满足，API 层转 400"""


def _now() -> datetime:
    return datetime.now()


def _dt(v, *, field: str) -> datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime.combine(v, datetime.min.time())
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("T", " ").split("+")[0])
    except (ValueError, TypeError):
        raise BasicStateError(f"{field} 不是有效的时间格式")


def _d(v, *, field: str) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (ValueError, TypeError):
        raise BasicStateError(f"{field} 不是有效的日期格式")


def _num(v, *, field: str, lo: float = 0, hi: float = 100) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise BasicStateError(f"{field} 必须是数字")
    if f < lo or f > hi:
        raise BasicStateError(f"{field} 必须在 {lo} 到 {hi} 之间")
    return round(f, 2)


def _row(o, extra: dict | None = None) -> dict:
    d: dict = {}
    for c in o.__table__.columns:
        v = getattr(o, c.name, None)
        if isinstance(v, datetime):
            v = v.isoformat(sep=" ", timespec="seconds")
        elif isinstance(v, date):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = float(v)
        d[c.name] = v
    if extra:
        d.update(extra)
    return d


def _name(db: Session, model, pk, field: str = "name") -> str | None:
    if not pk:
        return None
    o = db.get(model, int(pk))
    return getattr(o, field, None) if o else None


def _count(db: Session, stmt) -> int:
    inner = stmt.with_only_columns(func.count()).order_by(None).subquery()
    return int(db.scalar(select(func.count()).select_from(inner)) or 0)


# ────────────────────────────── 返工单 ──────────────────────────────

def rework_out(db: Session, r: ReworkOrder) -> dict:
    d = db.get(Disposition, r.disposition_id) if r.disposition_id else None
    return _row(r, {
        "disposition_code": d.code if d else None,
        "disposition_status": d.status if d else None,
        "task_code": _name(db, Task, r.task_id, "task_code"),
        "sku_name": _name(db, Sku, r.sku_id),
        "process_name": _name(db, Process, r.process_id),
    })


def _rework_stmt(*, status=None, process_id=None, disposition_id=None, keyword=None):
    stmt = select(ReworkOrder)
    if status:
        stmt = stmt.where(ReworkOrder.status == status)
    if process_id:
        stmt = stmt.where(ReworkOrder.process_id == int(process_id))
    if disposition_id:
        stmt = stmt.where(ReworkOrder.disposition_id == int(disposition_id))
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.join(Disposition, Disposition.id == ReworkOrder.disposition_id).where(
            or_(ReworkOrder.code.like(kw), Disposition.code.like(kw), ReworkOrder.remark.like(kw))
        )
    return stmt


def list_reworks(db: Session, *, offset: int = 0, limit: int = 20, **filters) -> list[ReworkOrder]:
    return list(db.scalars(
        _rework_stmt(**filters).order_by(ReworkOrder.id.desc()).offset(offset).limit(limit)
    ).all())


def count_reworks(db: Session, **filters) -> int:
    return _count(db, _rework_stmt(**filters))


def get_rework(db: Session, rework_id: int) -> ReworkOrder | None:
    return db.get(ReworkOrder, int(rework_id))


def reworks_for_disposition(db: Session, disposition_id: int) -> list[ReworkOrder]:
    return list(db.scalars(
        select(ReworkOrder)
        .where(ReworkOrder.disposition_id == int(disposition_id))
        .order_by(ReworkOrder.id.asc())
    ).all())


def generate_reworks_for_disposition(
    db: Session, d: Disposition, *, created_by: int | None = None
) -> list[ReworkOrder]:
    """把处置单里 `return_process` 的明细转成返工单。

    幂等：按 `disposition_item_id` 查重，已有就跳过。批准接口重复点、或事后补生成，
    都不会冒出第二张派工。没填 `target_process_id` 时退回处置单上的原工序，
    **不猜**目标工序——猜错了返工就派到错的班组去了。
    """
    rows = [it for it in (d.items or []) if it.method == "return_process"]
    if not rows:
        return []
    existing = {
        int(r.disposition_item_id)
        for r in db.scalars(
            select(ReworkOrder).where(ReworkOrder.disposition_id == d.id)
        ).all()
    }
    made: list[ReworkOrder] = []
    for it in rows:
        if int(it.id) in existing:
            continue

        def _exists(code: str) -> bool:
            return db.scalar(select(ReworkOrder.id).where(ReworkOrder.code == code)) is not None

        code = resolve_code(db, biz_type=BizType.REWORK, code=None, exists=_exists)
        r = ReworkOrder(
            code=code,
            status="pending",
            disposition_id=d.id,
            disposition_item_id=it.id,
            report_id=d.report_id,
            task_id=d.task_id,
            work_order_id=d.work_order_id,
            sku_id=d.sku_id,
            process_id=it.target_process_id or d.process_id,
            qty=int(it.qty or 0),
            remark=it.remark,
            created_by=created_by,
        )
        db.add(r)
        db.flush()
        existing.add(int(it.id))
        made.append(r)
    return made


def start_rework(db: Session, r: ReworkOrder, *, assigned_user_id: int | None = None) -> ReworkOrder:
    if r.status != "pending":
        raise BasicStateError("只有待派工的返工单可以开工")
    r.status = "in_progress"
    r.assigned_user_id = assigned_user_id
    r.assigned_at = _now()
    r.started_at = r.started_at or _now()
    db.flush()
    return r


def complete_rework(db: Session, r: ReworkOrder, *, done_qty: int | None = None) -> ReworkOrder:
    if r.status not in ("pending", "in_progress"):
        raise BasicStateError("只有待派工/在制的返工单可以完成")
    qty = int(r.qty or 0) if done_qty is None else int(done_qty)
    if qty < 0 or qty > int(r.qty or 0):
        raise BasicStateError(f"完成数量必须在 0 到 {r.qty} 之间")
    r.status = "done"
    r.done_qty = qty
    r.finished_at = _now()
    if r.started_at is None:
        r.started_at = r.finished_at
    db.flush()

    # 回流：把实际返工良品数写到处置明细上。处置单闭环时「未显式列出的行默认全量执行」，
    # 已填的不会被覆盖，所以这里填了就能在闭环里保留真实结果。
    it = db.get(DispositionItem, r.disposition_item_id)
    d = db.get(Disposition, r.disposition_id) if it else None
    if it and d and d.status == "approved":
        it.done_qty = qty
        db.flush()
    return r


def cancel_rework(db: Session, r: ReworkOrder, *, reason: str | None = None) -> ReworkOrder:
    if r.status == "done":
        raise BasicStateError("已完成的返工单不能作废")
    if r.status == "cancelled":
        raise BasicStateError("返工单已作废")
    r.status = "cancelled"
    r.remark = (r.remark or "") + (f"；作废：{reason}" if reason else "")
    db.flush()
    return r


def rework_stats(db: Session) -> dict:
    rows = db.execute(
        select(ReworkOrder.status, func.count(), func.coalesce(func.sum(ReworkOrder.qty), 0))
        .group_by(ReworkOrder.status)
    ).all()
    by_status = {s: {"count": int(c), "qty": int(q)} for s, c, q in rows}
    total = sum(v["count"] for v in by_status.values())
    done = by_status.get("done", {}).get("count", 0)
    done_qty = int(db.scalar(
        select(func.coalesce(func.sum(ReworkOrder.done_qty), 0)).where(ReworkOrder.status == "done")
    ) or 0)
    return {
        "total": total,
        "pending": by_status.get("pending", {}).get("count", 0),
        "in_progress": by_status.get("in_progress", {}).get("count", 0),
        "done": done,
        "completion_rate": round(done / total * 100, 1) if total else None,
        "done_qty": done_qty,
        "by_status": by_status,
    }


# ──────────────────────────── 物料替代 ────────────────────────────

def substitute_out(db: Session, s: MaterialSubstitute) -> dict:
    return _row(s, {
        "material_name": _name(db, Material, s.material_id),
        "material_code": _name(db, Material, s.material_id, "code"),
        "substitute_name": _name(db, Material, s.substitute_material_id),
        "substitute_code": _name(db, Material, s.substitute_material_id, "code"),
    })


def _substitute_stmt(*, material_id=None, substitute_material_id=None, bom_id=None, is_active=None):
    stmt = select(MaterialSubstitute)
    if material_id:
        stmt = stmt.where(MaterialSubstitute.material_id == int(material_id))
    if substitute_material_id:
        stmt = stmt.where(MaterialSubstitute.substitute_material_id == int(substitute_material_id))
    if bom_id:
        stmt = stmt.where(MaterialSubstitute.bom_id == int(bom_id))
    if is_active is not None:
        stmt = stmt.where(MaterialSubstitute.is_active.is_(bool(is_active)))
    return stmt


def list_substitutes(db: Session, *, offset=0, limit=20, **filters):
    return list(db.scalars(
        _substitute_stmt(**filters)
        .order_by(MaterialSubstitute.priority.desc(), MaterialSubstitute.id.desc())
        .offset(offset).limit(limit)
    ).all())


def count_substitutes(db: Session, **filters) -> int:
    return _count(db, _substitute_stmt(**filters))


def get_substitute(db: Session, sid: int):
    return db.get(MaterialSubstitute, int(sid))


def _validate_substitute(db: Session, data: dict, *, exclude_id: int | None = None) -> dict:
    mid = int(data.get("material_id") or 0)
    sub = int(data.get("substitute_material_id") or 0)
    if not mid or not sub:
        raise BasicStateError("原物料与替代物料都必须指定")
    if mid == sub:
        raise BasicStateError("原物料和替代物料不能是同一颗物料")
    for pk in (mid, sub):
        if not db.get(Material, pk):
            raise BasicStateError(f"物料 {pk} 不存在")
    bom_id = data.get("bom_id") or None
    ratio = float(data.get("ratio") or 1)
    if ratio <= 0:
        raise BasicStateError("替代比例必须大于 0")
    ef = _d(data.get("effective_from"), field="生效日期")
    et = _d(data.get("effective_to"), field="失效日期")
    if ef and et and ef > et:
        raise BasicStateError("生效日期不能晚于失效日期")
    dup = select(MaterialSubstitute.id).where(
        MaterialSubstitute.material_id == mid,
        MaterialSubstitute.substitute_material_id == sub,
        MaterialSubstitute.bom_id.is_(None) if bom_id is None
        else MaterialSubstitute.bom_id == int(bom_id),
    )
    if exclude_id:
        dup = dup.where(MaterialSubstitute.id != int(exclude_id))
    if db.scalar(dup) is not None:
        raise BasicStateError("这条替代关系已经存在，请直接修改而不是重复新增")
    return {
        "material_id": mid, "substitute_material_id": sub,
        "bom_id": int(bom_id) if bom_id else None,
        "ratio": ratio, "priority": int(data.get("priority") or 0),
        "reason": (data.get("reason") or "").strip() or None,
        "effective_from": ef, "effective_to": et,
        "is_active": bool(data.get("is_active", True)),
        "remark": (data.get("remark") or "").strip() or None,
    }


def create_substitute(db: Session, data: dict, *, created_by=None) -> MaterialSubstitute:
    v = _validate_substitute(db, data)
    o = MaterialSubstitute(**v, created_by=created_by)
    db.add(o)
    db.flush()
    return o


def update_substitute(db: Session, o: MaterialSubstitute, data: dict) -> MaterialSubstitute:
    merged = _row(o)
    merged.update({k: v for k, v in data.items() if v is not None})
    v = _validate_substitute(db, merged, exclude_id=o.id)
    for k, val in v.items():
        setattr(o, k, val)
    db.flush()
    return o


def substitute_suggestions(db: Session, *, material_id: int, bom_id=None, on_date=None) -> list[dict]:
    """缺料时给可用替代料。只给建议，不改 BOM、不代替仓管决定。"""
    if not material_id:
        return []
    day = _d(on_date, field="查询日期") or date.today()
    stmt = select(MaterialSubstitute).where(
        MaterialSubstitute.material_id == int(material_id),
        MaterialSubstitute.is_active.is_(True),
    )
    rows = list(db.scalars(stmt).all())
    out = []
    for s in rows:
        if s.bom_id and (not bom_id or int(s.bom_id) != int(bom_id)):
            continue
        if s.effective_from and day < s.effective_from:
            continue
        if s.effective_to and day > s.effective_to:
            continue
        m = db.get(Material, s.substitute_material_id)
        out.append({
            **substitute_out(db, s),
            "available_qty": None,  # 库存可用量由仓储域决定，这里不越界取数
            "spec": m.spec if m else None,
            "unit": m.unit if m else None,
        })
    out.sort(key=lambda x: (-(x.get("priority") or 0), x["id"]))
    return out


# ──────────────────────────── 工程变更 ECN ────────────────────────────

def ecn_out(db: Session, o: EngineeringChange) -> dict:
    return _row(o, {
        "sku_name": _name(db, Sku, o.sku_id),
        "sku_code": _name(db, Sku, o.sku_id, "code"),
    })


def _ecn_stmt(*, status=None, change_type=None, sku_id=None, keyword=None):
    stmt = select(EngineeringChange)
    if status:
        stmt = stmt.where(EngineeringChange.status == status)
    if change_type:
        stmt = stmt.where(EngineeringChange.change_type == change_type)
    if sku_id:
        stmt = stmt.where(EngineeringChange.sku_id == int(sku_id))
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(EngineeringChange.code.like(kw), EngineeringChange.title.like(kw)))
    return stmt


def list_ecns(db: Session, *, offset=0, limit=20, **filters):
    return list(db.scalars(
        _ecn_stmt(**filters).order_by(EngineeringChange.id.desc()).offset(offset).limit(limit)
    ).all())


def count_ecns(db: Session, **filters) -> int:
    return _count(db, _ecn_stmt(**filters))


def get_ecn(db: Session, eid: int):
    return db.get(EngineeringChange, int(eid))


def _ecode_exists(db: Session, code: str) -> bool:
    return db.scalar(select(EngineeringChange.id).where(EngineeringChange.code == code)) is not None


def create_ecn(db: Session, data: dict, *, created_by=None) -> EngineeringChange:
    title = (data.get("title") or "").strip()
    if not title:
        raise BasicStateError("变更标题不能为空")
    ctype = data.get("change_type") or "bom"
    if ctype not in ECN_TYPES:
        raise BasicStateError(f"变更类型必须是 {'/'.join(ECN_TYPES)}")
    code = resolve_code(db, biz_type=BizType.ECN, code=data.get("code"),
                        exists=lambda c: _ecode_exists(db, c))
    o = EngineeringChange(
        code=code, title=title, change_type=ctype, status="draft",
        product_id=data.get("product_id") or None,
        sku_id=data.get("sku_id") or None,
        bom_id=data.get("bom_id") or None,
        reason=(data.get("reason") or "").strip() or None,
        description=(data.get("description") or "").strip() or None,
        before_snapshot=data.get("before_snapshot"),
        after_snapshot=data.get("after_snapshot"),
        effective_date=_d(data.get("effective_date"), field="生效日期"),
        remark=(data.get("remark") or "").strip() or None,
        created_by=created_by,
    )
    db.add(o)
    db.flush()
    return o


def update_ecn(db: Session, o: EngineeringChange, data: dict) -> EngineeringChange:
    if o.status not in ("draft", "pending", "rejected"):
        raise BasicStateError("已批准/已执行/已作废的 ECN 不能修改，请新建变更单")
    if "title" in data and data["title"] is not None:
        t = str(data["title"]).strip()
        if not t:
            raise BasicStateError("变更标题不能为空")
        o.title = t
    if data.get("change_type"):
        if data["change_type"] not in ECN_TYPES:
            raise BasicStateError(f"变更类型必须是 {'/'.join(ECN_TYPES)}")
        o.change_type = data["change_type"]
    for k in ("product_id", "sku_id", "bom_id", "reason", "description",
              "before_snapshot", "after_snapshot", "remark"):
        if k in data and data[k] is not None:
            setattr(o, k, data[k])
    if "effective_date" in data:
        o.effective_date = _d(data.get("effective_date"), field="生效日期")
    db.flush()
    return o


def _ecn_flow(db: Session, o: EngineeringChange, allowed: tuple[str, ...], target: str,
              *, actor_id=None, reason=None) -> EngineeringChange:
    if o.status not in allowed:
        raise BasicStateError(f"当前状态「{o.status}」不能变更为「{target}」")
    # 校验一律放在改字段之前：抛异常时对象必须保持原样，否则调用方拿到半改不改的对象
    if target == "rejected" and not (reason or "").strip():
        raise BasicStateError("驳回必须填写原因")
    o.status = target
    if target == "approved":
        o.approved_by, o.approved_at = actor_id, _now()
    elif target == "rejected":
        o.reject_reason = reason.strip()
    elif target == "implemented":
        o.applied_at = _now()
    db.flush()
    return o


def ecn_stats(db: Session) -> dict:
    rows = db.execute(
        select(EngineeringChange.status, func.count()).group_by(EngineeringChange.status)
    ).all()
    by_status = {s: int(c) for s, c in rows}
    return {
        "total": sum(by_status.values()),
        "pending": by_status.get("pending", 0),
        "implemented": by_status.get("implemented", 0),
        "by_status": by_status,
    }


# ──────────────────────────── 设备停机记录 ────────────────────────────

def downtime_out(db: Session, o: EquipmentDowntime) -> dict:
    return _row(o, {
        "equipment_name": _name(db, Equipment, o.equipment_id),
        "equipment_code": _name(db, Equipment, o.equipment_id, "code"),
    })


def _downtime_stmt(*, equipment_id=None, reason_code=None, status=None, date_from=None, date_to=None):
    stmt = select(EquipmentDowntime)
    if equipment_id:
        stmt = stmt.where(EquipmentDowntime.equipment_id == int(equipment_id))
    if reason_code:
        stmt = stmt.where(EquipmentDowntime.reason_code == reason_code)
    if status:
        stmt = stmt.where(EquipmentDowntime.status == status)
    if date_from:
        stmt = stmt.where(func.date(EquipmentDowntime.started_at) >= _d(date_from, field="开始日期"))
    if date_to:
        stmt = stmt.where(func.date(EquipmentDowntime.started_at) <= _d(date_to, field="结束日期"))
    return stmt


def list_downtimes(db: Session, *, offset=0, limit=20, **filters):
    return list(db.scalars(
        _downtime_stmt(**filters).order_by(EquipmentDowntime.id.desc()).offset(offset).limit(limit)
    ).all())


def count_downtimes(db: Session, **filters) -> int:
    return _count(db, _downtime_stmt(**filters))


def get_downtime(db: Session, did: int):
    return db.get(EquipmentDowntime, int(did))


def _dcode_exists(db: Session, code: str) -> bool:
    return db.scalar(select(EquipmentDowntime.id).where(EquipmentDowntime.code == code)) is not None


def _duration(o: EquipmentDowntime) -> int:
    if not o.ended_at or not o.started_at:
        return 0
    delta = (o.ended_at - o.started_at).total_seconds()
    if delta < 0:
        raise BasicStateError("结束时间不能早于开始时间")
    return int(round(delta / 60))


def create_downtime(db: Session, data: dict, *, created_by=None) -> EquipmentDowntime:
    eq = int(data.get("equipment_id") or 0)
    if not eq or not db.get(Equipment, eq):
        raise BasicStateError("设备不存在")
    reason = data.get("reason_code") or "breakdown"
    if reason not in DOWNTIME_REASONS:
        raise BasicStateError(f"停机原因必须是 {'/'.join(DOWNTIME_REASONS)}")
    started = _dt(data.get("started_at"), field="开始时间") or _now()
    ended = _dt(data.get("ended_at"), field="结束时间")
    code = resolve_code(db, biz_type=BizType.DOWNTIME, code=data.get("code"),
                        exists=lambda c: _dcode_exists(db, c))
    o = EquipmentDowntime(
        code=code, equipment_id=eq, task_id=data.get("task_id") or None,
        reason_code=reason, status="open", started_at=started, ended_at=ended,
        description=(data.get("description") or "").strip() or None,
        responsible_id=data.get("responsible_id") or None,
        created_by=created_by,
    )
    if ended:
        o.duration_minutes = _duration(o)
        o.status = "closed"
    db.add(o)
    db.flush()
    return o


def update_downtime(db: Session, o: EquipmentDowntime, data: dict) -> EquipmentDowntime:
    if o.status == "closed":
        raise BasicStateError("已结束的停机记录不能修改")
    if data.get("reason_code"):
        if data["reason_code"] not in DOWNTIME_REASONS:
            raise BasicStateError(f"停机原因必须是 {'/'.join(DOWNTIME_REASONS)}")
        o.reason_code = data["reason_code"]
    if data.get("started_at"):
        o.started_at = _dt(data["started_at"], field="开始时间")
    for k in ("equipment_id", "task_id", "description", "responsible_id"):
        if k in data and data[k] is not None:
            setattr(o, k, data[k])
    db.flush()
    return o


def close_downtime(db: Session, o: EquipmentDowntime, *, ended_at=None) -> EquipmentDowntime:
    if o.status == "closed":
        raise BasicStateError("停机记录已经结束了")
    ended = _dt(ended_at, field="结束时间") or _now()
    delta = (ended - o.started_at).total_seconds()
    if delta < 0:
        raise BasicStateError("结束时间不能早于开始时间")
    # 先算完再赋值：时长算不出来时这条记录保持原样
    o.ended_at = ended
    o.duration_minutes = int(round(delta / 60))
    o.status = "closed"
    db.flush()
    return o


def downtime_stats(db: Session, *, date_from=None, date_to=None) -> dict:
    base = _downtime_stmt(date_from=date_from, date_to=date_to).where(
        EquipmentDowntime.status == "closed"
    )
    total_cnt = _count(db, base)
    total_min = int(db.scalar(
        base.with_only_columns(func.coalesce(func.sum(EquipmentDowntime.duration_minutes), 0)).order_by(None)
    ) or 0)
    reason_rows = db.execute(
        select(EquipmentDowntime.reason_code, func.count(),
               func.coalesce(func.sum(EquipmentDowntime.duration_minutes), 0))
        .where(EquipmentDowntime.status == "closed")
        .group_by(EquipmentDowntime.reason_code)
    ).all()
    return {
        "count": total_cnt,
        "total_minutes": total_min,
        "by_reason": {r: {"count": int(c), "minutes": int(m)} for r, c, m in reason_rows},
    }


# ──────────────────────────── 供应商评分 ────────────────────────────

def compute_score(o: SupplierScore) -> None:
    """唯一算分口径。分项都按 0~100，`total_score` 与 `grade` 永远由系统算，不收前端传值。"""
    total = sum(float(getattr(o, k) or 0) * w for k, w in SCORE_WEIGHTS.items())
    o.total_score = round(total, 2)
    o.grade = next(g for cut, g in GRADE_CUTOFFS if total >= cut)


def score_out(db: Session, o: SupplierScore) -> dict:
    return _row(o, {
        "supplier_name": _name(db, Supplier, o.supplier_id),
        "supplier_code": _name(db, Supplier, o.supplier_id, "code"),
    })


def _score_stmt(*, supplier_id=None, period=None, grade=None):
    stmt = select(SupplierScore)
    if supplier_id:
        stmt = stmt.where(SupplierScore.supplier_id == int(supplier_id))
    if period:
        stmt = stmt.where(SupplierScore.period == period)
    if grade:
        stmt = stmt.where(SupplierScore.grade == grade)
    return stmt


def list_scores(db: Session, *, offset=0, limit=20, **filters):
    return list(db.scalars(
        _score_stmt(**filters).order_by(SupplierScore.period.desc(), SupplierScore.id.desc())
        .offset(offset).limit(limit)
    ).all())


def count_scores(db: Session, **filters) -> int:
    return _count(db, _score_stmt(**filters))


def get_score(db: Session, sid: int):
    return db.get(SupplierScore, int(sid))


def _score_values(db: Session, data: dict, *, exclude_id=None) -> dict:
    sid = int(data.get("supplier_id") or 0)
    if not sid or not db.get(Supplier, sid):
        raise BasicStateError("供应商不存在")
    period = (data.get("period") or "").strip()
    if not period:
        raise BasicStateError("评分期间不能为空（如 2026-10 或 2026Q4）")
    dup = select(SupplierScore.id).where(
        SupplierScore.supplier_id == sid, SupplierScore.period == period
    )
    if exclude_id:
        dup = dup.where(SupplierScore.id != int(exclude_id))
    if db.scalar(dup) is not None:
        raise BasicStateError("该供应商此期间已有评分，请直接修改")
    return {
        "supplier_id": sid,
        "period": period,
        "quality_score": _num(data.get("quality_score", 0), field="质量分"),
        "delivery_score": _num(data.get("delivery_score", 0), field="交期分"),
        "price_score": _num(data.get("price_score", 0), field="价格分"),
        "service_score": _num(data.get("service_score", 0), field="服务分"),
        "evaluated_at": _d(data.get("evaluated_at"), field="评分日期"),
        "remark": (data.get("remark") or "").strip() or None,
    }


def create_score(db: Session, data: dict, *, created_by=None) -> SupplierScore:
    v = _score_values(db, data)
    o = SupplierScore(**v, created_by=created_by)
    compute_score(o)
    db.add(o)
    db.flush()
    return o


def update_score(db: Session, o: SupplierScore, data: dict) -> SupplierScore:
    merged = _row(o)
    merged.update({k: v for k, v in data.items() if v is not None})
    v = _score_values(db, merged, exclude_id=o.id)
    for k, val in v.items():
        setattr(o, k, val)
    compute_score(o)
    db.flush()
    return o


def score_stats(db: Session, *, supplier_id=None) -> dict:
    base = _score_stmt(supplier_id=supplier_id)
    total = _count(db, base)
    avg = db.scalar(
        base.with_only_columns(func.avg(SupplierScore.total_score)).order_by(None)
    )
    grade_rows = db.execute(
        select(SupplierScore.grade, func.count()).group_by(SupplierScore.grade)
    ).all()
    by_supplier = db.execute(
        select(SupplierScore.supplier_id, func.avg(SupplierScore.total_score), func.count())
        .group_by(SupplierScore.supplier_id)
        .order_by(func.avg(SupplierScore.total_score).desc())
        .limit(20)
    ).all()
    return {
        "total": total,
        "avg_score": round(float(avg), 2) if avg is not None else None,
        "by_grade": {g: int(c) for g, c in grade_rows},
        "by_supplier": [
            {"supplier_id": int(s), "supplier_name": _name(db, Supplier, s),
             "avg_score": round(float(a), 2), "count": int(c)}
            for s, a, c in by_supplier
        ],
    }
