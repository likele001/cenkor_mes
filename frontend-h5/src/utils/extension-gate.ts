// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { showDialog } from 'vant'

/** 付费扩展未开通（后端返回 code=403 且提示“未启用”） */
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
    title: '需要开通扩展',
    message: `「${name}」为付费扩展，请在应用市场的扩展应用中开通后再使用。`,
    confirmButtonText: '知道了',
  })
}

export function handleExtensionLocked(e: unknown, name: string): boolean {
  if (!isExtensionLocked(e)) return false
  showExtensionLocked(name)
  return true
}
