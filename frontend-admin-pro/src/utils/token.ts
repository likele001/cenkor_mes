// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { clearAuthToken, getAuthToken, setAuthToken } from '@/utils/session-token'

const KEY = 'cenkormes_admin_token'

export function getToken(): string | null {
  return getAuthToken(KEY)
}

export function setToken(token: string, remember = false) {
  setAuthToken(KEY, token, remember)
}

export function clearToken() {
  clearAuthToken(KEY)
}
