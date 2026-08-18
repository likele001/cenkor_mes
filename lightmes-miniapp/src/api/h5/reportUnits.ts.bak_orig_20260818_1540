import { apiGet, apiPost } from '../request'
import type { H5Task } from './tasks'

export interface ReportUnitItem {
  id: number
  unit_seq: number
  status: string
  result_type: string | null
  task_code?: string
  remark?: string | null
  product_code?: string
  unit_label?: string
  process_name?: string | null
  order_code?: string | null
  sku_label?: string | null
  submitted_at?: string | null
  created_at?: string | null
}

export function getTaskUnits(taskCode: string) {
  return apiGet<{
    task_code: string
    assigned_qty: number
    reported_qty: number
    remaining_qty: number
    task?: H5Task
    items: ReportUnitItem[]
    flow?: {
      is_first_process?: boolean
      auto_bind_piece?: boolean
      piece_pool_enabled?: boolean
      pool_available?: number
      pool_total?: number
      prev_process_name?: string | null
    }
  }>(`/h5/tasks/${encodeURIComponent(taskCode)}/units`)
}

export function submitReportUnit(data: {
  task_code: string
  unit_seq?: number
  result_type: 'good' | 'bad'
  attachment_ids: string
  remark?: string
}) {
  return apiPost<ReportUnitItem>('/h5/report-units', data)
}

export function getMyReportUnits(params?: { status?: string; offset?: number; limit?: number }) {
  return apiGet<{ items: ReportUnitItem[] }>('/h5/report-units', params as Record<string, unknown>)
}
