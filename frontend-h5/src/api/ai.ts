import { apiGet, apiPost } from '@/utils/http'

const AI_TIMEOUT_MS = 120_000

export type AiHelpOut = {
  answer: string
  sources: Array<{ source: string; title: string; snippet?: string }>
}

export type AiChatOut = {
  conversation_id: number
  reply: string
}

export type AlertItem = {
  id: number
  level: string
  title: string
  summary?: string
}

export type AiBriefOut = {
  mode: string
  content: string
  data?: Record<string, unknown>
}

export function reportAiCheck(data: {
  task_id: number
  result_type: string
  remark?: string
  good_qty?: number
  bad_qty?: number
}) {
  return apiPost<{ ok: boolean; hints: string[]; suggest_remark?: string; reply?: string }>(
    '/h5/ai/report/check',
    data,
    { timeout: 60_000 },
  )
}

export function aiHelp(question: string) {
  return apiPost<AiHelpOut>('/h5/ai/help', { question }, { timeout: AI_TIMEOUT_MS })
}

export function aiChat(data: { message: string; conversation_id?: number; model_code?: string }) {
  return apiPost<AiChatOut>(
    '/h5/ai/chat',
    { scene: 'boss_qa', ...data },
    { timeout: AI_TIMEOUT_MS },
  )
}

export function getAiBrief() {
  return apiGet<AiBriefOut>('/h5/ai/brief', { timeout: AI_TIMEOUT_MS })
}

export function listAiAlerts() {
  return apiGet<{ items: AlertItem[] }>('/h5/ai/alerts', { timeout: 30_000 })
}

export function runAiAlerts() {
  return apiPost<{ events: number; notified: number }>('/h5/ai/alerts/run', undefined, { timeout: AI_TIMEOUT_MS })
}

export function listAiModels() {
  return apiGet<{ items: Array<{ code: string; display_name: string; is_default: boolean }> }>('/h5/ai/models')
}

export function listAiConversations(scene = 'boss_qa') {
  return apiGet<{ items: Array<{ id: number; title: string | null; updated_at: string }> }>(
    '/h5/ai/conversations',
    { params: { scene } },
  )
}

export function deleteAiConversation(id: number) {
  return apiPost<{ ok: boolean }>(`/h5/ai/conversations/${id}/delete`, {})
}

// =========================================================================
// AI 报工增强（Task 1 拍照计数 / Task 2 语音解析 / Task 4 缺陷分类 / Task 6 交接摘要 / Task 5 推荐）
// =========================================================================

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

/** 拍照自动计数（Task 1） */
export function photoAiCount(data: { image_urls: string[]; task_id?: number; hint?: string }) {
  return apiPost<PhotoCountOut>('/h5/ai/report/photo-count', data, { timeout: AI_TIMEOUT_MS })
}

/** 语音报工解析（Task 2） */
export function voiceParseReport(data: { text: string; task_id?: number }) {
  return apiPost<VoiceParseOut>('/h5/ai/report/voice-parse', data, { timeout: AI_TIMEOUT_MS })
}

/** AI 缺陷自动分类（Task 4） */
export function defectAiClassify(data: { image_urls: string[]; task_id?: number; remark?: string }) {
  return apiPost<DefectClassifyOut>('/h5/ai/report/defect-classify', data, { timeout: AI_TIMEOUT_MS })
}

/** 换班/交接 AI 摘要（Task 6） */
export function shiftAiSummary(data: { shift_start?: string; shift_hours?: number } = {}) {
  return apiPost<ShiftSummaryOut>('/h5/ai/report/shift-summary', data, { timeout: AI_TIMEOUT_MS })
}

/** 智能报工建议（Task 5） */
export function getTaskRecommend() {
  return apiGet<{ items: TaskRecommendItem[] }>('/h5/ai/report/recommend', { timeout: 10_000 })
}

/** 将 attachment id 转换为后端可访问的图片 URL（用于 AI 调用） */
export function attachmentIdToUrl(id: number, filename?: string): string {
  const name = filename ? `&filename=${encodeURIComponent(filename)}` : ''
  return `/api/files/${id}?download=true${name}`
}
