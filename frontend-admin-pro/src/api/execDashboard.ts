import { http } from '@/utils/http'

/* -------- 类型定义 -------- */

export type MetricOut = {
  value: number
  prev_value: number
  change_pct: number | null
  unit?: string
}

export type ExecSummaryOut = {
  period: string
  revenue: MetricOut
  profit_margin: MetricOut
  delivery_rate: MetricOut
  collection_rate: MetricOut
  capacity_utilization: MetricOut
}

export type TrendItem = {
  date: string
  amount: number
}

export type OrderStatusItem = {
  status: string
  count: number
}

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

/* -------- API -------- */

export const execDashboardApi = {
  summary(period = 'month') {
    return http.request<ExecSummaryOut>({
      url: '/admin/exec-dashboard/summary',
      method: 'GET',
      params: { period },
    })
  },

  revenueTrend(days = 30) {
    return http.request<TrendItem[]>({
      url: '/admin/exec-dashboard/revenue-trend',
      method: 'GET',
      params: { days },
    })
  },

  orderStatus() {
    return http.request<OrderStatusItem[]>({
      url: '/admin/exec-dashboard/order-status',
      method: 'GET',
    })
  },

  topCustomers(period = 'month', limit = 5) {
    return http.request<TopCustomerItem[]>({
      url: '/admin/exec-dashboard/top-customers',
      method: 'GET',
      params: { period, limit },
    })
  },

  topSkus(period = 'month', limit = 5) {
    return http.request<TopSkuItem[]>({
      url: '/admin/exec-dashboard/top-skus',
      method: 'GET',
      params: { period, limit },
    })
  },

  overdueOrders(limit = 10) {
    return http.request<OverdueOrderItem[]>({
      url: '/admin/exec-dashboard/overdue-orders',
      method: 'GET',
      params: { limit },
    })
  },
}
