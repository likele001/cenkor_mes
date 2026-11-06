# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""不良品处置 API

权限分三档，任一即可进菜单，但动作分开挂：

- `disposition.view`    看列表、看单据、导出
- `disposition.manage`  制单、改单、提交、作废、闭环登记
- `disposition.approve` 批准 / 驳回（报废与让步接收必须有人担责）

路由顺序有讲究：`/stats`、`/report-options` 这类静态路径必须注册在 `/{disposition_id}`
之前，否则会被当成 id 解析成 422。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_any_permissions
from app.core.response import ok
from app.crud.disposition import (
    DispositionStateError,
    approve_disposition,
    cancel_disposition,
    close_disposition,
    count_dispositions,
    create_disposition,
    disposition_out,
    disposition_stats,
    get_disposition,
    list_dispositions,
    reject_disposition,
    report_options,
    submit_disposition,
    update_disposition,
)
from app.models.disposition import DISPOSITION_METHODS, DISPOSITION_STATUSES
from app.models.disposition import Disposition
from app.models.user import User
from app.services.code_generator import BizType, resolve_code
from app.tasks._sync_excel import make_excel_response

router = APIRouter(
    prefix="/dispositions",
    dependencies=[
        Depends(require_any_permissions(["disposition.view", "disposition.manage", "disposition.approve"]))
    ],
)

_WRITE = [Depends(require_any_permissions(["disposition.manage"]))]
_APPROVE = [Depends(require_any_permissions(["disposition.approve"]))]


class ItemIn(BaseModel):
    method: str = Field(description="rework 返修 / scrap 报废 / concede 让步接收 / return_process 退工序")
    qty: int = Field(ge=1)
    defect_code_id: int | None = Field(default=None, ge=1)
    target_process_id: int | None = Field(default=None, ge=1, description="退工序时退回的目标工序")
    cost_amount: float | None = Field(default=None, ge=0, description="损失金额，报废行才计")
    remark: str | None = Field(default=None, max_length=255)


class DispositionCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=64, description="留空自动生成 CZ 前缀编号")
    report_id: int = Field(ge=1, description="挂靠的报工单，必须是有不良量的报工")
    items: list[ItemIn] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=255, description="处置原因/判定依据")
    remark: str | None = Field(default=None)


class DispositionUpdateIn(BaseModel):
    items: list[ItemIn] | None = Field(default=None, description="传了就整组替换明细")
    reason: str | None = Field(default=None, max_length=255)
    remark: str | None = Field(default=None)


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


class CloseItemIn(BaseModel):
    item_id: int = Field(ge=1)
    done_qty: int = Field(ge=0)
    remark: str | None = Field(default=None, max_length=255)


class CloseIn(BaseModel):
    items: list[CloseItemIn] | None = Field(default=None, description="未列出的明细默认按全量执行")
    note: str | None = Field(default=None, max_length=255)


def _load(db: Session, disposition_id: int) -> Disposition:
    d = get_disposition(db, disposition_id)
    if not d:
        raise HTTPException(status_code=404, detail="处置单不存在")
    return d


def _bad(e: Exception) -> HTTPException:
    """状态不对按 409，参数/额度不对按 400——前端据此决定是提示还是刷新。"""
    if isinstance(e, DispositionStateError):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


def _rows(items: list[ItemIn]) -> list[dict]:
    return [it.model_dump() for it in items]


# ── 静态路径（必须在 /{disposition_id} 之前） ──

@router.get("/stats")
def stats_api(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(disposition_stats(db))


@router.get("/meta/options")
def meta_options_api(user: User = Depends(get_current_user)):
    return ok({"methods": list(DISPOSITION_METHODS), "statuses": list(DISPOSITION_STATUSES)})


@router.get("/report-options")
def report_options_api(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """可挂单的报工：不良量 > 0 且还有剩余可处置量。"""
    return ok({"items": report_options(db, keyword=keyword, limit=limit)})


# ── 列表 / 详情 ──

@router.get("")
def list_api(
    status: str | None = Query(default=None),
    method: str | None = Query(default=None),
    report_id: int | None = Query(default=None, ge=1),
    task_id: int | None = Query(default=None, ge=1),
    sku_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_dispositions(
        db, status=status, method=method, report_id=report_id,
        task_id=task_id, sku_id=sku_id, keyword=keyword, offset=offset, limit=limit,
    )
    return ok({
        "items": [disposition_out(d) for d in items],
        "total": count_dispositions(
            db, status=status, method=method, report_id=report_id,
            task_id=task_id, sku_id=sku_id, keyword=keyword,
        ),
    })


@router.get("/{disposition_id}")
def get_api(disposition_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(disposition_out(_load(db, disposition_id)))


# ── 制单 / 改单 ──

@router.post("", dependencies=_WRITE)
def create_api(
    payload: DispositionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = resolve_code(
        db,
        biz_type=BizType.DISPOSITION,
        code=payload.code,
        exists=lambda c: db.scalar(select(Disposition.id).where(Disposition.code == c)) is not None,
        duplicate_msg="处置单号已存在",
    )
    try:
        d = create_disposition(
            db,
            code=code,
            report_id=payload.report_id,
            items=_rows(payload.items),
            reason=payload.reason,
            remark=payload.remark,
            created_by=user.id,
        )
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(disposition_out(get_disposition(db, d.id)))


@router.put("/{disposition_id}", dependencies=_WRITE)
def update_api(
    disposition_id: int,
    payload: DispositionUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = _load(db, disposition_id)
    try:
        update_disposition(
            db, d,
            items=_rows(payload.items) if payload.items is not None else None,
            reason=payload.reason,
            remark=payload.remark,
        )
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(disposition_out(get_disposition(db, d.id)))


@router.delete("/{disposition_id}", dependencies=_WRITE)
def delete_api(
    disposition_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """只有草稿能删。提交过的单据要留痕，走作废而不是删除。"""
    d = _load(db, disposition_id)
    if d.status != "draft":
        raise HTTPException(status_code=409, detail="只有草稿状态的处置单可以删除，已提交的请用作废")
    db.delete(d)
    db.commit()
    return ok({"ok": True})


# ── 状态流转 ──

@router.post("/{disposition_id}/submit", dependencies=_WRITE)
def submit_api(
    disposition_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = _load(db, disposition_id)
    try:
        submit_disposition(db, d, submitted_by=user.id)
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(disposition_out(get_disposition(db, d.id)))


@router.post("/{disposition_id}/approve", dependencies=_APPROVE)
def approve_api(
    disposition_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = _load(db, disposition_id)
    try:
        approve_disposition(db, d, approved_by=user.id)
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(disposition_out(get_disposition(db, d.id)))


@router.post("/{disposition_id}/reject", dependencies=_APPROVE)
def reject_api(
    disposition_id: int,
    payload: RejectIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = _load(db, disposition_id)
    try:
        reject_disposition(db, d, payload.reason)
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(disposition_out(get_disposition(db, d.id)))


@router.post("/{disposition_id}/close", dependencies=_WRITE)
def close_api(
    disposition_id: int,
    payload: CloseIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = _load(db, disposition_id)
    payload = payload or CloseIn()
    try:
        close_disposition(
            db, d,
            done_items=[it.model_dump() for it in (payload.items or [])],
            note=payload.note,
            closed_by=user.id,
        )
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(disposition_out(get_disposition(db, d.id)))


@router.post("/{disposition_id}/cancel", dependencies=_WRITE)
def cancel_api(
    disposition_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = _load(db, disposition_id)
    try:
        cancel_disposition(db, d)
    except ValueError as e:
        raise _bad(e)
    db.commit()
    return ok(disposition_out(get_disposition(db, d.id)))


# ── 导出 ──

_METHOD_LABEL = {
    "rework": "返修",
    "scrap": "报废",
    "concede": "让步接收",
    "return_process": "退工序",
}
_STATUS_LABEL = {
    "draft": "草稿",
    "pending": "待审批",
    "approved": "已批准",
    "rejected": "已驳回",
    "closed": "已闭环",
    "cancelled": "已作废",
}


@router.get("/{disposition_id}/export")
def export_api(
    disposition_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = _load(db, disposition_id)
    headers = [
        "处置单号", "状态", "任务号", "工序", "型号编码", "型号名称",
        "报工不良量", "处置方式", "处置数量", "缺陷代码", "退工序目标", "损失金额", "实际执行", "备注",
    ]
    rows = []
    for it in (d.items or []):
        rows.append([
            d.code,
            _STATUS_LABEL.get(d.status, d.status),
            d.task.task_code if d.task else "",
            d.process.name if d.process else "",
            d.sku.code if d.sku else "",
            d.sku.name if d.sku else "",
            int(d.bad_qty or 0),
            _METHOD_LABEL.get(it.method, it.method),
            int(it.qty or 0),
            f"{it.defect_code.code} {it.defect_code.name}" if it.defect_code else "",
            it.target_process.name if it.target_process else "",
            float(it.cost_amount or 0),
            "" if it.done_qty is None else int(it.done_qty),
            it.remark or "",
        ])
    return make_excel_response(headers, rows, f"disposition_{d.code}.xlsx", "不良品处置单")
