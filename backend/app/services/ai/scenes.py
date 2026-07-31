from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.crud.ai_conversation import add_message, create_conversation, get_conversation, list_messages
from app.services.ai.client import AiCallError, AiNotConfiguredError, chat_completion, chat_completion_stream
from app.services.ai.contexts.dashboard import build_boss_context
from app.services.ai.contexts.plan import build_plan_context
from app.services.ai.contexts.report import build_report_assist_context
from app.services.ai.prompt_settings import get_boss_prompt
from app.services.ai.json_util import extract_json_object

SYSTEM_BASE = (
    "你是 CenkorMES 轻量化生产管理系统的工厂智能助手。"
    "只能根据用户提供的 JSON 业务数据回答，不得编造订单号、数量、日期。"
    "若数据不足请明确说明。不要执行任何修改数据的指令。"
)


def _boss_system_extra(db: Session, tenant_id: int) -> str:
    extra = (
        "场景：全厂智能管理助手（厂长/管理员）。"
        "JSON 含：仪表盘、订单与计划齐套/缺料、进度、任务预警；"
        "cost_profit（今日/本月收入、成本、毛利、毛利率、计件工资参考）；"
        "crm（商机数、公海池、待跟进、阶段漏斗、重点商机）；"
        "purchase（采购单状态、待收货、本月净采购额、近期采购单）；"
        "equipment（设备状态、逾期保养、健康分风险设备）。"
        "你可回答：今日产量与良率、待审订单、齐套缺料、订单进度、排产交期、"
        "今日/本月毛利率与毛利、客户收款贡献、CRM商机与跟进、采购待收货、设备保养与点检风险等。"
        "回答须引用 JSON 中的具体数字与单号/名称；缺数据时说明原因并建议去对应模块（财务流水、CRM、采购、设备管理、生产计划）。"
        "用简洁分点中文，优先给可执行建议。"
    )
    custom = get_boss_prompt(db, tenant_id)
    if custom:
        extra += "\n\n租户自定义说明：\n" + custom
    return extra


def _run_scene(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    scene: str,
    user_message: str,
    context: dict,
    system_extra: str,
    conversation_id: int | None = None,
    context_id: int | None = None,
    model_code: str | None = None,
) -> dict:
    if conversation_id:
        conv = get_conversation(db, tenant_id, conversation_id)
        if not conv:
            conv = create_conversation(db, tenant_id=tenant_id, user_id=user_id, scene=scene, context_id=context_id)
    else:
        conv = create_conversation(db, tenant_id=tenant_id, user_id=user_id, scene=scene, context_id=context_id)

    history = list_messages(db, conv.id, limit=10)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_BASE + "\n" + system_extra},
        {"role": "system", "content": "业务数据 JSON:\n" + json.dumps(context, ensure_ascii=False, default=str)},
    ]
    for m in history[-8:]:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_message})

    add_message(db, conversation_id=conv.id, role="user", content=user_message)
    try:
        reply, tin, tout = chat_completion(
            db, tenant_id=tenant_id, messages=messages, model_code=model_code
        )
    except (AiNotConfiguredError, AiCallError) as e:
        raise

    add_message(db, conversation_id=conv.id, role="assistant", content=reply, tokens_in=tin, tokens_out=tout)
    return {"conversation_id": conv.id, "reply": reply, "structured": extract_json_object(reply)}


def _prepare_boss_qa(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    message: str,
    conversation_id: int | None = None,
    model_code: str | None = None,
    context_id: int | None = None,
) -> tuple[object, list[dict[str, str]]]:
    ctx = build_boss_context(db, tenant_id, plan_id=context_id)
    if conversation_id:
        conv = get_conversation(db, tenant_id, conversation_id)
        if not conv:
            conv = create_conversation(db, tenant_id=tenant_id, user_id=user_id, scene="boss_qa")
    else:
        conv = create_conversation(db, tenant_id=tenant_id, user_id=user_id, scene="boss_qa")

    history = list_messages(db, conv.id, limit=10)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_BASE + "\n" + _boss_system_extra(db, tenant_id)},
        {"role": "system", "content": "业务数据 JSON:\n" + json.dumps(ctx, ensure_ascii=False, default=str)},
    ]
    for m in history[-8:]:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": message})
    add_message(db, conversation_id=conv.id, role="user", content=message)
    return conv, messages


def boss_qa_stream_chunks(
    db: Session,
    tenant_id: int,
    user_id: int,
    message: str,
    conversation_id: int | None = None,
    model_code: str | None = None,
    context_id: int | None = None,
):
    """生成 SSE 文本片段；调用方在流结束后 commit。"""
    conv, messages = _prepare_boss_qa(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        message=message,
        conversation_id=conversation_id,
        model_code=model_code,
        context_id=context_id,
    )
    parts: list[str] = []
    tokens_in: int | None = None
    tokens_out: int | None = None
    for chunk in chat_completion_stream(db, tenant_id=tenant_id, messages=messages, model_code=model_code):
        if chunk.delta:
            parts.append(chunk.delta)
            yield ("delta", chunk.delta)
        if chunk.tokens_in is not None:
            tokens_in = chunk.tokens_in
        if chunk.tokens_out is not None:
            tokens_out = chunk.tokens_out
    reply = "".join(parts).strip()
    add_message(
        db,
        conversation_id=conv.id,
        role="assistant",
        content=reply,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    yield ("done", {"conversation_id": conv.id, "reply": reply})


def boss_qa(
    db: Session,
    tenant_id: int,
    user_id: int,
    message: str,
    conversation_id: int | None = None,
    model_code: str | None = None,
    context_id: int | None = None,
) -> dict:
    ctx = build_boss_context(db, tenant_id, plan_id=context_id)
    return _run_scene(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        scene="boss_qa",
        user_message=message,
        context=ctx,
        system_extra=_boss_system_extra(db, tenant_id),
        conversation_id=conversation_id,
        context_id=context_id,
        model_code=model_code,
    )


def plan_risk(db: Session, tenant_id: int, user_id: int, plan_id: int) -> dict:
    ctx = build_plan_context(db, tenant_id, plan_id)
    prompt = (
        "请分析该生产计划的交期风险。"
        "输出 JSON：{\"risk_level\":\"low|medium|high\",\"summary\":\"\",\"risks\":[\"\"],\"suggestions\":[\"\"]}"
        "然后再用一段话说明。"
    )
    out = _run_scene(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        scene="plan_risk",
        user_message=prompt,
        context=ctx,
        system_extra="场景：生产计划交期风险分析。必须基于 JSON 数据。",
        context_id=plan_id,
    )
    structured = out.get("structured") or {}
    return {
        **out,
        "risk_level": structured.get("risk_level"),
        "summary": structured.get("summary"),
        "risks": structured.get("risks") or [],
        "suggestions": structured.get("suggestions") or [],
    }


def plan_schedule(db: Session, tenant_id: int, user_id: int, plan_id: int) -> dict:
    ctx = build_plan_context(db, tenant_id, plan_id)
    prompt = (
        "请给出智能排产建议。"
        "输出 JSON：{"
        "\"suggest_mode\":\"backward|forward\","
        "\"suggest_start_date\":\"YYYY-MM-DD|null\","
        "\"suggest_end_date\":\"YYYY-MM-DD|null\","
        "\"suggest_work_days\":number|null,"
        "\"dispatch_hints\":[\"\"],"
        "\"overload_warnings\":[\"\"]"
        "}"
        "然后再用一段话说明排产思路。"
    )
    out = _run_scene(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        scene="plan_schedule",
        user_message=prompt,
        context=ctx,
        system_extra=(
            "场景：智能排产建议。建议日期须与订单交期、工作日逻辑一致。"
            "若计划状态为「计划中」，用户点「采纳并执行」时会先自动按交期排产、再尝试确认下发并派工；"
            "下发需订单已审核、物料齐套（或允许缺料）。未下发前不存在可派工任务，勿建议「直接派工」而不提下发前提。"
        ),
        context_id=plan_id,
    )
    structured = out.get("structured") or {}
    return {
        **out,
        "suggest_mode": structured.get("suggest_mode"),
        "suggest_start_date": structured.get("suggest_start_date"),
        "suggest_end_date": structured.get("suggest_end_date"),
        "suggest_work_days": structured.get("suggest_work_days"),
        "dispatch_hints": structured.get("dispatch_hints") or [],
        "overload_warnings": structured.get("overload_warnings") or [],
    }


def report_assist(
    db: Session,
    tenant_id: int,
    user_id: int,
    *,
    task_id: int,
    result_type: str,
    remark: str,
    good_qty: int | None = None,
    bad_qty: int | None = None,
) -> dict:
    ctx = build_report_assist_context(
        db,
        tenant_id,
        task_id=task_id,
        user_id=user_id,
        result_type=result_type,
        remark=remark,
        good_qty=good_qty,
        bad_qty=bad_qty,
    )
    prompt = (
        "员工即将提交报工，请检查数量与备注是否合理。"
        "业务数据 JSON 中 use_unit_report=true 表示件次报工：每次固定 1 件，"
        "只看 result_type（good/bad）与 remark，不要提示填写 good_qty/bad_qty。"
        "use_unit_report=false 为批量报工：需确认 good_qty+bad_qty 已填写且不超过 remaining_qty。"
        "输出 JSON：{\"ok\":true|false,\"hints\":[\"\"],\"suggest_remark\":\"\"}"
    )
    out = _run_scene(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        scene="report_assist",
        user_message=prompt,
        context=ctx,
        system_extra="场景：报工提交前辅助。不得代替员工提交。",
        context_id=task_id,
    )
    structured = out.get("structured") or {}
    return {
        **out,
        "ok": structured.get("ok", True),
        "hints": structured.get("hints") or [],
        "suggest_remark": structured.get("suggest_remark"),
    }


def audit_batch_summary(db: Session, tenant_id: int, user_id: int, *, status: str = "submitted", limit: int = 30) -> dict:
    from app.crud.report_unit import list_report_units

    items = list_report_units(db, tenant_id=tenant_id, status=status, offset=0, limit=limit)
    rows = []
    for u in items:
        rows.append(
            {
                "id": u.id,
                "status": u.status,
                "result_type": u.result_type,
                "remark": (u.remark or "")[:200],
                "user": u.user.full_name if u.user else None,
                "task_code": u.task.task_code if u.task else None,
            }
        )
    ctx = {"pending_count": len(rows), "items": rows, "status_filter": status}
    if not rows:
        return {
            "conversation_id": None,
            "reply": "",
            "structured": {},
            "high_risk_ids": [],
            "summary": "当前无待审记录",
            "risk_points": [],
            "suggest_actions": [],
            "pending_count": 0,
        }
    prompt = (
        "你是报工审核助手。根据待审列表 JSON，输出批量审核摘要。"
        "JSON：{\"high_risk_ids\":[],\"summary\":\"\",\"risk_points\":[\"\"],\"suggest_actions\":[\"\"]}"
        "然后再用一段话说明。"
    )
    out = _run_scene(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        scene="audit_summary",
        user_message=prompt,
        context=ctx,
        system_extra="场景：待审报工批量 AI 摘要。不得编造未出现的记录。",
    )
    structured = out.get("structured") or {}
    return {
        **out,
        "high_risk_ids": structured.get("high_risk_ids") or [],
        "summary": structured.get("summary"),
        "risk_points": structured.get("risk_points") or [],
        "suggest_actions": structured.get("suggest_actions") or [],
        "pending_count": len(rows),
    }


def report_vision_audit(db: Session, tenant_id: int, user_id: int, report_unit_id: int) -> dict:
    from app.crud.attachment import get_attachments_by_ids
    from app.crud.report_unit import get_unit_by_id, _parse_attachment_ids
    from app.services.ai.client import vision_completion
    from app.services.attachment_media import attachment_play_url

    unit = get_unit_by_id(db, tenant_id=tenant_id, unit_id=report_unit_id)
    if not unit:
        return {"ok": False, "error": "报工记录不存在"}
    ids = _parse_attachment_ids(unit.employee_attachment_ids)
    atts = get_attachments_by_ids(db, tenant_id, ids)
    urls = [attachment_play_url(a, db=db) for a in atts if attachment_play_url(a, db=db)]
    if not urls:
        return {"ok": False, "error": "无员工上传的图片/视频附件"}

    prompt = (
        "你是质检员助手。查看报工现场照片，判断是否存在明显质量问题或与备注不符。"
        "输出 JSON：{\"risk_level\":\"low|medium|high\",\"findings\":[\"\"],\"match_remark\":true|false,\"summary\":\"\"}"
    )
    ctx_text = f"报工结果={unit.result_type} 备注={(unit.remark or '')[:300]}"
    reply, tin, tout = vision_completion(
        db,
        tenant_id=tenant_id,
        image_urls=urls,
        prompt=ctx_text + "\n" + prompt,
    )
    structured = extract_json_object(reply)
    return {
        "ok": True,
        "reply": reply,
        "structured": structured,
        "risk_level": (structured or {}).get("risk_level"),
        "findings": (structured or {}).get("findings") or [],
        "match_remark": (structured or {}).get("match_remark"),
        "summary": (structured or {}).get("summary"),
        "image_count": len(urls),
        "tokens_in": tin,
        "tokens_out": tout,
    }


# =========================================================================
# 拍照自动计数（photo_count）
# =========================================================================


def photo_count(
    db: Session,
    tenant_id: int,
    user_id: int,
    *,
    image_urls: list[str],
    hint: str | None = None,
) -> dict:
    """调用视觉大模型统计图片中的同类零件数量。

    适用于批量报工中“拍一张照片让 AI 自动数”场景。
    员工需多角度拍照，AI 透视转换后求总数。
    """
    from app.services.ai.client import vision_completion

    if not image_urls:
        return {"ok": False, "error": "未提供图片"}

    ctx_text = ""
    if hint:
        ctx_text = f"员工提示：{hint}\n"
    ctx_text += f"共 {len(image_urls)} 张图片，请先识别“同一种类零件”后再分张计数。"

    prompt = (
        "你是工业计数助手。任务：精确数出每张图片中同类零件的总数（重叠、堆叠、需估算）。"
        "如多张图为同一批零件的不同视角（可互补），输出一个总数字。"
        "输出 JSON：{"
        "\"count\": <整数>,"  # noqa: E501 - keeps the docstring formatter happy
        "\"confidence\": \"high|medium|low\","
        "\"per_image\": [<int>, ...],"
        "\"note\": \"<简明说明，如 1 号图 50 件×重叠 30% 估算，2 号图 60 件>\""
        "}"
    )
    reply, tin, tout = vision_completion(
        db,
        tenant_id=tenant_id,
        image_urls=image_urls,
        prompt=ctx_text + "\n" + prompt,
        temperature=0.1,
        max_tokens=512,
    )
    structured = extract_json_object(reply)
    try:
        count = int(structured.get("count", 0))
    except (TypeError, ValueError):
        count = 0
    return {
        "ok": True,
        "reply": reply,
        "structured": structured,
        "count": count,
        "confidence": structured.get("confidence") or "low",
        "per_image": structured.get("per_image") or [],
        "note": structured.get("note"),
        "image_count": len(image_urls),
        "tokens_in": tin,
        "tokens_out": tout,
    }


# =========================================================================
# 语音报工解析（voice_parse_report）
# =========================================================================


def voice_parse_report(
    db: Session,
    tenant_id: int,
    user_id: int,
    *,
    text: str,
    task_id: int | None = None,
) -> dict:
    """从员工口述文本中提取报工结构化字段。

    支持的表达例如：
        "做了 50 件合格 3 件不良，有毛刺。"
        "总共 120 个，都合格。"
        "不良两个，都是划痕。"
    """
    ctx: dict = {}
    if task_id:
        from app.services.ai.contexts.report import build_report_assist_context

        try:
            ctx["task"] = build_report_assist_context(
                db,
                tenant_id,
                task_id=task_id,
                user_id=user_id,
                result_type="good",
                remark="",
            )
        except Exception:
            pass

    # 将员工口述文本直接嵌入 user_message，让 LLM 明确知道要解析什么
    prompt = (
        f'员工口述内容："{text}"\n\n'
        "请从上述口述内容中提取结构化字段，只输出 JSON，不要输出其他内容：\n"
        "{\n"
        '  "good_qty": <合格品数量，整数；提取不到则 null>,\n'
        '  "bad_qty": <不良品数量，整数；提取不到则 null>,\n'
        '  "result_type": "good 或 bad 或 mixed",\n'
        '  "remark": "<员工原话或精简后的中文备注，不超过 100 字>",\n'
        '  "defect_keywords": ["<缺陷关键词，如 划痕/变形/色差，仅文本明确提到时才填>"]\n'
        "}\n\n"
        "解析规则：\n"
        "- result_type：全合格→good、全不良→bad、有合格有不良→mixed\n"
        "- 数字必须为整数，中文数字（如'五十'）也需转为阿拉伯数字\n"
        "- 未提到的数量字段设为 null，不得编造\n"
        "- defect_keywords 仅在口述中明确提到缺陷时才填充"
    )
    out = _run_scene(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        scene="voice_parse_report",
        user_message=prompt,
        context=ctx,
        system_extra="场景：报工语音转写后的结构化解析。只输出 JSON，不得编造未出现的数字。",
        context_id=task_id,
    )
    structured = out.get("structured") or {}
    good_qty = _safe_int(structured.get("good_qty"))
    bad_qty = _safe_int(structured.get("bad_qty"))
    # 生成 summary 供前端直接展示
    parts = []
    if good_qty is not None:
        parts.append(f"合格 {good_qty} 件")
    if bad_qty is not None:
        parts.append(f"不良 {bad_qty} 件")
    summary = "，".join(parts) if parts else text
    return {
        **out,
        "good_qty": good_qty,
        "bad_qty": bad_qty,
        "result_type": structured.get("result_type") or "good",
        "remark": structured.get("remark"),
        "defect_keywords": structured.get("defect_keywords") or [],
        "summary": summary,
    }


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# =========================================================================
# AI 缺陷自动分类（defect_classify）
# =========================================================================


def defect_classify(
    db: Session,
    tenant_id: int,
    user_id: int,
    *,
    image_urls: list[str],
    task_id: int | None = None,
    remark: str | None = None,
) -> dict:
    """根据员工上传的不良品照片自动识别缺陷类型。

    从租户已配置的 defect_codes 中选择最匹配项，
    返回 {defect_code_id, defect_code, severity, confidence, description}。
    """
    from sqlalchemy import select

    from app.crud.quality import list_defect_codes
    from app.services.ai.client import vision_completion

    if not image_urls:
        return {"ok": False, "error": "未提供图片"}

    codes = list_defect_codes(db, tenant_id=tenant_id, offset=0, limit=200) or []
    active_codes = [c for c in codes if getattr(c, "is_active", True)]
    code_options = [
        {
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "severity": c.severity,
            "description": c.description or "",
        }
        for c in active_codes
    ]
    if not code_options:
        return {"ok": False, "error": "租户未配置缺陷代码，请先在“质量设置”维护"}

    ctx_text = f"员工备注：{(remark or '')[:200]}\n"
    ctx_text += f"可选缺陷代码列表（id=... code=... name=... severity=...）：\n{json.dumps(code_options, ensure_ascii=False)}"

    prompt = (
        "你是质检员助手。查看不良品照片，从“可选缺陷代码列表”中选出最匹配的一项。"
        "如果都不完全匹配，选最接近的，并在 description 中说明差异。"
        "输出 JSON：{"
        "\"defect_code_id\": <int 或 null>,"
        "\"defect_code\": \"<code 值>\","
        "\"defect_name\": \"<name 值>\","
        "\"severity\": \"critical|major|minor\","
        "\"confidence\": \"high|medium|low\","
        "\"description\": \"<中文描述，不超过 60 字>\""
        "}"
    )
    reply, tin, tout = vision_completion(
        db,
        tenant_id=tenant_id,
        image_urls=image_urls,
        prompt=ctx_text + "\n" + prompt,
        temperature=0.1,
        max_tokens=512,
    )
    structured = extract_json_object(reply)
    defect_id = structured.get("defect_code_id")
    # 验证返回的 id 在合法集合中
    if defect_id is not None:
        valid_ids = {c["id"] for c in code_options}
        try:
            defect_id = int(defect_id)
            if defect_id not in valid_ids:
                defect_id = None
        except (TypeError, ValueError):
            defect_id = None
    return {
        "ok": True,
        "reply": reply,
        "structured": structured,
        "defect_code_id": defect_id,
        "defect_code": structured.get("defect_code"),
        "defect_name": structured.get("defect_name"),
        "severity": structured.get("severity"),
        "confidence": structured.get("confidence") or "low",
        "description": structured.get("description"),
        "image_count": len(image_urls),
        "tokens_in": tin,
        "tokens_out": tout,
        "options_count": len(code_options),
    }


# =========================================================================
# 换班/交接 AI 摘要（shift_handover_summary）
# =========================================================================


def shift_handover_summary(
    db: Session,
    tenant_id: int,
    user_id: int,
    *,
    shift_start: str | None = None,
    shift_hours: int = 8,
) -> dict:
    """汇总指定班次内的报工数据，调用 LLM 生成自然语言交接摘要。"""
    from datetime import datetime, timedelta

    from app.models.report import Report
    from app.models.task_assignment import TaskAssignment

    if shift_start:
        try:
            start_dt = datetime.fromisoformat(shift_start)
        except ValueError:
            start_dt = datetime.now() - timedelta(hours=shift_hours)
    else:
        start_dt = datetime.now() - timedelta(hours=shift_hours)
    end_dt = start_dt + timedelta(hours=shift_hours)

    # 件次报工（unit）
    from app.models.report_unit import ReportUnit as _RU

    unit_q = (
        select(_RU)
        .where(
            _RU.tenant_id == tenant_id,
            _RU.created_at >= start_dt,
            _RU.created_at < end_dt,
        )
        .order_by(_RU.id.desc())
        .limit(500)
        .options(
            selectinload(_RU.user),
            selectinload(_RU.task),
        )
    )
    units = db.scalars(unit_q).all()
    # 批量报工（report）
    rep_q = (
        select(Report)
        .where(
            Report.tenant_id == tenant_id,
            Report.created_at >= start_dt,
            Report.created_at < end_dt,
        )
        .order_by(Report.id.desc())
        .limit(200)
    )
    reports = db.scalars(rep_q).all()

    # 统计
    total_good = 0
    total_bad = 0
    rejected = 0
    units_summary = []
    for u in units:
        if u.result_type == "good":
            total_good += 1
        elif u.result_type == "bad":
            total_bad += 1
        if u.status == "rejected":
            rejected += 1
        units_summary.append(
            {
                "id": u.id,
                "task_code": u.task.task_code if u.task else None,
                "result_type": u.result_type,
                "status": u.status,
                "remark": (u.remark or "")[:120],
                "user": u.user.full_name if u.user else None,
            }
        )
    reports_summary = []
    for r in reports:
        total_good += int(r.good_qty or 0)
        total_bad += int(r.bad_qty or 0)
        if r.status == "rejected":
            rejected += 1
        reports_summary.append(
            {
                "id": r.id,
                "task_code": r.task.task_code if r.task else None,
                "good_qty": r.good_qty,
                "bad_qty": r.bad_qty,
                "status": r.status,
                "remark": (r.remark or "")[:120],
                "user": r.user.full_name if r.user else None,
            }
        )

    # 未完成任务（仍处于 assigned 状态）
    reported_subq = (
        select(func.count(_RU.id))
        .where(
            _RU.tenant_id == tenant_id,
            _RU.task_assignment_id == TaskAssignment.id,
            _RU.status != "rejected",
            _RU.result_type.isnot(None),
        )
        .correlate(TaskAssignment)
        .scalar_subquery()
    )
    open_assign_q = (
        select(func.count(TaskAssignment.id))
        .where(
            TaskAssignment.tenant_id == tenant_id,
            reported_subq < TaskAssignment.assigned_qty,
        )
    )
    open_assign_count = int(db.scalar(open_assign_q) or 0)

    ctx = {
        "shift_start": start_dt.isoformat(timespec="minutes"),
        "shift_end": end_dt.isoformat(timespec="minutes"),
        "totals": {
            "unit_count": len(units),
            "report_count": len(reports),
            "good": total_good,
            "bad": total_bad,
            "rejected": rejected,
            "open_assignments": open_assign_count,
        },
        "units": units_summary[:30],
        "reports": reports_summary[:20],
    }
    prompt = (
        "请根据“班次报工数据 JSON”生成交接班摘要中文文本。"
        "输出 JSON：{"
        "\"summary\": \"<3-5 句交接描述>\","
        "\"highlights\": [\"<亮点，最多 3 条>\"],"
        "\"alerts\": [\"<需交接注意的事项>\"],"
        "\"unfinished\": [\"<未完成的任务代号 / 工序>\""
        "]}"
        "重点说：完成数与良率、被驳回项及原因、未完成任务。"
    )
    out = _run_scene(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        scene="shift_handover",
        user_message=prompt,
        context=ctx,
        system_extra="场景：交接班 AI 摘要。数据为空时说明“本班次无报工数据”。",
        context_id=None,
    )
    structured = out.get("structured") or {}
    return {
        **out,
        "shift_start": ctx["shift_start"],
        "shift_end": ctx["shift_end"],
        "totals": ctx["totals"],
        "summary": structured.get("summary") or "",
        "highlights": structured.get("highlights") or [],
        "alerts": structured.get("alerts") or [],
        "unfinished": structured.get("unfinished") or [],
    }
