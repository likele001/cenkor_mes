// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

/** 事件契约条目（静态） */
export interface EventCatalogEntry {
  phase: 'notify' | 'intercept'
  payload: Record<string, string>
}

/** 订阅关系条目（运行时） */
export interface EventSubscription {
  event_name: string
  key: string
  phase: 'notify' | 'intercept'
  timeout: number | null
  handler: string
  in_catalog: boolean
  extension_name: string
  enabled: boolean
}

/** 最近事件流记录 */
export interface DispatchRecord {
  seq: number
  occurred_at: string
  event_name: string
  ext_key: string
  phase: 'notify' | 'intercept'
  ok: boolean
  allowed: boolean | null
  elapsed_ms: number
  error: string
  reason: string
  tenant_id: number | null
  actor_id: number | null
  trace_id: string
}

/** 按 (事件, 扩展) 聚合的统计 */
export interface EventStat {
  event_name: string
  ext_key: string
  phase: 'notify' | 'intercept'
  total: number
  errors: number
  slow: number
  rejections: number
  last_at: string
}

export function getEventCatalog() {
  return http.get<{ items: Record<string, EventCatalogEntry> }>('/admin/extensions/events/catalog')
}

export function getEventSubscriptions() {
  return http.get<{ items: EventSubscription[] }>('/admin/extensions/events/subscriptions')
}

export function getRecentEvents(params?: {
  limit?: number
  phase?: 'notify' | 'intercept'
  event_name?: string
  ext_key?: string
}) {
  return http.get<{ items: DispatchRecord[] }>('/admin/extensions/events/recent', { params })
}

export function getEventStats() {
  return http.get<{ items: EventStat[] }>('/admin/extensions/events/stats')
}
