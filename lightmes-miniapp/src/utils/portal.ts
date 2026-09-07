// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
export const ADMIN_PORTAL_HEADER = 'X-CenkorMES-Portal'
export const ADMIN_PORTAL_VALUE = 'admin'

export function adminHeaders(): Record<string, string> {
  return { [ADMIN_PORTAL_HEADER]: ADMIN_PORTAL_VALUE }
}
