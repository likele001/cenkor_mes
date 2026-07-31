import { http } from '@/utils/http'

export type AutomationSettings = {
  enabled: boolean
  auto_release: boolean
  auto_schedule: boolean
  schedule_window_days: number
  default_lead_time_hours: number
}

export const automationApi = {
  getAutomationSettings: () => http.request<any>({ url: '/automation/settings', method: 'GET' }),
}
