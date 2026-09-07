// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
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
