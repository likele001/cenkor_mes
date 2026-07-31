import { apiGet } from '../request'

export type KanbanOrder = {
  id: number
  code: string
  status: string
  due_date?: string | null
  due_days?: number | null
  warning_level?: string
  total_qty?: number
  done_qty?: number
  progress?: number | null
  customer?: { id: number; code: string; name: string } | null
}

export type KanbanOrderDetail = KanbanOrder & {
  remark?: string | null
  items?: { id: number; line_no?: number; qty: number; sku?: { code?: string; name?: string; display_label?: string } }[]
  work_orders?: {
    id: number
    qty: number
    done_qty?: number
    status: string
    sku?: { code?: string; name?: string; display_label?: string }
    tasks?: { id: number; task_code?: string; seq?: number; status: string; planned_qty?: number; done_qty?: number; process?: { name?: string } }[]
  }[]
}

export const dashboardAdminApi = {
  summary: () => apiGet<Record<string, unknown>>('/dashboard/summary', undefined, true),
  charts: (days = 7) => apiGet<{ daily_trend?: { date: string; good_qty: number; bad_qty: number; total_qty: number }[]; process_rank?: { process_name: string; good_qty: number; bad_qty: number }[] }>(
    '/dashboard/charts',
    { days },
    true,
  ),
  kanbanOrders: (p?: Record<string, unknown>) => apiGet<{ items: KanbanOrder[] }>('/dashboard/kanban/orders', p, true),
  kanbanOrder: (id: number) => apiGet<KanbanOrderDetail>(`/dashboard/kanban/orders/${id}`, undefined, true),
  purchaseStats: (p?: Record<string, unknown>) => apiGet<{ items: Record<string, unknown>[] }>('/admin/reports/purchase', p, true),
  crmOpportunityStats: (p?: Record<string, unknown>) =>
    apiGet<{ items: Record<string, unknown>[]; total_count?: number; total_amount?: number }>(
      '/admin/production/crm/opportunities/stats',
      p,
      true,
    ),
}
