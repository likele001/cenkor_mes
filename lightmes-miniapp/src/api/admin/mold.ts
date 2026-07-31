import { apiGet, apiPost, apiPut, apiDel } from '@/api/request'

export type MoldOut = {
  id: number
  code: string
  name: string
  model: string | null
  mold_type: string
  workshop: string | null
  status: string
  sku_id: number | null
  sku_code: string | null
  sku_name: string | null
  expected_lifespan: number | null
  current_shots: number
  purchase_date: string | null
  last_maintenance_date: string | null
  next_maintenance_date: string | null
  maintenance_interval_shots: number | null
  remark: string | null
  created_at: string
  updated_at: string
}

export type MoldMaintenanceLog = {
  id: number
  maintenance_type: string
  description: string | null
  shots_at_maintenance: number | null
  checked_by: number
  created_at: string
}

export type ProcessBinding = {
  id: number
  process_id: number
  process_name: string | null
}

export const MOLD_TYPES: Record<string, string> = {
  injection: '注塑', die_casting: '压铸', stamping: '冲压',
}

export const MOLD_STATUS_LABELS: Record<string, string> = {
  active: '正常', repair: '维修中', retired: '已退役',
}

export function lifePercent(m: MoldOut): number {
  if (!m.expected_lifespan || m.expected_lifespan <= 0) return 0
  return Math.round((m.current_shots / m.expected_lifespan) * 100)
}

export function lifeTag(pct: number): string {
  if (pct >= 95) return 'danger'
  if (pct >= 80) return 'warning'
  return 'success'
}

const BASE = '/admin/mold'

export const moldApi = {
  list(params?: { mold_type?: string; status?: string }) {
    return apiGet<{ items: MoldOut[] }>(BASE, params as Record<string, unknown>, true)
  },
  create(data: Record<string, unknown>) {
    return apiPost<{ id: number; code: string; name: string }>(BASE, data, true)
  },
  get(id: number) {
    return apiGet<MoldOut>(`${BASE}/${id}`, undefined, true)
  },
  update(id: number, data: Record<string, unknown>) {
    return apiPut<MoldOut>(`${BASE}/${id}`, data, true)
  },
  delete(id: number) {
    return apiDel<{ deleted: boolean }>(`${BASE}/${id}`, true)
  },
  listMaintenanceLogs(moldId: number, params?: { offset?: number; limit?: number }) {
    return apiGet<{ items: MoldMaintenanceLog[] }>(`${BASE}/${moldId}/maintenance-logs`, params as Record<string, unknown>, true)
  },
  createMaintenanceLog(moldId: number, data: { maintenance_type: string; description?: string }) {
    return apiPost<{ id: number; maintenance_type: string }>(`${BASE}/${moldId}/maintenance-logs`, data, true)
  },
  listProcessBindings(moldId: number) {
    return apiGet<{ items: ProcessBinding[] }>(`${BASE}/${moldId}/process-bindings`, undefined, true)
  },
  setProcessBindings(moldId: number, process_ids: number[]) {
    return apiPut<{ count: number }>(`${BASE}/${moldId}/process-bindings`, { process_ids }, true)
  },
}
