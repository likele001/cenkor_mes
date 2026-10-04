// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

export type PublicConfig = {
  company_name: string
  logo_url: string
  login_captcha_enabled: boolean
  session_expire_minutes: number
  remember_me_expire_minutes: number
}

export function fetchPublicConfig() {
  return http.request<PublicConfig>({ url: '/public-config', method: 'GET' })
}
