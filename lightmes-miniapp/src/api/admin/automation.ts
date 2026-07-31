import { apiGet, request } from '../request'

const AI_TIMEOUT_MS = 120_000

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
    mode: 'rule' | 'llm'
  }
  alerts: {
    notify_on_scan: boolean
    create_todo_on_critical: boolean
  }
}

export type AutomationLogOut = {
  id: number
  trigger: string
  action: string
  status: string
  message: string | null
  created_at: string
}

export const automationAdminApi = {
  getSettings() {
    return apiGet<AutomationSettings>('/admin/automation/settings', undefined, true)
  },
  saveSettings(data: Partial<AutomationSettings>) {
    return request<AutomationSettings>('/admin/automation/settings', {
      method: 'PUT',
      data,
      admin: true,
    })
  },
  listLogs(params?: { limit?: number; offset?: number }) {
    return apiGet<{ items: AutomationLogOut[]; total: number }>('/admin/automation/logs', params, true)
  },
  dryRun(data: { order_id?: number; plan_id?: number; allow_shortage?: boolean }) {
    return request<{ ok: boolean; checks: Array<{ level: string; message: string }> }>(
      '/admin/automation/dry-run',
      { method: 'POST', data, admin: true, timeout: AI_TIMEOUT_MS },
    )
  },
}
