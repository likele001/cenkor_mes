from io import BytesIO

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_permissions
from app.core.response import ok
from app.crud.attachment import create_attachment
from app.crud.print_template import ensure_print_template, get_print_template_by_code, get_print_template_by_id, render_print_template
from app.crud.print_template import html_to_pdf_bytes
from app.crud.task import get_task_by_id, list_tasks, set_task_equipment
from app.crud.task_assignment import (
    list_assignments_for_task,
    replace_task_assignments,
    sum_assigned_qty,
    sum_user_reported_qty)
from app.models.equipment import Equipment
from app.services.task_qr import task_qr_payload
from app.models.employee_skill import Skill
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskAssignIn, TaskAssignmentsIn, TaskLabelBatchIn
from app.storage import get_active_storage
from app.services.dispatch_candidates import list_dispatch_candidate_users
from app.services.entity_refs import equipment_ref_dict, process_ref_dict, product_ref_dict, sku_ref_dict

router = APIRouter(dependencies=[Depends(require_permissions(["task.manage"]))])

def _assignment_out(a) -> dict:
    u = getattr(a, "user", None)
    return {
        "id": a.id,
        "user_id": a.user_id,
        "assigned_qty": a.assigned_qty,
        "reported_qty": getattr(a, "_reported_qty", None),
        "remaining_qty": getattr(a, "_remaining_qty", None),
        "assigned_at": a.assigned_at,
        "assigned_by": a.assigned_by,
        "user": {"id": u.id, "username": u.username, "full_name": u.full_name} if u else None,
    }

def _out(x, db: Session | None = None) -> dict:
    assignments = []
    assigned_total = 0
    if db is not None:
        rows = list_assignments_for_task(db, task_id=x.id)
        assigned_total = sum(int(r.assigned_qty) for r in rows)
        for r in rows:
            reported = sum_user_reported_qty(db, x.id, r.user_id)
            r._reported_qty = reported  # noqa: SLF001
            r._remaining_qty = max(0, int(r.assigned_qty) - reported)
            assignments.append(_assignment_out(r))
    wo = getattr(x, "work_order", None)
    order = wo.order if wo and getattr(wo, "order", None) else None
    customer = order.customer if order and getattr(order, "customer", None) else None
    sku = wo.sku if wo else None
    product = (wo.product if wo and getattr(wo, "product", None) else None) or (
        sku.product if sku and getattr(sku, "product", None) else None
    )
    sku_out = sku_ref_dict(sku, product)
    return {
        "id": x.id,
        "work_order_id": x.work_order_id,
        "process_id": x.process_id,
        "seq": x.seq,
        "task_code": x.task_code,
        "planned_qty": x.planned_qty,
        "status": x.status,
        "assigned_user_id": x.assigned_user_id,
        "assigned_at": x.assigned_at,
        "assigned_by": x.assigned_by,
        "equipment_id": getattr(x, "equipment_id", None),
        "created_at": x.created_at,
        "updated_at": x.updated_at,
        "process": process_ref_dict(getattr(x, "process", None)),
        "equipment": (
            {**(equipment_ref_dict(x.equipment) or {}), "workshop": x.equipment.workshop, "status": x.equipment.status}
            if getattr(x, "equipment", None)
            else None
        ),
        "assignments": assignments,
        "assigned_total_qty": assigned_total,
        "unassigned_qty": max(0, int(x.planned_qty) - assigned_total),
        "order": (
            {
                "id": order.id,
                "code": order.code,
                "status": order.status,
                "customer_id": order.customer_id,
                "customer_name": customer.name if customer else None,
                "customer_code": customer.code if customer else None,
            }
            if order
            else None
        ),
        "sku": sku_out,
        "product": product_ref_dict(product),
        "work_order": (
            {
                "id": wo.id,
                "order_id": wo.order_id,
                "sku_id": wo.sku_id,
                "qty": wo.qty,
                "sku_display_label": sku_out.get("display_label") if sku_out else None,
            }
            if wo
            else None
        ),
    }

def _extract_head_body(html: str) -> tuple[str, str] | None:
    m_head = re.search(r"<head[^>]*>([\s\S]*?)</head>", html, flags=re.I)
    m_body = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, flags=re.I)
    if not m_head or not m_body:
        return None
    return (m_head.group(1), m_body.group(1))

@router.get("")
def list_api(
    work_order_id: int | None = Query(default=None, ge=1),
    assigned_user_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    items = list_tasks(
        db,
        work_order_id=work_order_id,
        assigned_user_id=assigned_user_id,
        keyword=keyword,
        status=status,
        with_refs=True,
        offset=offset,
        limit=limit)
    return ok({"items": [_out(x, db=db) for x in items]})

@router.get("/dispatch-skills", dependencies=[Depends(require_permissions(["dispatch.manage"]))])
def list_dispatch_skills_api(
    keyword: str | None = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    stmt = select(Skill).where(Skill.is_active.is_(True))
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where((Skill.code.like(kw)) | (Skill.name.like(kw)))
    stmt = stmt.order_by(Skill.id.desc()).limit(200)
    items = db.scalars(stmt).all()
    return ok({"items": [{"id": x.id, "code": x.code, "name": x.name} for x in items]})

@router.get("/dispatch-users", dependencies=[Depends(require_permissions(["dispatch.manage"]))])
def list_dispatch_users_api(
    keyword: str | None = Query(default=None, max_length=50),
    skill_ids: str | None = Query(default=None, max_length=200, description="逗号分隔技能ID，例如 1,2,3"),
    match: str = Query(default="all", max_length=8, description="all/any"),
    include_leader: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    ids: list[int] = []
    if skill_ids:
        for part in skill_ids.split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        ids = [x for x in ids if x > 0]
        ids = list(dict.fromkeys(ids))

    if match not in {"all", "any"}:
        raise HTTPException(status_code=400, detail="match 参数必须为 all 或 any")

    items = list_dispatch_candidate_users(db, include_leader=include_leader,
        skill_ids=ids or None,
        skill_match=match,
        keyword=keyword,
        offset=offset,
        limit=limit)
    return ok({"items": [{"id": u.id, "username": u.username, "full_name": u.full_name} for u in items]})

@router.get("/{task_id}/print-label", dependencies=[Depends(require_permissions(["dispatch.manage"]))])
def render_task_label_api(
    task_id: int,
    template_id: int | None = Query(default=None, ge=1),
    template_code: str = Query(default="task_label", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    task = get_task_by_id(db, task_id=task_id, with_refs=True)
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在")

    tpl = None
    if template_id is not None:
        tpl = get_print_template_by_id(db, template_id=template_id)
    else:
        tpl = get_print_template_by_code(db, code=template_code)
        if not tpl or not tpl.is_active:
            tpl = ensure_print_template(db, code=template_code)
            if tpl:
                db.commit()
    if not tpl or not tpl.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"未找到可用打印模板 code={template_code}（可在 系统管理-打印模板 中自定义）")

    wo = task.work_order
    sku = wo.sku if wo else None
    proc = task.process

    qr = task_qr_payload(task.task_code)
    html = render_print_template(
        tpl.content,
        {
            "task": {
                "id": task.id,
                "task_code": task.task_code,
                "seq": task.seq,
                "planned_qty": task.planned_qty,
                "status": task.status,
            },
            "work_order": {
                "id": wo.id,
                "order_id": wo.order_id,
                "qty": wo.qty,
            }
            if wo
            else None,
            "sku": {
                "id": sku.id,
                "code": sku.code,
                "name": sku.name,
            }
            if sku
            else None,
            "process": {
                "id": proc.id,
                "code": proc.code,
                "name": proc.name,
            }
            if proc
            else None,
            "qr": qr,
        })
    return ok({"html": html, "task_id": task.id, "task_code": task.task_code, "template_id": tpl.id, "report_url": qr.get("report_url")})

@router.post("/print-label-batch", dependencies=[Depends(require_permissions(["dispatch.manage"]))])
def render_task_label_batch_api(
    payload: TaskLabelBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    tpl = None
    if payload.template_id is not None:
        tpl = get_print_template_by_id(db, template_id=payload.template_id)
    else:
        tpl = get_print_template_by_code(db, code=payload.template_code)
        if not tpl or not tpl.is_active:
            tpl = ensure_print_template(db, code=payload.template_code)
            if tpl:
                db.commit()
    if not tpl or not tpl.is_active:
        raise HTTPException(status_code=400, detail="打印模板不存在或未启用")

    ids = [int(x) for x in payload.task_ids if int(x) > 0]
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise HTTPException(status_code=400, detail="task_ids 不能为空")
    if len(ids) > 200:
        raise HTTPException(status_code=400, detail="一次最多打印 200 个任务")

    tasks = db.scalars(
        select(Task)
        .where(Task.id.in_(ids))
        .order_by(Task.id.desc())
    ).all()
    if not tasks:
        raise HTTPException(status_code=400, detail="任务不存在")

    from app.models.work_order import WorkOrder
    from app.models.sku import Sku
    from app.models.process import Process

    wo_ids = list({t.work_order_id for t in tasks})
    proc_ids = list({t.process_id for t in tasks})
    wo_map = {x.id: x for x in db.scalars(select(WorkOrder).where(WorkOrder.id.in_(wo_ids))).all()}
    sku_ids = list({x.sku_id for x in wo_map.values() if x and x.sku_id})
    sku_map = {x.id: x for x in db.scalars(select(Sku).where(Sku.id.in_(sku_ids))).all()} if sku_ids else {}
    proc_map = {x.id: x for x in db.scalars(select(Process).where(Process.id.in_(proc_ids))).all()}

    pages: list[str] = []
    head_html: str | None = None
    for t in tasks:
        wo = wo_map.get(t.work_order_id)
        sku = sku_map.get(wo.sku_id) if wo else None
        proc = proc_map.get(t.process_id)
        qr = task_qr_payload(t.task_code)
        rendered = render_print_template(
            tpl.content,
            {
                "task": {"id": t.id, "task_code": t.task_code, "seq": t.seq, "planned_qty": t.planned_qty, "status": t.status},
                "work_order": {"id": wo.id, "order_id": wo.order_id, "qty": wo.qty} if wo else None,
                "sku": {"id": sku.id, "code": sku.code, "name": sku.name} if sku else None,
                "process": {"id": proc.id, "code": proc.code, "name": proc.name} if proc else None,
                "qr": qr,
            })

        hb = _extract_head_body(rendered)
        if hb:
            if head_html is None:
                head_html = hb[0]
            pages.append(hb[1])
        else:
            pages.append(rendered)

    joiner = '<div class="print-pagebreak"></div>'
    if head_html is not None:
        html = (
            "<!doctype html><html><head><meta charset=\"utf-8\" />"
            f"{head_html}<style>.print-pagebreak{{page-break-after:always}}</style></head>"
            f"<body>{joiner.join(pages)}</body></html>"
        )
    else:
        html = joiner.join(pages)
    return ok({"html": html, "count": len(pages), "template_id": tpl.id})

@router.get("/{task_id}/print-label-pdf", dependencies=[Depends(require_permissions(["dispatch.manage"]))])
def render_task_label_pdf_api(
    task_id: int,
    template_id: int | None = Query(default=None, ge=1),
    template_code: str = Query(default="task_label", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    inner = render_task_label_api(task_id=task_id, template_id=template_id, template_code=template_code, db=db, user=user)
    html = (inner.get("data") or {}).get("html") if isinstance(inner, dict) else ""
    task_code = (inner.get("data") or {}).get("task_code") if isinstance(inner, dict) else ""
    if not html:
        raise HTTPException(status_code=500, detail="渲染失败")
    try:
        pdf_bytes = html_to_pdf_bytes(html)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = f"task_label_{task_code or task_id}.pdf"
    storage = get_active_storage(db)
    bio = BytesIO(pdf_bytes)
    stored = storage.save(
        filename=filename,
        content_type="application/pdf",
        stream=bio,
        max_size=settings.FILE_MAX_UPLOAD_SIZE)
    att = create_attachment(
        db,
        uploader_id=user.id,
        storage_driver=stored.driver,
        storage_key=stored.key,
        original_filename=filename,
        content_type="application/pdf",
        size=stored.size,
        sha256=stored.sha256)
    db.commit()
    db.refresh(att)
    return ok({"attachment_id": att.id, "filename": att.original_filename, "url": f"/api/files/{att.id}?download=true"})

@router.get("/{task_id}/assignments", dependencies=[Depends(require_permissions(["dispatch.manage"]))])
def list_assignments_api(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    task = get_task_by_id(db, task_id=task_id, with_refs=False)
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在")
    rows = list_assignments_for_task(db, task_id=task_id)
    out = []
    for r in rows:
        reported = sum_user_reported_qty(db, task_id, r.user_id)
        r._reported_qty = reported
        r._remaining_qty = max(0, int(r.assigned_qty) - reported)
        out.append(_assignment_out(r))
    return ok({
        "task_id": task_id,
        "planned_qty": task.planned_qty,
        "assigned_total_qty": sum_assigned_qty(db, task_id),
        "items": out,
    })

@router.put("/{task_id}/assignments", dependencies=[Depends(require_permissions(["dispatch.manage"]))])
def set_assignments_api(
    task_id: int,
    payload: TaskAssignmentsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    task = get_task_by_id(db, task_id=task_id, with_refs=False)
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在")
    if payload.equipment_id is not None:
        eq = db.get(Equipment, payload.equipment_id)
        if not eq or False:
            raise HTTPException(status_code=400, detail="设备不存在")
    items = [{"user_id": x.user_id, "assigned_qty": x.assigned_qty} for x in payload.items]
    if items:
        from app.crud.task_assignment import ensure_users_exist

        try:
            ensure_users_exist(db, [x["user_id"] for x in items])
            replace_task_assignments(
                db,
                task=task,
                items=items,
                dispatcher_user_id=user.id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        replace_task_assignments(db, task=task, items=[], dispatcher_user_id=user.id)
    set_task_equipment(db, task=task, equipment_id=payload.equipment_id)
    db.commit()
    item = get_task_by_id(db, task_id=task.id, with_refs=True)
    if not item:
        raise HTTPException(status_code=500, detail="派工失败")
    return ok(_out(item, db=db))

@router.post("/{task_id}/assign", dependencies=[Depends(require_permissions(["dispatch.manage"]))])
def assign_api(
    task_id: int,
    payload: TaskAssignIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    """兼容旧接口：单人派工时分配全部计划数量。"""
    task = get_task_by_id(db, task_id=task_id, with_refs=False)
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在")
    items: list[dict] = []
    if payload.assigned_user_id is not None:
        items = [{"user_id": payload.assigned_user_id, "assigned_qty": int(task.planned_qty)}]
    body = TaskAssignmentsIn(items=items, equipment_id=payload.equipment_id)
    return set_assignments_api(task_id=task_id, payload=body, db=db, user=user)

@router.get("/{task_id}")
def get_api(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    item = get_task_by_id(db, task_id=task_id, with_refs=True)
    if not item:
        raise HTTPException(status_code=400, detail="任务不存在")
    return ok(_out(item, db=db))
