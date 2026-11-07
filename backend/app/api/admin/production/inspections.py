# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""检验单与检验台账 API

权限分三档，任一即可进菜单，但动作分开挂：

- `inspection.view`    看检验单、看台账、导出
- `inspection.manage`  制单、改单、提交、关闭、作废
- `inspection.audit`   判定（判定就是质检员签字，必须单独授权）

路由顺序有讲究：`/stats`、`/ledger`、`/template-options`、`/source-options`、`/export`
这类静态路径必须注册在 `/{inspection_id}` 之前，否则会被当成 id 解析成 422。
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_any_permissions
from app.core.response import ok
from app.crud.inspection import (
    InspectionStateError,
    cancel_inspection,
    close_inspection,
    count_inspections,
    count_ledger,
    create_inspection,
    get_inspection,
    inspection_out,
    inspection_stats,
    judge_inspection,
    ledger_detail,
    ledger_stats,
    list_inspections,
    list_ledger,
    report_options,
    source_options,
    source_summary,
    submit_inspection,
    template_options,
    update_inspection,
)
from app.models.inspection import (
    INSPECTION_HANDLINGS,
    INSPECTION_STATUSES,
    INSPECTION_TYPES,
    ITEM_RESULTS,
    SOURCE_TYPES,
    InspectionOrder,
)
from app.models.user import User
from app.models.report import Report
from app.services.code_generator import BizType, resolve_code
from app.tasks._sync_excel import make_excel_response

router = APIRouter(
    prefix="/inspections",
    dependencies=[
        Depends(require_any_permissions(["inspection.view", "inspection.manage", "inspection.audit"]))
    ],
)

_WRITE = [Depends(require_any_permissions(["inspection.manage"]))]
_AUDIT = [Depends(require_any_permissions(["inspection.audit"]))]


_TYPE_LABEL = {"iqc": "来料检验", "ipqc": "制程检验", "oqc": "出货检验", "fai": "首件检验"}
_STATUS_LABEL = {
    "draft": "草稿",
    "pending": "待检验",
    "passed": "合格",
    "failed": "不合格",
    "cancelled": "已作废",
}
_HANDLING_LABEL = {"return": "退货", "accept": "让步接收", "rework": "返工", "scrap": "报废"}
_RESULT_LABEL = {"pass": "合格", "fail": "不合格", "na": "不适用"}


# ──────────────────────────── 请求体 ────────────────────────────

class ItemIn(BaseModel):
    seq: int | None = Field(default=None, ge=1)
    template_item_id: int | None = Field(default=None, ge=1)
    item_name: str | None = Field(default=None, max_length=128)
    item_type: str | None = Field(default=None, description="pass_fail / measure / text")
    standard_value: str | None = Field(default=None, max_length=64)
    upper_limit: str | None = Field(default=None, max_length=64)
    lower_limit: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    is_required: bool | None = None
    result: str | None = Field(default=None, description="pass / fail / na，空表示未检")
    measured_value: str | None = Field(default=None, max_length=64)
    defect_code_id: int | None = Field(default=None, ge=1)
    remark: str | None = Field(default=None, max_length=255)


class InspectionCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64, description="留空自动生成 QC 前缀编号")
    inspection_type: str = Field(description="iqc 来料 / ipqc 制程 / oqc 出货 / fai 首件")
    qty: int = Field(default=0, ge=0, description="送检数量")
    sample_qty: int = Field(default=0, ge=0, description="抽样数量")
    template_id: int | None = Field(default=None, ge=1)
    items: list[ItemIn] | None = None
    source_type: str = Field(default="manual", description="purchase_order / work_order / shipment / task / report / manual")
    source_id: int | None = Field(default=None, ge=1)
    report_id: int | None = Field(default=None, ge=1, description="整批报工终审的检验依据挂靠点")
    process_id: int | None = Field(default=None, ge=1, description="FAI/IPQC 所在工序")
    material_id: int | None = Field(default=None, ge=1)
    sku_id: int | None = Field(default=None, ge=1)
    item_name: str | None = Field(default=None, max_length=255)
    batch_no: str | None = Field(default=None, max_length=64)
    supplier_id: int | None = Field(default=None, ge=1)
    customer_id: int | None = Field(default=None, ge=1)
    remark: str | None = None


class InspectionUpdateIn(BaseModel):
    qty: int | None = Field(default=None, ge=0)
    sample_qty: int | None = Field(default=None, ge=0)
    batch_no: str | None = Field(default=None, max_length=64)
    item_name: str | None = Field(default=None, max_length=255)
    material_id: int | None = Field(default=None, ge=1)
    sku_id: int | None = Field(default=None, ge=1)
    supplier_id: int | None = Field(default=None, ge=1)
    customer_id: int | None = Field(default=None, ge=1)
    template_id: int | None = Field(default=None, ge=1)
    items: list[ItemIn] | None = None
    remark: str | None = None


class JudgeIn(BaseModel):
    accept_qty: int | None = Field(default=None, ge=0)
    reject_qty: int | None = Field(default=None, ge=0)
    handling: str | None = Field(default=None, description="不合格时必填：return/accept/rework/scrap")
    conclusion: str | None = None


# ──────────────────────────── 辅助 ────────────────────────────

def _load(db: Session, inspection_id: int) -> InspectionOrder:
    o = get_inspection(db, inspection_id)
    if not o:
        raise HTTPException(status_code=404, detail="检验单不存在")
    return o


def _bad(e: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


def _rows(items: list[ItemIn] | None) -> list[dict] | None:
    if items is None:
        return None
    return [it.model_dump(exclude_unset=True) for it in items]


# ──────────────────────────── 静态路径（必须在 /{id} 之前）────────────────────────────

@router.get("/stats")
def stats_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(inspection_stats(db))


@router.get("/meta/options")
def meta_options_api(user: User = Depends(get_current_user)):
    return ok({
        "inspection_types": [{"value": t, "label": _TYPE_LABEL[t]} for t in INSPECTION_TYPES],
        "statuses": [{"value": s, "label": _STATUS_LABEL[s]} for s in INSPECTION_STATUSES],
        "handlings": [{"value": h, "label": _HANDLING_LABEL[h]} for h in INSPECTION_HANDLINGS],
        "item_results": [{"value": r, "label": _RESULT_LABEL[r]} for r in ITEM_RESULTS],
    })


@router.get("/template-options")
def template_options_api(
    inspection_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ok(template_options(db, inspection_type=inspection_type, keyword=keyword, limit=limit))


@router.get("/source-options")
def source_options_api(
    inspection_type: str = Query(description="iqc / ipqc / oqc / fai"),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if inspection_type not in INSPECTION_TYPES:
        raise HTTPException(status_code=400, detail="检验类型不支持")
    return ok(source_options(db, inspection_type=inspection_type, keyword=keyword, limit=limit))


# ── 检验台账（读已有的 inspection_records）──

@router.get("/ledger/stats")
def ledger_stats_api(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ok(ledger_stats(db, date_from=date_from, date_to=date_to))


@router.get("/ledger/export")
def ledger_export_api(
    result: str | None = Query(default=None),
    process_id: int | None = Query(default=None, ge=1),
    sku_id: int | None = Query(default=None, ge=1),
    defect_code_id: int | None = Query(default=None, ge=1),
    auditor_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = list_ledger(
        db, result=result, process_id=process_id, sku_id=sku_id,
        defect_code_id=defect_code_id, auditor_id=auditor_id,
        date_from=date_from, date_to=date_to, keyword=keyword, offset=0, limit=20000,
    )
    headers = [
        "记录时间", "检查项", "类型", "标准值", "下限", "上限", "实测值",
        "结果", "缺陷代码", "缺陷名称", "严重度", "说明",
        "任务号", "工序", "型号编码", "型号名称", "件次", "审核环节",
    ]
    data = []
    for r in rows:
        data.append([
            (r["recorded_at"] or "")[:19].replace("T", " "),
            r["item_name"] or "",
            r["item_type"] or "",
            r["standard_value"] or "",
            r["lower_limit"] or "",
            r["upper_limit"] or "",
            r["measured_value"] or "",
            _RESULT_LABEL.get(r["result"] or "", r["result"] or ""),
            r["defect_code"] or "",
            r["defect_name"] or "",
            r["defect_severity"] or "",
            r["remark"] or "",
            r["task_code"] or "",
            r["process_name"] or "",
            r["sku_code"] or "",
            r["sku_name"] or "",
            "" if r["unit_seq"] is None else r["unit_seq"],
            r["audit_level"] or "",
        ])
    return make_excel_response(headers, data, "inspection_ledger.xlsx", "检验台账")


@router.get("/ledger")
def ledger_api(
    result: str | None = Query(default=None),
    process_id: int | None = Query(default=None, ge=1),
    sku_id: int | None = Query(default=None, ge=1),
    defect_code_id: int | None = Query(default=None, ge=1),
    auditor_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = dict(
        result=result, process_id=process_id, sku_id=sku_id,
        defect_code_id=defect_code_id, auditor_id=auditor_id,
        date_from=date_from, date_to=date_to, keyword=keyword,
    )
    return ok({
        "items": list_ledger(db, offset=offset, limit=limit, **filters),
        "total": count_ledger(db, **filters),
    })


@router.get("/ledger/{record_id}")
def ledger_detail_api(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = ledger_detail(db, record_id)
    if not row:
        raise HTTPException(status_code=404, detail="检验记录不存在")
    return ok(row)


# ── 列表导出 ──

@router.get("/export")
def export_api(
    inspection_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_inspections(
        db, inspection_type=inspection_type, status=status, keyword=keyword,
        date_from=date_from, date_to=date_to, offset=0, limit=20000,
    )
    headers = [
        "检验单号", "检验类型", "状态", "来源单号", "检验对象", "批次",
        "送检数", "抽样数", "接收数", "拒收数",
        "检查项", "未通过项", "处置方式", "结论", "检验员", "检验时间", "是否关闭", "备注",
    ]
    rows = []
    for o in items:
        d = inspection_out(o, with_items=False)
        rows.append([
            o.code,
            _TYPE_LABEL.get(o.inspection_type, o.inspection_type),
            _STATUS_LABEL.get(o.status, o.status),
            o.source_code or "",
            o.item_name or "",
            o.batch_no or "",
            int(o.qty or 0),
            int(o.sample_qty or 0),
            int(o.accept_qty or 0),
            int(o.reject_qty or 0),
            d["item_total"],
            d["item_failed"],
            _HANDLING_LABEL.get(o.handling or "", ""),
            o.conclusion or "",
            o.inspector.full_name if o.inspector and o.inspector.full_name else (
                o.inspector.username if o.inspector else ""),
            o.inspected_at.strftime("%Y-%m-%d %H:%M") if o.inspected_at else "",
            "是" if o.is_closed else "否",
            o.remark or "",
        ])
    return make_excel_response(headers, rows, "inspections.xlsx", "检验单")


# ──────────────────────────── 检验单 ────────────────────────────

# ── 0019：整批报工终审检验依据 / OQC·FAI 来源联动 ──

class FromReportIn(BaseModel):
    report_id: int | None = Field(default=None, ge=1)
    template_id: int | None = Field(default=None, ge=1)
    items: list[ItemIn] | None = None
    sample_qty: int = Field(default=0, ge=0)
    remark: str | None = None


@router.get("/report-options")
def report_options_api(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """待终审报工单列表：建 IPQC 依据单时选来源。"""
    return ok(report_options(db, keyword=keyword, limit=limit))


@router.get("/source-summary")
def source_summary_api(
    source_type: str = Query(...),
    source_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """来源单据的检验汇总（只读，不推进来源单据状态）。"""
    if source_type not in SOURCE_TYPES:
        raise _bad(ValueError("来源单据类型不支持"))
    return ok(source_summary(db, source_type=source_type, source_id=source_id))


@router.get("/by-report/{report_id}")
def by_report_api(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """某条报工挂着的检验单，供终审弹窗列出可选依据。"""
    items = list_inspections(db, report_id=report_id, limit=50)
    return ok({"items": [inspection_out(o, with_items=False) for o in items]})


@router.post("/from-report", dependencies=_WRITE)
def from_report_api(
    payload: FromReportIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按一条待终审报工一键建 IPQC 检验单，省掉逐字段手填。"""
    p = payload or FromReportIn()
    if not p.report_id:
        raise _bad(ValueError("请选择报工单"))
    rep = db.get(Report, int(p.report_id))
    if not rep:
        raise _bad(ValueError("报工记录不存在"))
    if rep.status != "leader_approved":
        raise _bad(ValueError("只有待终审（已初审通过）的报工可以建检验依据单"))

    def _exists(code: str) -> bool:
        from sqlalchemy import select as _select

        return db.scalar(_select(InspectionOrder.id).where(InspectionOrder.code == code)) is not None

    try:
        code = resolve_code(db, biz_type=BizType.INSPECTION, code=None, exists=_exists,
                            duplicate_msg="检验单号已存在")
        o = create_inspection(
            db,
            code=code,
            inspection_type="ipqc",
            source_type="report",
            source_id=int(p.report_id),
            template_id=p.template_id,
            items=_rows(p.items),
            sample_qty=p.sample_qty,
            remark=p.remark,
            created_by=user.id,
        )
        db.commit()
    except (InspectionStateError, ValueError) as e:
        raise _bad(e)
    return ok(inspection_out(get_inspection(db, o.id)))


@router.get("")
def list_api(
    inspection_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    supplier_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = dict(
        inspection_type=inspection_type, status=status, source_type=source_type,
        supplier_id=supplier_id, keyword=keyword, date_from=date_from, date_to=date_to,
    )
    items = list_inspections(db, offset=offset, limit=limit, **filters)
    return ok({
        "items": [inspection_out(o) for o in items],
        "total": count_inspections(db, **filters),
    })


@router.post("", dependencies=_WRITE)
def create_api(
    payload: InspectionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _exists(c: str) -> bool:
        from sqlalchemy import select as _select

        return db.scalar(_select(InspectionOrder.id).where(InspectionOrder.code == c)) is not None

    try:
        code = resolve_code(
            db,
            biz_type=BizType.INSPECTION,
            code=payload.code,
            exists=_exists,
            duplicate_msg="检验单号已存在",
        )
        o = create_inspection(
            db,
            code=code,
            inspection_type=payload.inspection_type,
            qty=payload.qty,
            sample_qty=payload.sample_qty,
            template_id=payload.template_id,
            items=_rows(payload.items),
            source_type=payload.source_type,
            source_id=payload.source_id,
            report_id=payload.report_id,
            process_id=payload.process_id,
            material_id=payload.material_id,
            sku_id=payload.sku_id,
            item_name=payload.item_name,
            batch_no=payload.batch_no,
            supplier_id=payload.supplier_id,
            customer_id=payload.customer_id,
            remark=payload.remark,
            created_by=user.id,
        )
        db.commit()
    except (InspectionStateError, ValueError) as e:
        raise _bad(e)
    return ok(inspection_out(get_inspection(db, o.id)))


@router.get("/{inspection_id}")
def get_api(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(inspection_out(_load(db, inspection_id)))


@router.put("/{inspection_id}", dependencies=_WRITE)
def update_api(
    inspection_id: int,
    payload: InspectionUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _load(db, inspection_id)
    try:
        update_inspection(
            db, o,
            qty=payload.qty,
            sample_qty=payload.sample_qty,
            batch_no=payload.batch_no,
            item_name=payload.item_name,
            material_id=payload.material_id,
            sku_id=payload.sku_id,
            supplier_id=payload.supplier_id,
            customer_id=payload.customer_id,
            template_id=payload.template_id,
            items=_rows(payload.items),
            remark=payload.remark,
        )
        db.commit()
    except (InspectionStateError, ValueError) as e:
        raise _bad(e)
    return ok(inspection_out(get_inspection(db, o.id)))


@router.delete("/{inspection_id}", dependencies=_WRITE)
def delete_api(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """只有草稿能删。判定过的单子是质量证据，删不得——要作废走 cancel。"""
    o = _load(db, inspection_id)
    if o.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿可以删除，其余请用作废")
    db.delete(o)
    db.commit()
    return ok({"id": inspection_id, "deleted": True})


# ── 状态流转 ──

@router.post("/{inspection_id}/submit", dependencies=_WRITE)
def submit_api(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _load(db, inspection_id)
    try:
        submit_inspection(db, o)
        db.commit()
    except InspectionStateError as e:
        raise _bad(e)
    return ok(inspection_out(get_inspection(db, o.id)))


@router.post("/{inspection_id}/judge", dependencies=_AUDIT)
def judge_api(
    inspection_id: int,
    payload: JudgeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _load(db, inspection_id)
    try:
        judge_inspection(
            db, o,
            inspector_id=user.id,
            accept_qty=payload.accept_qty,
            reject_qty=payload.reject_qty,
            handling=payload.handling,
            conclusion=payload.conclusion,
        )
        db.commit()
    except InspectionStateError as e:
        raise _bad(e)
    return ok(inspection_out(get_inspection(db, o.id)))


@router.post("/{inspection_id}/close", dependencies=_WRITE)
def close_api(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _load(db, inspection_id)
    try:
        close_inspection(db, o)
        db.commit()
    except InspectionStateError as e:
        raise _bad(e)
    return ok(inspection_out(get_inspection(db, o.id)))


@router.post("/{inspection_id}/cancel", dependencies=_WRITE)
def cancel_api(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _load(db, inspection_id)
    try:
        cancel_inspection(db, o)
        db.commit()
    except InspectionStateError as e:
        raise _bad(e)
    return ok(inspection_out(get_inspection(db, o.id)))


# ── 单张导出 ──

@router.get("/{inspection_id}/export")
def export_one_api(
    inspection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    o = _load(db, inspection_id)
    headers = [
        "序号", "检查项", "类型", "标准值", "下限", "上限", "单位",
        "实测值", "结果", "缺陷代码", "缺陷名称", "严重度", "是否必检", "说明",
    ]
    rows = []
    for it in (o.items or []):
        rows.append([
            it.seq,
            it.item_name,
            it.item_type,
            it.standard_value or "",
            it.lower_limit or "",
            it.upper_limit or "",
            it.unit or "",
            it.measured_value or "",
            _RESULT_LABEL.get(it.result or "", ""),
            it.defect_code.code if it.defect_code else "",
            it.defect_code.name if it.defect_code else "",
            it.defect_code.severity if it.defect_code else "",
            "是" if it.is_required else "否",
            it.remark or "",
        ])
    return make_excel_response(headers, rows, f"inspection_{o.code}.xlsx", "检验单明细")
