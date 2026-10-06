// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

export type AutomationSettings = {
  enabled: boolean
  on_order_confirm: {
    create_plan: boolean
    start_offset_days: number
    run_pipeline_after_create: boolean
  }
  on_plan_saved: {
    run_schedule: boolean
    engine: string
    auto_release: boolean
    auto_dispatch: boolean
    allow_shortage: boolean
  }
  audit: {
    prescreen_on_submit: boolean
    auto_leader_approve: boolean
    auto_qc_approve: boolean
    require_employee_photo: boolean
    vision_min_score: number
    block_if_prior_reject: boolean
  }
  briefing: {
    daily_enabled: boolean
    daily_hour: number
    mode: string
  }
  alerts: {
    notify_on_scan: boolean
    create_todo_on_critical: boolean
  }
}

export type AutomationCheck = { level: string; message: string }

export type AutomationDryRunOut = {
  ok: boolean
  checks: AutomationCheck[]
  readiness?: Record<string, unknown> | null
  plan_status?: string
}

export type AutomationLog = {
  id: number
  trigger: string
  action: string
  biz_type: string | null
  biz_id: number | null
  status: string
  message: string | null
  detail_json: string | null
  created_by: number | null
  created_at: string | null
}

export const automationApi = {
  getAutomationSettings: () =>
    http.request<AutomationSettings>({ url: '/admin/automation/settings', method: 'GET' }),
  saveAutomationSettings: (data: Partial<AutomationSettings>) =>
    http.request<AutomationSettings>({ url: '/admin/automation/settings', method: 'PUT', data }),
  dryRun: (data: { order_id?: number; plan_id?: number; allow_shortage?: boolean }) =>
    http.request<AutomationDryRunOut>({ url: '/admin/automation/dry-run', method: 'POST', data }),
  listLogs: (params?: {
    trigger?: string
    status?: string
    biz_type?: string
    biz_id?: number
    offset?: number
    limit?: number
  }) =>
    http.request<{ items: AutomationLog[] }>({ url: '/admin/automation/logs', method: 'GET', params }),
}
