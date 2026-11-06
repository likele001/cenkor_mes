# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""检验单 crud 与检验台账

两件事放在一起，因为它们共用一套「检验标准」：

1. **检验单**（`inspection_orders`）——按批次/按次判定，四类共用一套结构。
2. **检验台账**（读已有的 `inspection_records`）——逐件报工审核时填的检查项，
   此前只能写不能查，等于填了白填。这里把它查出来。

判定口径（改之前先读）：

- **明细是模板的快照**，判定只看明细上的 `upper_limit` / `lower_limit`，不回读模板。
- **测量项自动判**：上下限都是数字且录了数值，直接算 pass/fail；人只负责录数。
- **必检项必须都有结果才能判定**，`is_required=0` 的项允许空着。
- **判定后明细锁定**（passed / failed / closed / cancelled）。要重检开新单，
  不给改历史的口子——改了追溯就断了。
- **数量三个口径互相约束**：抽样 ≤ 送检，接收 + 拒收 ≤ 送检。
"""
from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.inspection import (
    CANCELLABLE_STATUSES,
    INSPECTION_HANDLINGS,
    INSPECTION_TYPES,
    LOCKED_STATUSES,
    ITEM_RESULTS,
    InspectionOrder,
    InspectionOrderItem,
)
from app.models.material import Material
from app.models.process import Process
from app.models.purchase import PurchaseOrder
from app.models.quality import (
    DefectCode,
    InspectionRecord,
    InspectionTemplate,
    InspectionTemplateItem,
)
from app.models.report_unit import ReportUnit, ReportUnitAudit
from app.models.shipment import Shipment
from app.models.sku import Sku
from app.models.supplier import Supplier
from app.models.task import Task
from app.models.work_order import WorkOrder


class InspectionStateError(ValueError):
    """状态机或口径不满足，API 层转 400"""


def _now() -> datetime:
    return datetime.now()


def _to_float(v) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


# ──────────────────────────── 序列化 ────────────────────────────

def item_out(it: InspectionOrderItem) -> dict:
    return {
        "id": it.id,
        "seq": it.seq,
        "template_item_id": it.template_item_id,
        "item_name": it.item_name,
        "item_type": it.item_type,
        "standard_value": it.standard_value,
        "upper_limit": it.upper_limit,
        "lower_limit": it.lower_limit,
        "unit": it.unit,
        "is_required": bool(it.is_required),
        "result": it.result,
        "measured_value": it.measured_value,
        "defect_code_id": it.defect_code_id,
        "defect_code": it.defect_code.code if it.defect_code else None,
        "defect_name": it.defect_code.name if it.defect_code else None,
        "defect_severity": it.defect_code.severity if it.defect_code else None,
        "remark": it.remark,
    }


def _user_label(u) -> str | None:
    """User 模型没有 `name`，显示名是 `full_name`，退回 `username`。"""
    if not u:
        return None
    return getattr(u, "full_name", None) or getattr(u, "username", None)


def inspection_out(o: InspectionOrder, with_items: bool = True) -> dict:
    items = o.items or []
    filled = [it for it in items if it.result]
    fails = [it for it in items if it.result == "fail"]
    d = {
        "id": o.id,
        "code": o.code,
        "inspection_type": o.inspection_type,
        "status": o.status,
        "source_type": o.source_type,
        "source_id": o.source_id,
        "source_code": o.source_code,
        "material_id": o.material_id,
        "sku_id": o.sku_id,
        "item_name": o.item_name,
        "batch_no": o.batch_no,
        "supplier_id": o.supplier_id,
        "customer_id": o.customer_id,
        "qty": o.qty,
        "sample_qty": o.sample_qty,
        "accept_qty": o.accept_qty,
        "reject_qty": o.reject_qty,
        "template_id": o.template_id,
        "handling": o.handling,
        "conclusion": o.conclusion,
        "inspector_id": o.inspector_id,
        "inspector_name": _user_label(o.inspector),
        "inspected_at": o.inspected_at.isoformat() if o.inspected_at else None,
        "created_by": o.created_by,
        "closed_at": o.closed_at.isoformat() if o.closed_at else None,
        "remark": o.remark,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        # 进度：前端不用自己数
        "item_total": len(items),
        "item_filled": len(filled),
        "item_failed": len(fails),
        "is_locked": o.is_locked,
        "is_closed": o.is_closed,
    }
    if with_items:
        d["items"] = [item_out(it) for it in items]
    return d


# ──────────────────────────── 查询 ────────────────────────────

def get_inspection(db: Session, inspection_id: int) -> InspectionOrder | None:
    return db.scalars(
        select(InspectionOrder)
        .where(InspectionOrder.id == inspection_id)
        .options(
            selectinload(InspectionOrder.items).selectinload(InspectionOrderItem.defect_code),
            selectinload(InspectionOrder.inspector),
        )
    ).first()


def _list_stmt(
    *,
    keyword: str | None = None,
    inspection_type: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    supplier_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(InspectionOrder)
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                InspectionOrder.code.like(kw),
                InspectionOrder.source_code.like(kw),
                InspectionOrder.item_name.like(kw),
                InspectionOrder.batch_no.like(kw),
            )
        )
    if inspection_type:
        stmt = stmt.where(InspectionOrder.inspection_type == inspection_type)
    if status:
        stmt = stmt.where(InspectionOrder.status == status)
    if source_type:
        stmt = stmt.where(InspectionOrder.source_type == source_type)
    if supplier_id:
        stmt = stmt.where(InspectionOrder.supplier_id == supplier_id)
    if date_from:
        stmt = stmt.where(func.date(InspectionOrder.created_at) >= date_from)
    if date_to:
        stmt = stmt.where(func.date(InspectionOrder.created_at) <= date_to)
    return stmt


def list_inspections(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 20,
    **filters,
) -> list[InspectionOrder]:
    stmt = (
        _list_stmt(**filters)
        .options(
            selectinload(InspectionOrder.items).selectinload(InspectionOrderItem.defect_code),
            selectinload(InspectionOrder.inspector),
        )
        .order_by(InspectionOrder.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def count_inspections(db: Session, **filters) -> int:
    # 计数不需要明细，去掉 order_by 的负担
    stmt = _list_stmt(**filters).with_only_columns(func.count(InspectionOrder.id))
    return int(db.scalar(stmt) or 0)


# ──────────────────────────── 明细处理 ────────────────────────────

def _auto_judge_item(it: InspectionOrderItem) -> None:
    """测量项按快照的上下限自动判定。

    `na` 不覆盖（人显式声明不适用）；不是数字就留空让人判——宁可没结论，
    也不要系统瞎猜一个结论出来。
    """
    if it.item_type != "measure" or it.result == "na":
        return
    raw = (it.measured_value or "").strip()
    if not raw:
        return
    v = _to_float(raw)
    if v is None:
        return
    lo = _to_float(it.lower_limit)
    hi = _to_float(it.upper_limit)
    if lo is None and hi is None:
        return
    ok = (lo is None or v >= lo) and (hi is None or v <= hi)
    it.result = "pass" if ok else "fail"


def _truthy(v) -> bool:
    """`is_required` 可能来自 JSON（bool）、前端表单（"0"/"1"）或 DB（1/0）。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    return str(v).strip().lower() not in ("0", "false", "no", "off", "")


def _row_to_item(row: dict, seq: int) -> InspectionOrderItem:
    result = (row.get("result") or "").strip() or None
    if result is not None and result not in ITEM_RESULTS:
        raise InspectionStateError(f"检验结果必须是 {'/'.join(ITEM_RESULTS)}")
    it = InspectionOrderItem(
        seq=int(row.get("seq") or seq),
        template_item_id=row.get("template_item_id"),
        item_name=(row.get("item_name") or "").strip() or "未命名检查项",
        item_type=(row.get("item_type") or "pass_fail"),
        standard_value=row.get("standard_value"),
        upper_limit=row.get("upper_limit"),
        lower_limit=row.get("lower_limit"),
        unit=row.get("unit"),
        is_required=_truthy(row.get("is_required", True)),
        result=result,
        measured_value=(row.get("measured_value") or "").strip() or None,
        defect_code_id=row.get("defect_code_id"),
        remark=(row.get("remark") or "").strip() or None,
    )
    _auto_judge_item(it)
    return it


def _expand_template(db: Session, template_id: int) -> list[dict]:
    tpl = db.get(InspectionTemplate, int(template_id))
    if not tpl:
        raise InspectionStateError("检验模板不存在")
    if not tpl.is_active:
        raise InspectionStateError("检验模板已停用，请换一个")
    rows = []
    for it in sorted(tpl.items or [], key=lambda x: x.seq):
        rows.append({
            "seq": it.seq,
            "template_item_id": it.id,
            "item_name": it.item_name,
            "item_type": it.item_type,
            "standard_value": it.standard_value,
            "upper_limit": it.upper_limit,
            "lower_limit": it.lower_limit,
            "unit": it.unit,
            "is_required": bool(it.is_required),
        })
    return rows


def _merge_rows(base: list[dict], incoming: list[dict] | None) -> list[dict]:
    """模板展开 + 手工行的合并。

    按 `template_item_id`（其次 `seq`）匹配：匹配上就覆盖那条快照上的结果，
    匹配不上就追加为新项。这样前端可以「先按模板带出，再把录到的值回贴」。
    """
    if not incoming:
        return base
    merged = [dict(r) for r in base]
    by_tpl = {r["template_item_id"]: r for r in merged if r.get("template_item_id")}
    by_seq = {int(r.get("seq") or 0): r for r in merged}

    extra: list[dict] = []
    for row in incoming:
        tid = row.get("template_item_id")
        target = by_tpl.get(tid) if tid else None
        if target is None:
            target = by_seq.get(int(row.get("seq") or 0)) if row.get("seq") else None
        if target is not None:
            for k in ("result", "measured_value", "defect_code_id", "remark"):
                if k in row and row[k] is not None:
                    target[k] = row[k]
        else:
            extra.append(dict(row))
    return merged + extra


def _patch_items(db: Session, o: InspectionOrder, rows: list[dict]) -> None:
    """按 seq / template_item_id 把传入的行**合并**到现有明细上。

    改单不能整单替换：前端往往只提交改过的那几项（比如检验员只录了第 1 项的结果），
    整单替换会把没提交的检查项直接删掉，判定依据就没了。不认识的项才追加。
    """
    by_seq = {it.seq: it for it in (o.items or [])}
    by_tpl = {it.template_item_id: it for it in (o.items or []) if it.template_item_id}
    extra: list[dict] = []

    for row in rows:
        tid = row.get("template_item_id")
        target = by_tpl.get(tid) if tid else None
        if target is None and row.get("seq"):
            target = by_seq.get(int(row["seq"]))
        if target is None:
            extra.append(row)
            continue

        # 用 `in` 判断而不是 `is not None`：显式传 null 表示「清空这一项」，
        # 也是调用方的意图，不该被当成「没传」跳过。
        if "item_name" in row and row["item_name"]:
            target.item_name = row["item_name"]
        if "item_type" in row and row["item_type"]:
            target.item_type = row["item_type"]
        if "standard_value" in row:
            target.standard_value = row["standard_value"]
        if "upper_limit" in row:
            target.upper_limit = row["upper_limit"]
        if "lower_limit" in row:
            target.lower_limit = row["lower_limit"]
        if "unit" in row:
            target.unit = row["unit"]
        if "is_required" in row and row["is_required"] is not None:
            target.is_required = _truthy(row["is_required"])
        if "result" in row:
            target.result = (row["result"] or "").strip() or None
        if "measured_value" in row:
            target.measured_value = (row["measured_value"] or "").strip() or None
        if "defect_code_id" in row:
            target.defect_code_id = row["defect_code_id"]
        if "remark" in row:
            target.remark = (row["remark"] or "").strip() or None
        _auto_judge_item(target)

    if extra:
        max_seq = max((it.seq for it in (o.items or [])), default=0)
        for row in extra:
            max_seq += 1
            o.items.append(_row_to_item(row, max_seq))
    db.flush()


def _item_to_row(it: InspectionOrderItem) -> dict:
    """把已落库的明细转回行字典，换模板时按 template_item_id 带回已录的值。"""
    return {
        "seq": it.seq,
        "template_item_id": it.template_item_id,
        "item_name": it.item_name,
        "item_type": it.item_type,
        "standard_value": it.standard_value,
        "upper_limit": it.upper_limit,
        "lower_limit": it.lower_limit,
        "unit": it.unit,
        "is_required": it.is_required,
        "result": it.result,
        "measured_value": it.measured_value,
        "defect_code_id": it.defect_code_id,
        "remark": it.remark,
    }


def _replace_items(db: Session, o: InspectionOrder, rows: list[dict]) -> None:
    """整单替换明细（仅换模板时用）。

    先 delete + flush 再插入：唯一键是 `(inspection_order_id, seq)`，
    同一 flush 里既删又插会撞约束，必须先让删除落地。删完还要 expire 关系缓存，
    否则 `o.items` 里仍挂着已删除的对象。
    """
    for old in list(o.items or []):
        db.delete(old)
    db.flush()
    db.expire(o, ["items"])

    seqs: set[int] = set()
    idx = 0
    for row in rows:
        idx += 1
        it = _row_to_item(row, idx)
        # seq 重复会撞唯一键，顺延处理而不是报错——调用方不一定保证 seq 唯一
        while it.seq in seqs:
            it.seq += 1
        seqs.add(it.seq)
        o.items.append(it)
    db.flush()


# ──────────────────────────── 建单 / 改单 ────────────────────────────

def _resolve_source(db: Session, o: InspectionOrder, source_type: str, source_id: int | None) -> None:
    """按来源单据回填对象与单号。

    只做「带出」，不改来源单据的状态——检验单没有权力去推进采购单或工单。
    """
    if source_type not in ("purchase_order", "work_order", "shipment", "task", "manual"):
        raise InspectionStateError("来源单据类型不支持")
    o.source_type = source_type
    o.source_id = None
    if source_type == "manual" or not source_id:
        return

    o.source_id = int(source_id)
    if source_type == "purchase_order":
        po = db.get(PurchaseOrder, int(source_id))
        if not po:
            raise InspectionStateError("采购单不存在")
        o.source_code = po.code
        o.supplier_id = po.supplier_id
        # 采购单只有一条明细时把物料带出来——多数来料检验就是一单一料，
        # 不自动带我就要用户再从物料列表里挑一次，白费一道手。
        if len(po.items or []) == 1 and not o.material_id:
            only = po.items[0]
            if only.material:
                o.material_id = only.material_id
                o.item_name = o.item_name or only.material.name
        if not o.qty:
            o.qty = sum(int(it.qty or 0) for it in (po.items or []))
    elif source_type == "work_order":
        wo = db.get(WorkOrder, int(source_id))
        if not wo:
            raise InspectionStateError("工单不存在")
        o.source_code = f"WO{wo.id}"
        if not o.sku_id:
            o.sku_id = wo.sku_id
        if not o.qty:
            o.qty = int(wo.qty or 0)
        if not o.item_name and wo.sku:
            o.item_name = wo.sku.name
    elif source_type == "shipment":
        sh = db.get(Shipment, int(source_id))
        if not sh:
            raise InspectionStateError("发货单不存在")
        o.source_code = sh.code
    elif source_type == "task":
        task = db.get(Task, int(source_id))
        if not task:
            raise InspectionStateError("任务不存在")
        o.source_code = task.task_code


def create_inspection(
    db: Session,
    *,
    code: str,
    inspection_type: str,
    qty: int = 0,
    sample_qty: int = 0,
    template_id: int | None = None,
    items: list[dict] | None = None,
    source_type: str = "manual",
    source_id: int | None = None,
    material_id: int | None = None,
    sku_id: int | None = None,
    item_name: str | None = None,
    batch_no: str | None = None,
    supplier_id: int | None = None,
    customer_id: int | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> InspectionOrder:
    if inspection_type not in INSPECTION_TYPES:
        raise InspectionStateError(f"检验类型必须是 {'/'.join(INSPECTION_TYPES)}")

    o = InspectionOrder(
        code=code,
        inspection_type=inspection_type,
        status="draft",
        qty=int(qty or 0),
        sample_qty=int(sample_qty or 0),
        template_id=template_id,
        batch_no=(batch_no or "").strip() or None,
        remark=(remark or "").strip() or None,
        created_by=created_by,
    )

    _resolve_source(db, o, source_type, source_id)

    # 显式传入的对象优先于来源带出的
    if material_id:
        m = db.get(Material, int(material_id))
        if not m:
            raise InspectionStateError("物料不存在")
        o.material_id = m.id
        o.item_name = item_name or m.name
        o.sku_id = None
    if sku_id:
        s = db.get(Sku, int(sku_id))
        if not s:
            raise InspectionStateError("产品不存在")
        o.sku_id = s.id
        o.item_name = item_name or s.name
        o.material_id = None
    if item_name and not o.item_name:
        o.item_name = item_name.strip()
    if supplier_id:
        o.supplier_id = int(supplier_id)
    if customer_id:
        if not db.get(Customer, int(customer_id)):
            raise InspectionStateError("客户不存在")
        o.customer_id = int(customer_id)

    # IQC 必须知道检的是哪个物料，否则这张单没有意义
    if inspection_type == "iqc" and not o.material_id and not o.item_name:
        raise InspectionStateError("来料检验必须指定物料或至少填写检验对象名称")

    if o.sample_qty > o.qty:
        raise InspectionStateError("抽样数量不能大于送检数量")

    rows: list[dict] = []
    if template_id:
        rows = _expand_template(db, int(template_id))
    rows = _merge_rows(rows, items)
    if not rows:
        raise InspectionStateError("没有任何检查项：请选择检验模板或至少添加一项")

    db.add(o)
    db.flush()
    _patch_items(db, o, rows)  # 新单 items 为空，合并 = 全部追加
    db.flush()
    return o


def update_inspection(
    db: Session,
    o: InspectionOrder,
    *,
    qty: int | None = None,
    sample_qty: int | None = None,
    batch_no: str | None = None,
    item_name: str | None = None,
    material_id: int | None = None,
    sku_id: int | None = None,
    supplier_id: int | None = None,
    customer_id: int | None = None,
    template_id: int | None = None,
    items: list[dict] | None = None,
    remark: str | None = None,
) -> InspectionOrder:
    if o.status in LOCKED_STATUSES:
        raise InspectionStateError("已判定/已关闭的检验单不能修改，要重检请开新单")

    if qty is not None:
        o.qty = int(qty)
    if sample_qty is not None:
        o.sample_qty = int(sample_qty)
    if o.sample_qty > o.qty:
        raise InspectionStateError("抽样数量不能大于送检数量")
    if batch_no is not None:
        o.batch_no = batch_no.strip() or None
    if item_name is not None:
        o.item_name = item_name.strip() or None
    if material_id is not None:
        m = db.get(Material, int(material_id))
        if not m:
            raise InspectionStateError("物料不存在")
        o.material_id, o.sku_id = m.id, None
        o.item_name = o.item_name or m.name
    if sku_id is not None:
        s = db.get(Sku, int(sku_id))
        if not s:
            raise InspectionStateError("产品不存在")
        o.sku_id, o.material_id = s.id, None
        o.item_name = o.item_name or s.name
    if supplier_id is not None:
        o.supplier_id = int(supplier_id) or None
    if customer_id is not None:
        if customer_id and not db.get(Customer, int(customer_id)):
            raise InspectionStateError("客户不存在")
        o.customer_id = int(customer_id) or None
    if remark is not None:
        o.remark = remark.strip() or None

    # 换模板：整单重铺，但已录的结果/实测值按 template_item_id 尽量带回——
    # 检验员录了一半换模板，不能让他重录一遍。
    if template_id and int(template_id) != (o.template_id or 0):
        o.template_id = int(template_id)
        base = _expand_template(db, int(template_id))
        old_rows = [_item_to_row(it) for it in (o.items or []) if it.template_item_id]
        merged = _merge_rows(base, old_rows)
        if items:
            merged = _merge_rows(merged, items)
        _replace_items(db, o, merged)
    elif items is not None:
        _patch_items(db, o, items)  # 只提交改动过的项，别把没提交的删掉

    db.flush()
    return o


# ──────────────────────────── 状态流转 ────────────────────────────

def _need(o: InspectionOrder, allowed: tuple[str, ...], action: str) -> None:
    if o.status not in allowed:
        raise InspectionStateError(f"当前状态「{o.status}」不能{action}")


def submit_inspection(db: Session, o: InspectionOrder, submitted_by: int | None = None) -> InspectionOrder:
    _need(o, ("draft",), "提交检验")
    if not o.items:
        raise InspectionStateError("没有检查项，无法提交")
    if not o.qty:
        raise InspectionStateError("送检数量为 0，无法提交")
    o.status = "pending"
    db.flush()
    return o


def judge_inspection(
    db: Session,
    o: InspectionOrder,
    *,
    inspector_id: int,
    accept_qty: int | None = None,
    reject_qty: int | None = None,
    handling: str | None = None,
    conclusion: str | None = None,
) -> InspectionOrder:
    """判定：必检项齐全后，有 fail 即不合格。

    不合格时 `handling`（退货/让步/返工/报废）是**必填**的——判了不合格却不说怎么办，
    等于把问题原样丢回给现场。这是这张单存在的意义所在。

    所有校验都放在改字段之前：抛异常时对象必须保持原样，否则调用方拿到一个
    半改不改的对象会很难收拾。
    """
    _need(o, ("pending",), "判定")
    if not o.items:
        raise InspectionStateError("没有检查项，无法判定")

    missing = [it for it in o.items if it.is_required and not it.result]
    if missing:
        names = "、".join(it.item_name for it in missing[:3])
        raise InspectionStateError(f"还有 {len(missing)} 个必检项未录结果（如：{names}）")

    if accept_qty is None and reject_qty is None:
        accept_qty = o.qty
        reject_qty = 0
    accept_qty = int(accept_qty or 0)
    reject_qty = int(reject_qty or 0)
    if accept_qty < 0 or reject_qty < 0:
        raise InspectionStateError("接收/拒收数量不能为负")
    if accept_qty + reject_qty > o.qty:
        raise InspectionStateError("接收 + 拒收不能大于送检数量")

    fails = [it for it in o.items if it.result == "fail"]
    critical: list[InspectionOrderItem] = []
    for it in fails:
        if not it.defect_code_id:
            continue
        dc = db.get(DefectCode, int(it.defect_code_id))
        if dc and dc.severity == "critical":
            critical.append(it)

    # 校验完再动手改
    if fails:
        if not handling:
            raise InspectionStateError("判定不合格时必须选择处置方式（退货/让步接收/返工/报废）")
        if handling not in INSPECTION_HANDLINGS:
            raise InspectionStateError(f"处置方式必须是 {'/'.join(INSPECTION_HANDLINGS)}")

    o.status = "failed" if fails else "passed"
    o.accept_qty = accept_qty
    o.reject_qty = reject_qty
    o.inspector_id = inspector_id
    o.inspected_at = _now()

    if fails:
        o.handling = handling
        tail = f"，其中 {len(critical)} 项为致命缺陷" if critical else ""
        o.conclusion = conclusion or f"共 {len(o.items)} 项，{len(fails)} 项不合格{tail}"
    else:
        o.handling = None
        o.conclusion = conclusion or f"共 {len(o.items)} 项，全部合格"

    db.flush()
    return o


def close_inspection(db: Session, o: InspectionOrder) -> InspectionOrder:
    """登记关闭。只盖 `closed_at`，**不动 status**——判定结论必须留着。"""
    if o.status not in ("passed", "failed"):
        raise InspectionStateError("只有已判定（合格/不合格）的检验单可以关闭")
    if o.closed_at is not None:
        raise InspectionStateError("这张检验单已经关闭了")
    o.closed_at = _now()
    db.flush()
    return o


def cancel_inspection(db: Session, o: InspectionOrder) -> InspectionOrder:
    if o.status not in CANCELLABLE_STATUSES:
        raise InspectionStateError("只有草稿或待检验的检验单可以作废")
    o.status = "cancelled"
    db.flush()
    return o


# ──────────────────────────── 统计与选项 ────────────────────────────

def inspection_stats(db: Session) -> dict:
    rows = db.execute(
        select(InspectionOrder.inspection_type, InspectionOrder.status, func.count())
        .group_by(InspectionOrder.inspection_type, InspectionOrder.status)
    ).all()

    by_type = {t: {"total": 0, "pending": 0, "passed": 0, "failed": 0} for t in INSPECTION_TYPES}
    total = pending = passed = failed = 0
    for itype, status, cnt in rows:
        cnt = int(cnt)
        total += cnt
        bucket = by_type.setdefault(itype, {"total": 0, "pending": 0, "passed": 0, "failed": 0})
        bucket["total"] += cnt
        if status in ("pending", "passed", "failed"):
            bucket[status] += cnt
            if status == "pending":
                pending += cnt
            elif status == "passed":
                passed += cnt
            else:
                failed += cnt

    judged = passed + failed
    # 来料拒收的累计数量，比单数更有经营含义
    reject_qty = int(db.scalar(
        select(func.coalesce(func.sum(InspectionOrder.reject_qty), 0))
        .where(InspectionOrder.status.in_(("passed", "failed")))
    ) or 0)

    return {
        "total": total,
        "pending": pending,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / judged * 100, 1) if judged else None,
        "reject_qty": reject_qty,
        "by_type": by_type,
    }


def template_options(db: Session, *, inspection_type: str | None = None, keyword: str | None = None,
                     limit: int = 50) -> list[dict]:
    stmt = (
        select(InspectionTemplate)
        .where(InspectionTemplate.is_active.is_(True))
        .options(selectinload(InspectionTemplate.items))
        .order_by(InspectionTemplate.id.desc())
        .limit(limit)
    )
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(InspectionTemplate.code.like(kw), InspectionTemplate.name.like(kw)))
    out = []
    for t in db.scalars(stmt).all():
        out.append({
            "id": t.id,
            "code": t.code,
            "name": t.name,
            "process_id": t.process_id,
            "product_id": t.product_id,
            "item_count": len(t.items or []),
        })
    return out


def source_options(db: Session, *, inspection_type: str, keyword: str | None = None,
                   limit: int = 50) -> list[dict]:
    """按检验类型给出可选的来源单据（已确认且可收的采购单等）。"""
    kw = f"%{keyword.strip()}%" if keyword else None
    out: list[dict] = []

    if inspection_type == "iqc":
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.status.in_(("confirmed", "partial_received")))
            .options(selectinload(PurchaseOrder.items), selectinload(PurchaseOrder.supplier))
            .order_by(PurchaseOrder.id.desc())
            .limit(limit)
        )
        if kw:
            stmt = stmt.where(PurchaseOrder.code.like(kw))
        for po in db.scalars(stmt).all():
            out.append({
                "id": po.id,
                "code": po.code,
                "label": f"{po.code} · {po.supplier.name if po.supplier else '未知供应商'}",
                "supplier_id": po.supplier_id,
                "supplier_name": po.supplier.name if po.supplier else None,
                "item_count": len(po.items or []),
                "qty": sum(int(it.qty or 0) for it in (po.items or [])),
            })
    elif inspection_type == "ipqc":
        stmt = select(WorkOrder).options(selectinload(WorkOrder.sku)).order_by(WorkOrder.id.desc()).limit(limit)
        if kw:
            stmt = stmt.where(WorkOrder.id.in_(
                select(WorkOrder.id).join(Sku, Sku.id == WorkOrder.sku_id).where(Sku.name.like(kw))
            ))
        for wo in db.scalars(stmt).all():
            out.append({
                "id": wo.id,
                "code": f"WO{wo.id}",
                "label": f"WO{wo.id} · {wo.sku.name if wo.sku else ''}",
                "sku_id": wo.sku_id,
                "item_name": wo.sku.name if wo.sku else None,
                "qty": int(wo.qty or 0),
            })
    elif inspection_type == "oqc":
        stmt = select(Shipment).order_by(Shipment.id.desc()).limit(limit)
        if kw:
            stmt = stmt.where(Shipment.code.like(kw))
        for sh in db.scalars(stmt).all():
            out.append({
                "id": sh.id,
                "code": sh.code,
                "label": f"{sh.code} · 订单 {sh.order_id}",
                "order_id": sh.order_id,
            })
    elif inspection_type == "fai":
        stmt = select(Task).order_by(Task.id.desc()).limit(limit)
        if kw:
            stmt = stmt.where(Task.task_code.like(kw))
        for t in db.scalars(stmt).all():
            proc = db.get(Process, t.process_id) if t.process_id else None
            out.append({
                "id": t.id,
                "code": t.task_code,
                "label": f"{t.task_code} · {proc.name if proc else ''}",
                "process_id": t.process_id,
                "item_name": proc.name if proc else None,
            })
    return out


# ──────────────────────────── 检验台账（读 inspection_records）────────────────────────────

def _ledger_stmt(
    *,
    keyword: str | None = None,
    result: str | None = None,
    process_id: int | None = None,
    sku_id: int | None = None,
    defect_code_id: int | None = None,
    auditor_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = (
        select(
            InspectionRecord,
            InspectionTemplateItem,
            DefectCode,
            ReportUnitAudit,
            ReportUnit,
            Task,
            Process,
            WorkOrder,
            Sku,
        )
        .join(ReportUnitAudit, ReportUnitAudit.id == InspectionRecord.report_unit_audit_id)
        .join(ReportUnit, ReportUnit.id == ReportUnitAudit.report_unit_id)
        .join(Task, Task.id == ReportUnit.task_id)
        .outerjoin(Process, Process.id == Task.process_id)
        .outerjoin(WorkOrder, WorkOrder.id == Task.work_order_id)
        .outerjoin(Sku, Sku.id == WorkOrder.sku_id)
        .outerjoin(InspectionTemplateItem, InspectionTemplateItem.id == InspectionRecord.template_item_id)
        .outerjoin(DefectCode, DefectCode.id == InspectionRecord.defect_code_id)
    )
    if result:
        stmt = stmt.where(InspectionRecord.result == result)
    if process_id:
        stmt = stmt.where(Task.process_id == process_id)
    if sku_id:
        stmt = stmt.where(WorkOrder.sku_id == sku_id)
    if defect_code_id:
        stmt = stmt.where(InspectionRecord.defect_code_id == defect_code_id)
    if auditor_id:
        stmt = stmt.where(ReportUnitAudit.auditor_id == auditor_id)
    if date_from:
        stmt = stmt.where(func.date(InspectionRecord.created_at) >= date_from)
    if date_to:
        stmt = stmt.where(func.date(InspectionRecord.created_at) <= date_to)
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                InspectionTemplateItem.item_name.like(kw),
                InspectionRecord.measured_value.like(kw),
                InspectionRecord.remark.like(kw),
                ReportUnitAudit.reason.like(kw),
            )
        )
    return stmt


def _ledger_row(row) -> dict:
    rec, item, dc, audit, unit, task, proc, wo, sku = row
    return {
        "id": rec.id,
        "recorded_at": rec.created_at.isoformat() if rec.created_at else None,
        "result": rec.result,
        "measured_value": rec.measured_value,
        "remark": rec.remark,
        "item_name": item.item_name if item else None,
        "item_type": item.item_type if item else None,
        "standard_value": item.standard_value if item else None,
        "upper_limit": item.upper_limit if item else None,
        "lower_limit": item.lower_limit if item else None,
        "unit": item.unit if item else None,
        "defect_code": dc.code if dc else None,
        "defect_name": dc.name if dc else None,
        "defect_severity": dc.severity if dc else None,
        "audit_level": audit.audit_level,
        "audit_action": audit.action,
        "audit_reason": audit.reason,
        "auditor_id": audit.auditor_id,
        "unit_id": unit.id,
        "unit_seq": unit.unit_seq,
        "unit_status": unit.status,
        "unit_result_type": unit.result_type,
        "report_user_id": unit.user_id,
        "task_id": task.id,
        "task_code": task.task_code,
        "process_id": proc.id if proc else None,
        "process_name": proc.name if proc else None,
        "work_order_id": wo.id if wo else None,
        "sku_id": sku.id if sku else None,
        "sku_code": sku.code if sku else None,
        "sku_name": sku.name if sku else None,
    }


def list_ledger(db: Session, *, offset: int = 0, limit: int = 20, **filters) -> list[dict]:
    stmt = (
        _ledger_stmt(**filters)
        .order_by(InspectionRecord.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [_ledger_row(r) for r in db.execute(stmt).all()]


def count_ledger(db: Session, **filters) -> int:
    inner = _ledger_stmt(**filters).with_only_columns(InspectionRecord.id).subquery()
    return int(db.scalar(select(func.count()).select_from(inner)) or 0)


def ledger_detail(db: Session, record_id: int) -> dict | None:
    stmt = _ledger_stmt().where(InspectionRecord.id == record_id)
    row = db.execute(stmt).first()
    return _ledger_row(row) if row else None


def ledger_stats(db: Session, *, date_from: date | None = None, date_to: date | None = None) -> dict:
    """台账统计：总条数、不合格条数、按严重度与按工序分布。

    只统计 `result` 有值的记录；`na`（不适用）不进分母，否则合格率会被稀释。
    """
    filters: dict = {}
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    inner = _ledger_stmt(**filters).with_only_columns(
        InspectionRecord.id,
        InspectionRecord.result,
        InspectionRecord.defect_code_id,
        Task.process_id,
        Process.name,
        DefectCode.severity,
    ).subquery()

    total = int(db.scalar(select(func.count()).select_from(inner)) or 0)
    counted = int(db.scalar(
        select(func.count()).select_from(inner).where(inner.c.result.in_(("pass", "fail")))
    ) or 0)
    failed = int(db.scalar(
        select(func.count()).select_from(inner).where(inner.c.result == "fail")
    ) or 0)

    sev_rows = db.execute(
        select(inner.c.severity, func.count())
        .where(inner.c.result == "fail")
        .group_by(inner.c.severity)
    ).all()
    proc_rows = db.execute(
        select(inner.c.process_id, inner.c.name, func.count())
        .where(inner.c.result == "fail")
        .group_by(inner.c.process_id, inner.c.name)
        .order_by(func.count().desc())
        .limit(10)
    ).all()

    return {
        "total": total,
        "counted": counted,
        "failed": failed,
        "pass_rate": round((counted - failed) / counted * 100, 1) if counted else None,
        "by_severity": {(s or "unknown"): int(c) for s, c in sev_rows},
        "top_processes": [
            {"process_id": pid, "process_name": name or "未指定工序", "failed": int(c)}
            for pid, name, c in proc_rows
        ],
    }
