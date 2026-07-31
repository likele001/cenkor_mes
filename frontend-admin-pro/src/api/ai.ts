import { http } from '@/utils/http'

export type PlanScheduleOut = {
  reply: string
  dispatch_hints: string[]
  overload_warnings: string[]
  suggest_start_date: string
  suggest_end_date: string
  suggest_mode: string
}

export type PlanOptimizeOut = {
  solver: string
  suggest_start_date: string
  suggest_end_date: string
  suggest_work_days: number
  total_minutes: number
  notes: string[]
  ok: boolean
  text: string
  suggestions: unknown[]
}

export type PlanForecastOut = {
  due_risk: string
  due_date: string
  days_left: number
  remaining_tasks: number
  avg_daily_output_7d: number
  kitting_ok: boolean
  shortage_count: number
}

export type PlanApsStrategyItem = {
  key: string
  title: string
  score: number
  pros: string[]
  cons: string[]
}

export type AuditSummaryOut = {
  summary: string
  anomaly_count: number
  ai_suggestions: string[]
  conversation_id?: number
  reply?: string
  pending_count?: number
  high_risk_ids?: number[]
  risk_points?: string[]
  suggest_actions?: string[]
}

export const aiApi = {
  listModels: () => http.request<any>({ url: '/ai/models', method: 'GET' }),
  listConversations: (kind: string) => http.request<any>({ url: '/ai/conversations', method: 'GET', params: { kind } }),
  deleteConversation: (id: number) => http.request<void>({ url: `/ai/conversations/${id}`, method: 'DELETE' }),
  runAlerts: () => http.request<any>({ url: '/ai/alerts/run', method: 'POST' }),
  listAlerts: () => http.request<any>({ url: '/ai/alerts', method: 'GET' }),
  getAiBrief: () => http.request<any>({ url: '/ai/brief', method: 'GET' }),
  getAlertSettings: () => http.request<any>({ url: '/ai/alert-settings', method: 'GET' }),
  saveAlertSettings: (data: unknown) => http.request<any>({ url: '/ai/alert-settings', method: 'PUT', data }),
  chatStream: (data: unknown, onDelta?: (delta: string) => void) => http.request<any>({ url: '/ai/chat', method: 'POST', data }),
  planScheduleSuggest: (planId: number) => http.request<any>({ url: `/ai/plan/${planId}/schedule-suggest`, method: 'GET' }),
  planScheduleOptimize: (planId: number) => http.request<any>({ url: `/ai/plan/${planId}/schedule-optimize`, method: 'GET' }),
  planScheduleApply: (planId: number, data: unknown) => http.request<void>({ url: `/ai/plan/${planId}/schedule-apply`, method: 'POST', data }),
  getPlanForecast: (planId: number) => http.request<any>({ url: `/ai/plan/${planId}/forecast`, method: 'GET' }),
  getPlanApsStrategy: (planId: number) => http.request<any>({ url: `/ai/plan/${planId}/aps-strategy`, method: 'GET' }),
  planAnalyze: (planId: number) => http.request<any>({ url: `/ai/plan/${planId}/analyze`, method: 'POST' }),
  getGatewaySettings: () => http.request<any>({ url: '/ai/gateway-settings', method: 'GET' }),
  saveGatewaySettings: (data: unknown) => http.request<void>({ url: '/ai/gateway-settings', method: 'PUT', data }),
  getPromptSettings: () => http.request<any>({ url: '/ai/prompt-settings', method: 'GET' }),
  savePromptSettings: (data: unknown) => http.request<void>({ url: '/ai/prompt-settings', method: 'PUT', data }),
  auditSummary: (status: string) => http.request<any>({ url: '/ai/audit/summary', method: 'GET', params: { status } }),
  reportVision: (id: number) => http.request<any>({ url: `/ai/report-units/${id}/vision`, method: 'POST' }),
}
