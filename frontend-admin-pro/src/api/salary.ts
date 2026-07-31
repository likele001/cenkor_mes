import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type SalaryItemOut = {
  id: number
  report_id: number | null
  user_id: number
  sku_id: number
  process_id: number
  unit_price: number
  good_qty: number
  amount: number
  month: string
  created_at: string
}

/** 工资明细台账（对标 thinkmes 工资列表） */
export type SalaryLedgerOut = {
  id: number
  source: 'unit' | 'report'
  salary_id: number | null
  report_unit_id: number | null
  report_id: number | null
  user_id: number
  username: string | null
  user_full_name: string | null
  order_id: number | null
  order_code: string | null
  product_id: number | null
  product_name: string | null
  sku_id: number | null
  sku_code: string | null
  sku_name: string | null
  process_id: number | null
  process_code: string | null
  process_name: string | null
  unit_seq: number | null
  reported_qty: number
  unit_price: number
  amount: number
  status: string
  status_label: string
  reported_at: string | null
  month: string
  task_code: string | null
  result_type: string | null
}

export type SalarySlipOut = {
  id: number
  user_id: number
  user_name: string | null
  month: string
  total_qty: number
  item_amount: number
  hourly_amount: number
  hourly_hours: number
  bonus_amount: number
  deduction_amount: number
  net_amount: number
  signature_attachment_id: number | null
  signed_at: string | null
  is_signed: boolean
  confirm_status?: string
  reject_reason?: string | null
  rejected_at?: string | null
}

export type HourlyItemOut = {
  id: number
  user_id: number
  user_name: string | null
  item_type: string
  work_date: string | null
  work_hours: number
  hourly_rate: number
  amount: number
  month: string
  is_absent: boolean
}

export type ExportJobOut = {
  id: number
  job_type: string
  status: string
  params: any
  result_attachment_id: number | null
  error_msg: string | null
  created_by: number | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export const salaryApi = {
  // 工资
  listSalaryLedger(params?: {
    month?: string
    user_id?: number
    status?: string
    keyword?: string
    offset?: number
    limit?: number
  }) {
    return http.request<{ items: SalaryLedgerOut[]; total: number }>({
      url: '/admin/production/reports/salary/ledger',
      method: 'GET',
      params,
    })
  },
  listSalaryItems(params: any) {
    return http.request<ListResp<SalaryItemOut>>({ url: '/admin/production/reports/salary/items', method: 'GET', params })
  },
  getSalarySummary(params: any) {
    return http.request<{ items: any[] }>({ url: '/admin/production/reports/salary/summary', method: 'GET', params })
  },
  listSalaryAllowances(params?: { user_id?: number; month?: string }) {
    return http.request<{ items: { id: number; user_id: number; allowance_type: string; amount: number; month: string; reason: string | null }[] }>({
      url: '/admin/production/reports/salary/allowances',
      method: 'GET',
      params,
    })
  },
  createSalaryAllowance(data: {
    user_id: number
    allowance_type: string
    amount: number
    month: string
    reason?: string
  }) {
    return http.request<{ id: number; allowance_type: string; amount: number }>({
      url: '/admin/production/reports/salary/allowances',
      method: 'POST',
      data,
    })
  },
  exportSalaryExcel(params: any) {
    return http.request<Blob>({ url: '/admin/production/reports/salary/export', method: 'GET', params, responseType: 'blob' })
  },
  createSalaryExportJob(params: any) {
    return http.request<ExportJobOut>({ url: '/admin/production/reports/salary/export-jobs', method: 'POST', params })
  },
  getSalaryExportJob(id: number) {
    return http.request<ExportJobOut>({ url: `/admin/production/reports/salary/export-jobs/${id}`, method: 'GET' })
  },
  listSalarySlips(params: any) {
    return http.request<ListResp<SalarySlipOut>>({ url: '/admin/production/reports/salary/slips', method: 'GET', params })
  },
  resetSalarySlipConfirm(id: number) {
    return http.request<any>({ url: `/admin/production/reports/salary/slips/${id}/reset-confirm`, method: 'POST' })
  },
  remindSalarySlips(month: string) {
    return http.request<{ month: string; sent: number; skipped: number }>({
      url: '/admin/production/reports/salary/slips/remind',
      method: 'POST',
      params: { month },
    })
  },

  // 计时工资
  listHourlyItems(params?: { month?: string; user_id?: number; offset?: number; limit?: number }) {
    return http.request<{ items: HourlyItemOut[]; total: number }>({
      url: '/admin/production/reports/salary/hourly-items',
      method: 'GET',
      params,
    })
  },
  generateTimeItems(params: { date_from: string; date_to?: string; user_id?: number }) {
    return http.request<{ generated: number; date_from: string; date_to: string }>({
      url: '/admin/production/reports/salary/generate-time-items',
      method: 'POST',
      params,
    })
  },
  getHourlySummary(params?: { month?: string; user_id?: number }) {
    return http.request<{ total_hours: number; total_amount: number }>({
      url: '/admin/production/reports/salary/hourly-summary',
      method: 'GET',
      params,
    })
  },
  listHourlyLedger(params?: { month?: string; user_id?: number; offset?: number; limit?: number }) {
    return http.request<{ items: any[]; total: number }>({
      url: '/admin/production/reports/salary/hourly-ledger',
      method: 'GET',
      params,
    })
  },
}
