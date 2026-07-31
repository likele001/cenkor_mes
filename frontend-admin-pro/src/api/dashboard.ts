import { http } from '@/utils/http'

export type DashboardSummaryOut = {
  today: {
    date: string
    good_qty: number
    bad_qty: number
    total_qty: number
    yield_rate: number | null
    report_count: number
    salary_amount: number
  }
  orders: { total: number; confirmed: number }
  tasks: { total: number; pending: number; done: number }
  reports: { pending_audit: number }
}

export type DailyTrendItem = {
  date: string
  good_qty: number
  bad_qty: number
  total_qty: number
}

export type ProcessRankItem = {
  process_id: number
  process_name: string
  good_qty: number
  bad_qty: number
}

export type DashboardChartsOut = {
  daily_trend: DailyTrendItem[]
  process_rank: ProcessRankItem[]
}

export const dashboardApi = {
  summary() {
    return http.request<DashboardSummaryOut>({ url: '/dashboard/summary', method: 'GET' })
  },
  charts(days?: number) {
    return http.request<DashboardChartsOut>({ url: '/dashboard/charts', method: 'GET', params: { days } })
  },
}

