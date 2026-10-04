// 独立版构建期短路：除非显式开启 VITE_ENABLE_AI=1，否则 aiApi 为安全空实现。
// 这样 vite 会把整个 ai.ts tree-shake 掉，主入口 chunk 不再出现 /ai/* 路径。
const AI_ENABLED = (import.meta.env.VITE_ENABLE_AI === '1')
const _disabled = <T>(fallback?: T): Promise<T> => Promise.resolve((fallback ?? null) as T)
const _disabledVoid: Promise<void> = Promise.resolve()

// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
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

const _aiApiEnabled = {
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
  auditSummary: (status: string) => http.request<any>({ url: '/ai/audit/summary', method: 'GET', params: { status } }),
  reportVision: (id: number) => http.request<any>({ url: `/ai/report-units/${id}/vision`, method: 'POST' }),
}


// 独立版默认关闭 AI：所有 aiApi 方法返回安全空值
const _aiApiDisabled: Record<string, (...args: any[]) => Promise<any>> = {
  listModels: () => _disabled({ items: [] }),
  listConversations: () => _disabled({ items: [] }),
  deleteConversation: () => _disabledVoid,
  runAlerts: () => _disabled({ events: 0, notified: 0 }),
  listAlerts: () => _disabled({ items: [] }),
  getAiBrief: () => _disabled({ mode: null, content: null }),
  getAlertSettings: () => _disabled({ items: [] }),
  saveAlertSettings: () => _disabled({ ok: true }),
  chatStream: () => _disabled({ reply: '' }),
  planScheduleSuggest: () => _disabled({ dispatch_hints: [] }),
  planScheduleOptimize: () => _disabled({ ok: false }),
  planScheduleApply: () => _disabledVoid,
  getPlanForecast: () => _disabled({ due_risk: 'low' }),
  getPlanApsStrategy: () => _disabled({ items: [] }),
  planAnalyze: () => _disabled({ ok: false }),
  auditSummary: () => _disabled({ summary: '', anomaly_count: 0, ai_suggestions: [] }),
  reportVision: () => _disabled({ text: '', anomaly_count: 0 }),
}
export const aiApi = AI_ENABLED ? (_aiApiEnabled as any) : (_aiApiDisabled as any)
