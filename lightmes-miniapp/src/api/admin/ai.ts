import { apiGet, request } from '../request'

const AI_TIMEOUT_MS = 120_000

export type PlanScheduleOut = {
  reply?: string
  suggest_start_date?: string | null
  suggest_end_date?: string | null
  suggest_work_days?: number | null
  dispatch_hints?: string[]
  overload_warnings?: string[]
}

export type PlanOptimizeOut = {
  ok?: boolean
  solver?: string
  suggest_start_date?: string | null
  suggest_end_date?: string | null
  suggest_work_days?: number | null
  total_minutes?: number
  notes?: string[]
  error?: string
}

export type AuditSummaryOut = {
  summary?: string
  reply?: string
  risk_points?: string[]
  suggest_actions?: string[]
  pending_count?: number
}

export type AlertItem = {
  id: number
  level: string
  title: string
  summary?: string
  created_at?: string
}

export type AlertSettingsOut = {
  pending_audit: number
  yield_drop_delta: number
  pending_tasks: number
  unassigned_sample_min: number
}

export type AiBriefOut = {
  mode: string
  content: string
  data?: Record<string, unknown>
}

export type PlanForecastOut = {
  plan_id: number
  order_id: number
  due_date: string | null
  days_left: number | null
  due_risk: 'green' | 'yellow' | 'red' | string
  remaining_tasks: number
  avg_daily_output_7d: number
  kitting_ok: boolean
  shortage_count: number
  notes?: string[]
}

export type PlanApsStrategyItem = {
  key: string
  title: string
  score: number
  pros?: string[]
  cons?: string[]
  enabled?: boolean
  suggest_start?: string | null
  suggest_end?: string | null
  solver?: string
}

export type PlanApsStrategyOut = {
  plan_id: number
  forecast: PlanForecastOut
  strategies: PlanApsStrategyItem[]
  recommended: string
  llm_summary?: string | null
}

export const aiAdminApi = {
  planScheduleSuggest(planId: number) {
    return request<PlanScheduleOut>(`/admin/ai/plan/${planId}/schedule-suggest`, {
      method: 'POST',
      admin: true,
      timeout: AI_TIMEOUT_MS,
    })
  },
  planScheduleOptimize(planId: number) {
    return request<PlanOptimizeOut>(`/admin/ai/plan/${planId}/schedule-optimize`, {
      method: 'POST',
      admin: true,
      timeout: AI_TIMEOUT_MS,
    })
  },
  auditSummary(status = 'submitted') {
    return request<AuditSummaryOut>('/admin/ai/audit/summary', {
      method: 'POST',
      admin: true,
      timeout: AI_TIMEOUT_MS,
      params: { status },
    })
  },
  reportVision(unitId: number) {
    return request<Record<string, unknown>>(`/admin/ai/report-units/${unitId}/vision`, {
      method: 'POST',
      admin: true,
      timeout: AI_TIMEOUT_MS,
    })
  },
  listAlerts() {
    return apiGet<{ items: AlertItem[] }>('/admin/ai/alerts', undefined, true)
  },
  getAlertSettings() {
    return apiGet<AlertSettingsOut>('/admin/ai/alert-settings', undefined, true)
  },
  saveAlertSettings(data: Partial<AlertSettingsOut>) {
    return request<AlertSettingsOut>('/admin/ai/alert-settings', {
      method: 'PUT',
      data,
      admin: true,
    })
  },
  getGatewaySettings() {
    return apiGet<{
      enabled: boolean
      base_url: string
      api_key_configured: boolean
      api_key_masked: string
      model_id: string
      timeout_seconds: number
    }>('/admin/ai/gateway-settings', undefined, true)
  },
  saveGatewaySettings(data: {
    enabled?: boolean
    base_url?: string
    api_key?: string
    model_id?: string
    timeout_seconds?: number
  }) {
    return request<{
      enabled: boolean
      base_url: string
      api_key_configured: boolean
      api_key_masked: string
      model_id: string
      timeout_seconds: number
    }>('/admin/ai/gateway-settings', {
      method: 'PUT',
      data,
      admin: true,
    })
  },
  runAlerts() {
    return request<{ events: number; notified: number }>('/admin/ai/alerts/run', {
      method: 'POST',
      admin: true,
      timeout: AI_TIMEOUT_MS,
    })
  },
  planAnalyze(planId: number) {
    return request<{
      risk_level?: string
      summary?: string
      risks?: string[]
      suggestions?: string[]
      reply?: string
    }>(`/admin/ai/plan/${planId}/analyze`, {
      method: 'POST',
      admin: true,
      timeout: AI_TIMEOUT_MS,
    })
  },
  getAiBrief() {
    return request<AiBriefOut>('/admin/ai/brief', { method: 'GET', admin: true, timeout: AI_TIMEOUT_MS })
  },
  getPlanForecast(planId: number) {
    return apiGet<PlanForecastOut>(`/admin/plans/${planId}/forecast`, undefined, true)
  },
  getPlanApsStrategy(planId: number) {
    return request<PlanApsStrategyOut>(`/admin/plans/${planId}/aps-strategy`, {
      method: 'GET',
      admin: true,
      timeout: AI_TIMEOUT_MS,
    })
  },
  deepOverview() {
    return request<Record<string, unknown>>('/admin/ai/deep/overview', {
      method: 'GET',
      admin: true,
      timeout: AI_TIMEOUT_MS,
    })
  },
  stats(days = 30) {
    return apiGet<{
      total_calls: number
      tokens_in: number
      tokens_out: number
      by_scene: Array<{ scene: string; calls: number; tokens_in: number; tokens_out: number }>
      daily: Array<{ date: string; calls: number; tokens_in: number; tokens_out: number }>
    }>('/admin/ai/stats', { days }, true)
  },
  listModels() {
    return apiGet<{ items: Array<{ code: string; display_name: string; is_default: boolean }> }>(
      '/admin/ai/models',
      undefined,
      true,
    )
  },
  listConversations(scene = 'boss_qa') {
    return apiGet<{ items: Array<{ id: number; title: string | null; updated_at?: string }> }>(
      '/admin/ai/conversations',
      { scene },
      true,
    )
  },
  deleteConversation(id: number) {
    return request<{ ok: boolean }>(`/admin/ai/conversations/${id}`, { method: 'DELETE', admin: true })
  },
  getPromptSettings() {
    return apiGet<{ prompt: string; max_length: number }>('/admin/ai/prompt-settings', undefined, true)
  },
  savePromptSettings(data: { prompt?: string }) {
    return request<{ prompt: string; max_length: number }>('/admin/ai/prompt-settings', {
      method: 'PUT',
      data,
      admin: true,
    })
  },
  chat(data: { message: string; conversation_id?: number; model_code?: string; context_id?: number }) {
    return request<{ conversation_id: number; reply: string }>('/h5/ai/chat', {
      method: 'POST',
      data: { scene: 'boss_qa', ...data },
      admin: true,
      timeout: AI_TIMEOUT_MS,
    })
  },
}
