import { http } from '@/utils/http'
import type { ExportJobOut } from '@/api/production'

export type ProductionSummaryOut = {
  good_qty: number
  bad_qty: number
  total_qty: number
  yield_rate: number | null
  report_count: number
}

export type YieldSummaryOut = {
  yield_rate: number | null
  good_qty: number
  bad_qty: number
  total_qty: number
}

export type ProcessRankItemOut = {
  process_id: number
  process_name: string
  good_qty: number
  bad_qty: number
  total_qty: number
  yield_rate: number | null
}

export type DailyTrendItemOut = {
  date: string
  good_qty: number
  bad_qty: number
  total_qty: number
  yield_rate: number | null
}

export type DefectParetoItemOut = {
  defect_code: string
  defect_name: string
  severity: string
  count: number
  pct: number
  cumulative_pct: number
}

export type DefectParetoOut = {
  items: DefectParetoItemOut[]
  total: number
}

export const reportsApi = {
  production(params: { date_from?: string; date_to?: string }) {
    return http.request<ProductionSummaryOut>({ url: '/admin/reports/production', method: 'GET', params })
  },
  yield(params: { date_from?: string; date_to?: string }) {
    return http.request<YieldSummaryOut>({ url: '/admin/reports/yield', method: 'GET', params })
  },
  processRank(params: { date_from?: string; date_to?: string; limit?: number }) {
    return http.request<{ items: ProcessRankItemOut[] }>({ url: '/admin/reports/process-rank', method: 'GET', params })
  },
  dailyTrend(params: { date_from?: string; date_to?: string }) {
    return http.request<{ items: DailyTrendItemOut[] }>({ url: '/admin/reports/daily-trend', method: 'GET', params })
  },
  defectPareto(params: { date_from?: string; date_to?: string; limit?: number }) {
    return http.request<DefectParetoOut>({ url: '/admin/reports/defect-pareto', method: 'GET', params })
  },
  exportProductionExcel(params: { date_from?: string; date_to?: string }) {
    return http.request<ExportJobOut>({ url: '/admin/reports/export/production', method: 'POST', params })
  },
}

