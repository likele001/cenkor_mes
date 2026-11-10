// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { showDialog } from 'vant'
import { i18n } from '@/locales'

const t = i18n.global.t.bind(i18n.global) as (key: string, params?: Record<string, unknown>) => string

/** 付费扩展未开通（后端返回 code=403 且提示"未启用"） */
export function isExtensionLocked(e: unknown): boolean {
  const err = e as { code?: number; message?: string } | null
  return !!err && err.code === 403 && String(err.message || '').includes('未启用')
}

/** 403：扩展未开通，或当前账号未获得该扩展权限 */
export function isAccessDenied(e: unknown): boolean {
  return (e as { code?: number } | null)?.code === 403
}

export function showExtensionLocked(name: string): void {
  void showDialog({
    title: t('ai.needExtensionTitle'),
    message: t('ai.needExtensionMsg', { name }),
    confirmButtonText: t('ai.ok'),
  })
}

/** 403 但非"未开通"（角色没分配权限点）：给明确引导 */
export function showAccessDenied(): void {
  void showDialog({
    title: t('ai.needExtensionTitle'),
    message: t('ai.needPermission'),
    confirmButtonText: t('ai.ok'),
  })
}

export function handleExtensionLocked(e: unknown, name: string): boolean {
  if (!isExtensionLocked(e)) return false
  showExtensionLocked(name)
  return true
}
