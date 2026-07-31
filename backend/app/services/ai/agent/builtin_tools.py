# -*- coding: utf-8 -*-
"""Built-in AI agent tools - registered at module import time."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.services.ai.agent.tools_registry import registry

logger = logging.getLogger(__name__)


def _get_db_and_tenant(context: dict) -> tuple:
    db = context.get("db")
    tenant_id = context.get("tenant_id")
    return db, tenant_id


# === Tool: query_order_status ===
def tool_query_orders(args: dict, context: dict) -> str:
    db, tenant_id = _get_db_and_tenant(context)
    if not db or not tenant_id:
        return "System context not available"

    status_filter = args.get("status")
    code_contains = args.get("code_contains", "")
    limit = min(int(args.get("limit", 5)), 20)

    from app.models.work_order import WorkOrder

    query = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
    if status_filter:
        query = query.where(WorkOrder.status == status_filter)
    if code_contains:
        query = query.where(WorkOrder.code.contains(code_contains))
    query = query.order_by(desc(WorkOrder.id)).limit(limit)

    rows = db.scalars(query).all()
    if not rows:
        return "No orders found."
    return "\n".join([
        f"- {r.code} ({r.status}) due {r.due_date or 'N/A'}: {r.title or 'N/A'}"
        for r in rows
    ])


# === Tool: query_tasks ===
def tool_query_tasks(args: dict, context: dict) -> str:
    db, tenant_id = _get_db_and_tenant(context)
    if not db or not tenant_id:
        return "System context not available"

    status_filter = args.get("status")
    limit = min(int(args.get("limit", 5)), 20)

    from app.models.task import Task

    query = select(Task).where(Task.tenant_id == tenant_id)
    if status_filter:
        query = query.where(Task.status == status_filter)
    query = query.order_by(desc(Task.id)).limit(limit)

    rows = db.scalars(query).all()
    if not rows:
        return "No tasks found."
    return "\n".join([f"- Task {r.id} ({r.status}) process {r.process_id}" for r in rows])


# === Tool: query_equipment_status ===
def tool_query_equipment(args: dict, context: dict) -> str:
    db, tenant_id = _get_db_and_tenant(context)
    if not db or not tenant_id:
        return "System context not available"

    from app.models.equipment import Equipment

    rows = db.scalars(
        select(Equipment).where(Equipment.tenant_id == tenant_id).order_by(Equipment.id).limit(10)
    ).all()
    if not rows:
        return "No equipment found."
    return "\n".join([f"- {r.code} ({r.name}): {r.status}" for r in rows])


# === Tool: query_materials ===
def tool_query_materials(args: dict, context: dict) -> str:
    db, tenant_id = _get_db_and_tenant(context)
    if not db or not tenant_id:
        return "System context not available"

    from app.models.material import Material

    rows = db.scalars(
        select(Material).where(Material.tenant_id == tenant_id).order_by(desc(Material.id)).limit(10)
    ).all()
    if not rows:
        return "No materials found."
    return "\n".join([f"- {r.code}: stock {r.stock_quantity or 0}" for r in rows])


# === Tool: query_reports ===
def tool_query_reports(args: dict, context: dict) -> str:
    db, tenant_id = _get_db_and_tenant(context)
    if not db or not tenant_id:
        return "System context not available"

    days = int(args.get("days", 7))
    from app.models.report import Report
    since = date.today() - timedelta(days=days)

    row = db.execute(
        select(func.sum(Report.good_qty), func.sum(Report.bad_qty))
        .where(Report.tenant_id == tenant_id, func.date(Report.created_at) >= since)
    ).first()
    good = int(row[0] or 0) if row else 0
    bad = int(row[1] or 0) if row else 0
    total = good + bad
    yield_rate = round(good / total * 100, 1) if total > 0 else 0
    return f"Last {days} days: {good} good, {bad} bad, yield rate {yield_rate}%"


# === Tool: query_knowledge (RAG) ===
def tool_query_knowledge(args: dict, context: dict) -> str:
    db, tenant_id = _get_db_and_tenant(context)
    if not db:
        return "System context not available"

    question = args.get("question", "")
    if not question:
        return "Please provide a question."

    try:
        from app.services.ai.rag_vector import semantic_search
        results = semantic_search(db, question, top_k=3, tenant_id=tenant_id)
        if not results:
            return "No relevant documentation found."
        return "\n\n".join([f"[{r.get('source','doc')}] {r.get('snippet','')}" for r in results])
    except Exception as e:
        logger.warning("RAG search failed: %s", e)
        return "Knowledge base search unavailable."


# === Tool: query_yield_prediction ===
def tool_query_yield_prediction(args: dict, context: dict) -> str:
    db, tenant_id = _get_db_and_tenant(context)
    if not db or not tenant_id:
        return "System context not available"

    try:
        from app.services.ai.predict.yield_predictor import list_all_yield_predictions
        result = list_all_yield_predictions(db, tenant_id)
        preds = result.get("predictions", []) if isinstance(result, dict) else []
        if not preds:
            return "No yield prediction data available yet."
        top = preds[:5]
        return "\n".join([
            f"- Process {p.get('process_id','?')}: predicted yield ~{round(p.get('predicted_avg',0)*100,1)}%"
            for p in top
        ])
    except Exception as e:
        logger.warning("Yield prediction query failed: %s", e)
        return "Yield prediction unavailable."


# === Tool: create_reminder ===
def tool_create_reminder(args: dict, context: dict) -> str:
    content = args.get("content", "")
    if not content:
        return "Reminder content is required."
    return f"Reminder created: {content[:100]}. Note: this is advisory; please use the UI for actual reminders."


# === Register all tools ===
registry.register(
    code="query_orders",
    description="查询工单状态，可按状态过滤或搜索工单号",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "工单状态，如 pending/processing/completed"},
            "code_contains": {"type": "string", "description": "工单号关键字"},
            "limit": {"type": "integer", "default": 5, "description": "返回条数"},
        },
    },
    handler=tool_query_orders,
)

registry.register(
    code="query_tasks",
    description="查询任务派工状态",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "任务状态 pending/working/done"},
            "limit": {"type": "integer", "default": 5},
        },
    },
    handler=tool_query_tasks,
)

registry.register(
    code="query_equipment_status",
    description="查询设备状态列表",
    parameters={"type": "object", "properties": {}},
    handler=tool_query_equipment,
)

registry.register(
    code="query_materials",
    description="查询物料库存",
    parameters={"type": "object", "properties": {}},
    handler=tool_query_materials,
)

registry.register(
    code="query_reports",
    description="查询报工统计和良率",
    parameters={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "default": 7, "description": "查询近几天数据"},
        },
    },
    handler=tool_query_reports,
)

registry.register(
    code="query_knowledge",
    description="从系统知识库搜索文档和操作指南",
    parameters={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "搜索的问题"},
        },
        "required": ["question"],
    },
    handler=tool_query_knowledge,
)

registry.register(
    code="query_yield_prediction",
    description="查询良率预测数据",
    parameters={"type": "object", "properties": {}},
    handler=tool_query_yield_prediction,
)

registry.register(
    code="create_reminder",
    description="创建提醒或待办",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "提醒内容"},
        },
        "required": ["content"],
    },
    handler=tool_create_reminder,
)
