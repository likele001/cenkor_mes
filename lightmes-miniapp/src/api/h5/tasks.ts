import { apiGet, apiPostQuery } from '../request'

export interface H5Sku {
  id: number
  code: string
  name: string
  color?: string | null
  material?: string | null
  spec?: string | null
  display_label?: string | null
}

export interface H5Task {
  id: number
  task_code: string
  status: string
  seq?: number
  planned_qty?: number
  assigned_qty?: number
  reported_qty?: number
  remaining_qty?: number
  progress_pct?: number
  use_unit_report?: boolean
  report_mode?: string
  process?: { code: string; name: string } | null
  work_order?: {
    order_id?: number
    order_code?: string | null
    qty?: number
    product?: { id: number; code: string; name: string } | null
    sku?: H5Sku | null
  } | null
  flow?: {
    is_first_process?: boolean
    auto_bind_piece?: boolean
    prev_process_name?: string | null
    report_mode?: string
  }
}

export interface H5SalaryItem {
  id: number
  process_id: number
  process_name?: string | null
  unit_price: number
  good_qty: number
  amount: number
  month: string
}

export function getMyTasks(params?: { status?: string; offset?: number; limit?: number }) {
  return apiGet<{ items: H5Task[] }>('/h5/tasks', params as Record<string, unknown>)
}

export function getTaskDetail(taskCode: string) {
  return apiGet<H5Task>(`/h5/tasks/${encodeURIComponent(taskCode)}`)
}

export function getTaskQr(taskCode: string) {
  return apiGet<{ svg: string; report_url: string }>(`/h5/tasks/${encodeURIComponent(taskCode)}/qr`)
}

export function submitReport(params: {
  task_code: string
  good_qty: number
  bad_qty?: number
  remark?: string
  attachment_ids?: string
}) {
  return apiPostQuery<{ id: number; status: string }>('/h5/reports', params as Record<string, unknown>)
}

export function getDashboardSummary() {
  return apiGet<Record<string, unknown>>('/h5/dashboard/summary')
}

export function getMyReports(params?: { offset?: number; limit?: number }) {
  return apiGet<{ items: unknown[] }>('/h5/reports', params as Record<string, unknown>)
}
