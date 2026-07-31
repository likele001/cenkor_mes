import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type KanbanCustomerOut = { id: number; code: string; name: string }

export type KanbanOrderOut = {
  id: number
  code: string
  status: string
  due_date: string | null
  due_days: number | null
  warning_level: string
  total_qty: number
  done_qty: number
  progress: number | null
  customer: KanbanCustomerOut | null
  created_at: string
  updated_at: string
}

export type KanbanSkuOut = { id: number; code: string; name: string }
export type KanbanProcessOut = { id: number; code: string; name: string }

export type KanbanTaskOut = {
  id: number
  task_code: string
  seq: number
  process: KanbanProcessOut | null
  planned_qty: number
  done_qty: number
  progress: number | null
  status: string
  assigned_user_id: number | null
  assigned_at: string | null
}

export type KanbanWorkOrderOut = {
  id: number
  order_item_id: number
  product_id: number
  sku: KanbanSkuOut | null
  qty: number
  done_qty: number
  progress: number | null
  status: string
  tasks: KanbanTaskOut[]
}

export type KanbanOrderItemOut = {
  id: number
  line_no: number
  sku: KanbanSkuOut | null
  qty: number
  remark: string | null
}

export type KanbanOrderDetailOut = {
  id: number
  code: string
  status: string
  due_date: string | null
  due_days: number | null
  warning_level: string
  remark: string | null
  customer_id: number
  customer: KanbanCustomerOut | null
  total_qty: number
  done_qty: number
  progress: number | null
  created_at: string
  updated_at: string
  items: KanbanOrderItemOut[]
  work_orders: KanbanWorkOrderOut[]
}

export const kanbanApi = {
  listOrders(params: {
    status?: string
    customer_id?: number
    due_from?: string
    due_to?: string
    offset?: number
    limit?: number
  }) {
    return http.request<ListResp<KanbanOrderOut>>({ url: '/dashboard/kanban/orders', method: 'GET', params })
  },
  getOrder(id: number) {
    return http.request<KanbanOrderDetailOut>({ url: `/dashboard/kanban/orders/${id}`, method: 'GET' })
  },
}
