// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
// H5 侧 AI 能力统一走付费扩展 /extensions/*（飞书为核心免费能力，见 api/feishu.ts）
import { apiDelete, apiGet, apiPatch, apiPost } from '@/utils/http'

const AI_TIMEOUT_MS = 120_000

export type AiHelpOut = {
  answer: string
  sources: Array<{ source: string; title: string; snippet?: string }>
}

export type AiChatOut = {
  conversation_id: number
  reply: string | null
  available?: boolean
  degraded?: boolean
  error?: boolean
  hint?: string
  tokens_in?: number | null
  tokens_out?: number | null
}

export type AlertItem = {
  id: number
  level: string
  title: string
  summary?: string
  detail?: string
  root_cause?: string
  suggestion?: string
  status?: string
  status_label?: string
  dim_label?: string
  dim?: string
  code?: string
  severity?: string
  score?: number
  entity_type?: string
  entity_id?: number | string | null
  entity_name?: string
  facts?: { [key: string]: string | number | null } | null
  ai_insight?: string | null
  ai_insight_at?: string | null
  first_seen_at?: string
  last_seen_at?: string
}

export type AiBriefOut = {
  mode: string
  content: string
  data?: Record<string, unknown>
}

export type AiInsightItem = {
  axis: string
  name: string
  headline?: string
  error?: string
}

export type EmployeeTool = { code: string; name: string; desc: string }

export type SceneDoc = {
  id: number
  doc_type: string
  title: string
  report?: string
  rule_summary?: string
  risks?: string[]
  suggestions?: string[]
  generated_at?: string
}

export type TaskRecommendItem = {
  task_id: number
  task_code: string
  process_name: string | null
  remaining_qty: number
  assigned_qty: number
  reported_qty: number
  priority: 'urgent' | 'normal' | 'low'
  last_report_at: string | null
  reason: string
}

function asInt(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? Math.trunc(n) : null
}

function parseJsonBlock(text: string): Record<string, any> | null {
  if (!text) return null
  const m = text.match(/\{[\s\S]*\}/)
  if (!m) return null
  try {
    return JSON.parse(m[0])
  } catch {
    return null
  }
}

// ── AI 助手（对话 / 知识库帮助）────────────────────────────────────────────

export function aiHelp(question: string) {
  return apiPost<{ answer?: string | null; hits?: any[]; hint?: string; degraded?: boolean }>(
    '/extensions/ai_assistant/help',
    { q: question },
    { timeout: AI_TIMEOUT_MS },
  ).then<AiHelpOut>((r) => ({
    answer: r.answer || r.hint || '知识库暂未命中相关条目',
    sources: (r.hits || []).map((h: any) => ({
      source: h.source || h.doc_type || '知识库',
      title: h.title || '',
      snippet: h.text || h.snippet,
    })),
  }))
}

export function aiChat(data: {
  message: string
  conversation_id?: number | null
  model_code?: string
  kind?: string
}) {
  return apiPost<{
    reply?: string | null
    conversation_id: number
    hint?: string
    tokens_in?: number | null
    tokens_out?: number | null
  }>(
    '/extensions/ai_assistant/chat',
    {
      message: data.message,
      conversation_id: data.conversation_id ?? undefined,
      kind: data.kind || 'assistant',
      model_code: data.model_code,
    },
    { timeout: AI_TIMEOUT_MS },
  ).then<AiChatOut>((r) => ({
    conversation_id: r.conversation_id,
    reply: r.reply || r.hint || '暂无回复',
    tokens_in: r.tokens_in,
    tokens_out: r.tokens_out,
  }))
}

// ── 深度洞察 ───────────────────────────────────────────────────────────────

export function getAiBrief() {
  return apiGet<{ items?: AiInsightItem[]; generated_at?: string }>(
    '/extensions/ai_insight/summary',
    { params: { days: 7 }, timeout: AI_TIMEOUT_MS },
  ).then<AiBriefOut>((r) => ({
    mode: 'rule',
    content: (r.items || [])
      .map((it) => `${it.name}：${it.headline || (it.error ? `取数失败（${it.error}）` : '暂无数据')}`)
      .join('\n'),
    data: { items: r.items || [], generated_at: r.generated_at },
  }))
}

export function listAiInsight() {
  return apiGet<{ items?: AiInsightItem[]; generated_at?: string }>(
    '/extensions/ai_insight/summary',
    { params: { days: 30 }, timeout: AI_TIMEOUT_MS },
  )
}

export function analyzeInsight(axis: string, days = 30) {
  return apiPost<{ ok?: boolean; report?: string; rule_summary?: string; error?: string }>(
    '/extensions/ai_insight/analyze',
    { axis, days, use_llm: true },
    { timeout: AI_TIMEOUT_MS },
  )
}

// ── 异常预警 ───────────────────────────────────────────────────────────────

export function listAiAlerts(params: { dim?: string; severity?: string; status?: string; limit?: number } = {}) {
  return apiGet<{
    items?: AlertItem[]
    total_active?: number
    by_status?: { [key: string]: number }
    by_severity?: { [key: string]: number }
    status_labels?: { [key: string]: string }
  }>(
    '/extensions/ai_anomaly/alerts',
    { params: { status: 'all', limit: 100, ...params }, timeout: 30_000 },
  )
}

export function runAiAlerts() {
  return apiPost<{ events?: number; notified?: number }>(
    '/extensions/ai_anomaly/scan',
    undefined,
    { timeout: AI_TIMEOUT_MS },
  )
}

export function handleAlert(id: number, status: string) {
  return apiPost<{ ok: boolean }>(
    `/extensions/ai_anomaly/alerts/${id}/handle`,
    { status },
    { timeout: 30_000 },
  )
}

// ── 数字员工 ───────────────────────────────────────────────────────────────

export function listEmployeeTools() {
  return apiGet<{ enabled: boolean; tools: EmployeeTool[] }>('/extensions/ai_employee/tools')
}

export function employeeOverview() {
  return apiGet<{ total_runs?: number; runs_last_24h?: number; recent?: any[] }>(
    '/extensions/ai_employee/overview',
  )
}

export function executeEmployeeTool(tool: string, instruction?: string) {
  return apiPost<{ ok: boolean; report?: string; rule_summary?: string; error?: string; facts?: any }>(
    '/extensions/ai_employee/execute',
    { tool, instruction, use_llm: true },
    { timeout: AI_TIMEOUT_MS },
  )
}

// ── 场景文书 ───────────────────────────────────────────────────────────────

export type SceneField = {
  key: string
  label: string
  type: string
  placeholder?: string
  default?: string | number
  options?: string[]
}

export type SceneScenario = {
  code: string
  name: string
  desc: string
  fields?: SceneField[]
}

export function listSceneScenarios() {
  return apiGet<{ scenarios: SceneScenario[]; enabled?: boolean; note?: string; defaults?: Record<string, unknown> }>(
    '/extensions/ai_scene_reports/scenarios',
  )
}

export function generateSceneDoc(type: string, params: Record<string, unknown> = {}) {
  return apiPost<SceneDoc & { ok: boolean; error?: string }>(
    '/extensions/ai_scene_reports/generate',
    { type, use_llm: true, ...params },
    { timeout: AI_TIMEOUT_MS },
  )
}

// ── 报工增强（语音 / 拍照 / 缺陷）──────────────────────────────────────────

export type PhotoCountOut = {
  ok: boolean
  count: number
  confidence: 'high' | 'medium' | 'low'
  per_image: number[]
  note?: string | null
  image_count: number
  reply?: string
  error?: string
}

export type VoiceParseOut = {
  good_qty: number | null
  bad_qty: number | null
  result_type: 'good' | 'bad' | 'mixed' | string
  remark?: string | null
  defect_keywords: string[]
  summary?: string
  conversation_id?: number
  reply?: string
}

export type DefectClassifyOut = {
  ok: boolean
  defect_code_id: number | null
  defect_code?: string | null
  defect_name?: string | null
  severity?: 'critical' | 'major' | 'minor' | string | null
  confidence: 'high' | 'medium' | 'low'
  description?: string | null
  image_count: number
  options_count: number
  reply?: string
  error?: string
}

export type ShiftSummaryOut = {
  shift_start: string
  shift_end: string
  totals: {
    unit_count: number
    report_count: number
    good: number
    bad: number
    rejected: number
    open_assignments: number
  }
  summary: string
  highlights: string[]
  alerts: string[]
  unfinished: string[]
  reply?: string
}

/** 拍照自动计数 — 付费扩展 mes_ai_vision */
export function photoAiCount(data: { image_urls: string[]; task_id?: number; hint?: string }) {
  return apiPost<PhotoCountOut>('/extensions/mes_ai_vision/photo-count', data, { timeout: AI_TIMEOUT_MS })
}

/** AI 缺陷自动分类 — 付费扩展 mes_ai_vision */
export function defectAiClassify(data: { image_urls: string[]; task_id?: number; remark?: string }) {
  return apiPost<DefectClassifyOut>('/extensions/mes_ai_vision/defect-classify', data, { timeout: AI_TIMEOUT_MS })
}

/** 语音报工解析 — 由 AI 助手把口述转成结构化字段 */
export async function voiceParseReport(data: { text: string; task_id?: number }): Promise<VoiceParseOut> {
  const r = await apiPost<{ reply?: string | null; conversation_id?: number }>(
    '/extensions/ai_assistant/chat',
    {
      message:
        '你是车间报工解析器。把口述内容解析为 JSON，只输出 JSON，不要解释。' +
        '字段：good_qty(数字或null)、bad_qty(数字或null)、result_type(good|bad|mixed)、' +
        'remark(字符串或null)、defect_keywords(字符串数组)。\n口述：' + data.text,
      kind: 'report',
    },
    { timeout: AI_TIMEOUT_MS },
  )
  const reply = r.reply || ''
  const obj = parseJsonBlock(reply)
  if (obj) {
    return {
      good_qty: asInt(obj.good_qty),
      bad_qty: asInt(obj.bad_qty),
      result_type: String(obj.result_type || (asInt(obj.bad_qty) ? 'mixed' : 'good')),
      remark: obj.remark ?? null,
      defect_keywords: Array.isArray(obj.defect_keywords) ? obj.defect_keywords.map(String) : [],
      summary: reply,
      conversation_id: r.conversation_id,
      reply,
    }
  }
  const good = /合格\s*(\d+)/.exec(data.text)?.[1]
  const bad = /不良\s*(\d+)/.exec(data.text)?.[1]
  return {
    good_qty: good ? Number(good) : null,
    bad_qty: bad ? Number(bad) : null,
    result_type: bad ? 'mixed' : 'good',
    remark: null,
    defect_keywords: [],
    summary: reply || '未能识别结构化数据',
    reply,
  }
}

/** AI 报工自检 — 由 AI 助手给出风险要点 */
export async function reportAiCheck(data: {
  task_id: number
  result_type: string
  remark?: string
  good_qty?: number
  bad_qty?: number
}) {
  const r = await apiPost<{ reply?: string | null }>(
    '/extensions/ai_assistant/chat',
    {
      message:
        `报工数据自检：任务 ${data.task_id}，结果 ${data.result_type}，合格 ${data.good_qty ?? 0}，` +
        `不良 ${data.bad_qty ?? 0}，备注：${data.remark || '无'}。` +
        '请用 2-3 条简短要点指出数据风险与建议，不要客套。',
      kind: 'report',
    },
    { timeout: 60_000 },
  )
  const reply = r.reply || ''
  const hints = reply
    .split('\n')
    .map((s) => s.replace(/^[-*·\d.、\s]+/, '').trim())
    .filter(Boolean)
  return { ok: true, hints, suggest_remark: undefined, reply }
}

/** 交接班摘要 — 付费扩展 ai_scene_reports 的「交接班记录」 */
export async function shiftAiSummary(data: { shift_start?: string; shift_hours?: number } = {}) {
  const r = await generateSceneDoc('shift_handover', {
    shift_start: data.shift_start,
    shift_hours: data.shift_hours,
  })
  if (r.ok === false) throw new Error(r.error || '生成交接摘要失败')
  const facts = (r as any).facts || {}
  const span = String(facts['统计时段'] || '')
  const [start, end] = span.split('~').map((s) => s.trim())
  return {
    shift_start: start || '',
    shift_end: end || '',
    totals: {
      unit_count: Number(facts['逐件报工单元数'] || 0),
      report_count: Number(facts['报工条数'] || 0),
      good: Number(facts['良品数'] || 0),
      bad: Number(facts['不良数'] || 0),
      rejected: 0,
      open_assignments: Number(facts['全厂未完成任务数'] || 0),
    },
    summary: r.report || r.rule_summary || '',
    highlights: [],
    alerts: r.risks || [],
    unfinished: r.suggestions || [],
    reply: r.report,
  } as ShiftSummaryOut
}

/** 将 attachment id 转换为后端可访问的图片 URL（用于 AI 调用） */
export function attachmentIdToUrl(id: number, filename?: string): string {
  const name = filename ? `&filename=${encodeURIComponent(filename)}` : ''
  return `/api/files/${id}?download=true${name}`
}

// ── 第二批：接入后端已有能力（会话历史 / 概览 / 记录 / 归档 / 预览） ───────

export type AssistantConversation = {
  id: number
  kind: string
  title: string
  created_at?: string
  updated_at?: string
  message_count?: number
}

export type AssistantMessage = {
  id: number
  role: string
  content: string
  created_at?: string
}

export function listAssistantConversations(kind = 'assistant') {
  return apiGet<{ items?: AssistantConversation[]; count?: number }>(
    '/extensions/ai_assistant/conversations',
    { params: { kind } },
  )
}

export function getAssistantConversation(id: number) {
  return apiGet<{
    conversation: AssistantConversation | null
    items?: AssistantMessage[]
    found: boolean
  }>(`/extensions/ai_assistant/conversations/${id}`)
}

export function deleteAssistantConversation(id: number) {
  return apiDelete<{ deleted: boolean; found: boolean }>(
    `/extensions/ai_assistant/conversations/${id}`,
  )
}

export type AnomalySummary = {
  health_score?: number
  total_active?: number
  total_events?: number
  total_resolved?: number
  by_dimension?: Record<string, number>
  generated_at?: string
}

export function getAnomalySummary() {
  return apiGet<AnomalySummary>('/extensions/ai_anomaly/summary')
}

export type AnomalyOptionItem = { key: string; label: string; score?: number }
export type AnomalyOptions = {
  dimensions?: AnomalyOptionItem[]
  severities?: AnomalyOptionItem[]
  statuses?: AnomalyOptionItem[]
}

export function getAnomalyOptions() {
  return apiGet<AnomalyOptions>('/extensions/ai_anomaly/options')
}

export function getAlertDetail(id: number) {
  return apiGet<{ alert: AlertItem | null; found: boolean }>(
    `/extensions/ai_anomaly/alerts/${id}`,
  )
}

export function interpretAlert(id: number, refresh = false) {
  return apiPost<{
    found?: boolean
    available?: boolean
    insight?: string
    hint?: string
    cached?: boolean
    degraded?: boolean
    error?: boolean
  }>(`/extensions/ai_anomaly/alerts/${id}/interpret`, { refresh }, { timeout: AI_TIMEOUT_MS })
}

export type InsightAxis = { code: string; name: string; desc?: string }

export function listInsightAxes() {
  return apiGet<{ enabled?: boolean; axes?: InsightAxis[]; default_days?: number; note?: string }>(
    '/extensions/ai_insight/axes',
  )
}

export type InsightRun = {
  id: number
  axis: string
  axis_name?: string
  days?: number
  ai_unavailable?: boolean
  duration_ms?: number
  created_at?: string
  excerpt?: string
}

export function listInsightRuns(params: { axis?: string; page?: number; page_size?: number } = {}) {
  return apiGet<{ items?: InsightRun[]; total?: number; page?: number; page_size?: number }>(
    '/extensions/ai_insight/runs',
    { params },
  )
}

export function getInsightRun(id: number) {
  return apiGet<{
    ok: boolean
    error?: string
    axis_name?: string
    summary?: string
    rule_summary?: string
    report?: string
    risks?: string[]
    suggestions?: string[]
    facts?: { [key: string]: unknown }
    created_at?: string
  }>(`/extensions/ai_insight/runs/${id}`)
}

export type EmployeeLog = {
  id: number
  tool_code?: string
  tool_name?: string
  status?: string
  available?: boolean
  summary?: string
  duration_ms?: number
  created_at?: string
}

// mine=1 只看本人执行记录：/logs 本身是全站时间线，员工端不能默认看全厂
export function listEmployeeLogs(
  params: { tool?: string; status?: string; mine?: number; limit?: number; offset?: number } = {},
) {
  return apiGet<{ items?: EmployeeLog[]; count?: number; total?: number; mine?: boolean }>(
    '/extensions/ai_employee/logs',
    { params },
  )
}

export type EmployeeLogDetail = EmployeeLog & {
  found: boolean
  error?: string
  conversation_id?: number | null
  user_id?: number
  instruction?: string
  facts?: { [key: string]: unknown }
  tokens_in?: number | null
  tokens_out?: number | null
  manage?: boolean
}

export function getEmployeeLog(id: number) {
  return apiGet<EmployeeLogDetail>(`/extensions/ai_employee/logs/${id}`)
}

export function getEmployeeToggle() {
  return apiGet<{ enabled: boolean }>('/extensions/ai_employee/toggle')
}

export type SceneDocItem = {
  id: number
  doc_type: string
  title: string
  type_name?: string
  excerpt?: string
  ai_unavailable?: boolean
  created_at?: string
}

export function listSceneDocs(params: { type?: string; page?: number; page_size?: number } = {}) {
  return apiGet<{ items?: SceneDocItem[]; total?: number; page?: number; page_size?: number }>(
    '/extensions/ai_scene_reports/docs',
    { params },
  )
}

export function getSceneDoc(id: number) {
  return apiGet<SceneDoc & { ok: boolean; error?: string; summary?: string; facts?: { [key: string]: unknown } }>(
    `/extensions/ai_scene_reports/docs/${id}`,
  )
}

export function deleteSceneDoc(id: number) {
  return apiDelete<{ ok: boolean; id?: number; deleted?: boolean; error?: string }>(
    `/extensions/ai_scene_reports/docs/${id}`,
  )
}

export function previewSceneDoc(type: string, params: Record<string, unknown> = {}) {
  return apiGet<{
    ok: boolean
    error?: string
    title?: string
    facts?: { [key: string]: unknown }
    rule_summary?: string
    risks?: string[]
    suggestions?: string[]
    generated_at?: string
  }>('/extensions/ai_scene_reports/preview', { params: { type, ...params }, timeout: AI_TIMEOUT_MS })
}

// ── 第三批：会话重命名 / 知识库问答 / 预警筛选 ──────────────────────────────

export function renameAssistantConversation(id: number, title: string) {
  return apiPatch<{
    ok: boolean
    updated?: boolean
    found?: boolean
    id?: number
    title?: string
    error?: string
  }>(`/extensions/ai_assistant/conversations/${id}`, { title })
}

export type KnowledgeHit = {
  doc_id: number
  title: string
  seq: number
  score: number
  excerpt?: string
  text?: string
  scope?: string
}

export type KnowledgeSearchOut = {
  ok: boolean
  locked?: boolean
  error?: string
  query?: string
  mode?: string
  top_k?: number
  hits?: KnowledgeHit[]
  note?: string
  degrade_reason?: string
  searched_at?: string
}

export type KnowledgeAskOut = {
  ok: boolean
  locked?: boolean
  error?: string
  answered?: boolean
  mode?: string
  answer?: string
  hits?: KnowledgeHit[]
  ai_unavailable?: boolean
  ai_model?: string
  ai_disabled?: boolean
  ai_hint?: string
  note?: string
  tokens_in?: number | null
  tokens_out?: number | null
  asked_at?: string
  doc_id?: number | null
}

// docId 传了就只在这一篇里检索（资料页「问这篇」）；不传仍是全库检索
export function knowledgeSearch(query: string, topK = 5, docId?: number) {
  return apiPost<KnowledgeSearchOut>(
    '/extensions/ai_knowledge/search',
    { query, top_k: topK, ...(docId ? { doc_id: docId } : {}) },
    { timeout: AI_TIMEOUT_MS },
  )
}

export function knowledgeAsk(query: string, useLlm = true, topK = 5, docId?: number) {
  return apiPost<KnowledgeAskOut>(
    '/extensions/ai_knowledge/ask',
    { query, use_llm: useLlm, top_k: topK, ...(docId ? { doc_id: docId } : {}) },
    { timeout: AI_TIMEOUT_MS },
  )
}

export function getKnowledgeStatus() {
  return apiGet<{
    ok?: boolean
    enabled?: boolean
    docs?: number
    vectorized?: number
    chunks?: number
    vectorized_docs?: number
    mode_note?: string
    llm_note?: string
    degrade_reason?: string
  }>('/extensions/ai_knowledge/status')
}

// ── 第四批：扩展状态预检查 / 预警批量处置 ──────────────────────────────────

export type AiExtensionStatus = {
  key: string
  installed: boolean
  enabled: boolean
  granted: boolean
  permission: string
}

/** 智能中心首页一次性拿到各扩展「已安装 / 已启用 / 已授权」三态，避免逐页撞 403 */
export function getAiExtensionStatus() {
  return apiGet<{ items: AiExtensionStatus[]; installed_total: number }>('/h5/ai/extensions')
}

export type BatchHandleOut = {
  ok: boolean
  error?: string
  status?: string
  status_label?: string
  succeeded: number[]
  missing: number[]
  total: number
}

/** 批量处置预警（最多 50 条），不存在的 id 通过 missing 回传 */
export function batchHandleAlerts(ids: number[], status: string) {
  return apiPost<BatchHandleOut>('/extensions/ai_anomaly/alerts/batch-handle', { ids, status })
}

// ── 第六批：知识库个人留痕 / 洞察跑批删除 ──────────────────────────────────

export type KnowledgeLog = {
  id: number
  query_text: string
  mode?: string
  hit_count?: number
  scope?: string
  answered?: number
  ai_unavailable?: number
  ai_model?: string
  tokens_in?: number | null
  tokens_out?: number | null
  created_at?: string
}

export function listKnowledgeLogs(params: { mine?: number; page?: number; page_size?: number } = {}) {
  return apiGet<{
    items?: KnowledgeLog[]
    total?: number
    page?: number
    page_size?: number
    mine?: boolean
  }>('/extensions/ai_knowledge/logs', { params })
}

export function deleteInsightRun(id: number) {
  return apiDelete<{ ok: boolean; id?: number; deleted?: boolean; error?: string }>(
    `/extensions/ai_insight/runs/${id}`,
  )
}

// ── 第七批：知识库资料只读浏览 / 洞察批量清理 ──────────────────────────────

export type KnowledgeDocItem = {
  id: number
  title: string
  source?: string
  scope?: string
  role_allowed?: string
  chunk_count?: number
  vectorized?: number
  updated_at?: string
  content_len?: number
}

export function listKnowledgeDocs(
  params: {
    q?: string; scope?: string; page?: number; page_size?: number
    sort?: string; vectorized?: number
  } = {},
) {
  return apiGet<{ items?: KnowledgeDocItem[]; total?: number; page?: number; page_size?: number }>(
    '/extensions/ai_knowledge/docs',
    { params },
  )
}

export type KnowledgeDoc = {
  ok: boolean
  error?: string
  id: number
  title: string
  source?: string
  content?: string
  scope?: string
  role_allowed?: string
  chunk_count?: number
  vectorized?: number
  created_at?: string
  updated_at?: string
}

export function getKnowledgeDoc(id: number) {
  return apiGet<KnowledgeDoc>(`/extensions/ai_knowledge/docs/${id}`)
}

export function batchDeleteInsightRuns(ids: number[]) {
  return apiPost<{ ok: boolean; error?: string; total?: number; succeeded?: number[]; missing?: number[] }>(
    '/extensions/ai_insight/runs/batch-delete',
    { ids },
  )
}
