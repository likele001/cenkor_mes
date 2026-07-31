import { apiGet } from '../request'

export type ExecMetric = {
  value: number
  prev_value: number
  change_pct: number | null
  unit?: string
}

export type ExecSummary = {
  period: string
  revenue: ExecMetric
  profit_margin: ExecMetric
  delivery_rate: ExecMetric
  collection_rate: ExecMetric
  capacity_utilization: ExecMetric
}

export type TrendItem = { date: string; amount: number }

export type TopCustomerItem = {
  customer_id: number
  customer_name: string
  amount: number
  order_count: number
}

export type TopSkuItem = {
  sku_id: number
  sku_code: string
  sku_name: string
  quantity: number
  amount: number
}

export type OverdueOrderItem = {
  id: number
  code: string
  customer_name: string
  due_date: string
  days_overdue: number
  amount: number
}

export const execDashboardApi = {
  summary: (period = 'month') => apiGet<ExecSummary>('/admin/exec-dashboard/summary', { period }, true),
  revenueTrend: (days = 14) => apiGet<TrendItem[]>('/admin/exec-dashboard/revenue-trend', { days }, true),
  topCustomers: (period = 'month', limit = 5) =>
    apiGet<TopCustomerItem[]>('/admin/exec-dashboard/top-customers', { period, limit }, true),
  topSkus: (period = 'month', limit = 5) =>
    apiGet<TopSkuItem[]>('/admin/exec-dashboard/top-skus', { period, limit }, true),
  overdueOrders: (limit = 10) => apiGet<OverdueOrderItem[]>('/admin/exec-dashboard/overdue-orders', { limit }, true),
}
