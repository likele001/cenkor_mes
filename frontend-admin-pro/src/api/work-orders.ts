import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type WorkOrderOut = {
  id: number
  tenant_id: number
  order_id: number
  order_item_id: number
  product_id: number
  sku_id: number
  qty: number
  status: string
  created_at: string
  updated_at: string
  sku: {
    id: number
    code: string
    name: string
    product_id?: number
    product_name?: string
    sku_name?: string
    display_label?: string
  } | null
}

export type WorkOrderDetailOut = WorkOrderOut & {
  tasks: TaskOut[]
}

export type TaskAssignmentOut = {
  id: number
  user_id: number
  assigned_qty: number
  reported_qty?: number
  remaining_qty?: number
  assigned_at: string
  assigned_by: number | null
  user: { id: number; username: string; full_name: string | null } | null
}

/** 分工分配列表行（员工×任务） */
export type DispatchAssignmentOut = {
  id: number
  task_id: number
  task_code: string
  task_status: string
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
  user_id: number
  username: string | null
  user_full_name: string | null
  assigned_qty: number
  reported_qty: number
  remaining_qty: number
  progress: number
  status: string
  assigned_at: string
  assigned_by: number | null
}

export type TaskOut = {
  id: number
  tenant_id: number
  work_order_id: number
  process_id: number
  seq: number
  task_code: string
  planned_qty: number
  status: string
  assigned_user_id: number | null
  assigned_at: string | null
  assigned_by: number | null
  equipment_id?: number | null
  assignments?: TaskAssignmentOut[]
  assigned_total_qty?: number
  unassigned_qty?: number
  created_at: string
  updated_at: string
  process: { id: number; code: string; name: string } | null
  equipment?: { id: number; code: string; name: string; workshop: string | null; status: string } | null
  order?: {
    id: number
    code: string
    status: string
    customer_id: number
    customer_name: string | null
    customer_code: string | null
  } | null
  sku?: {
    id: number
    code: string
    name: string
    display_label?: string
    sku_display_name?: string
    product_name?: string
  } | null
  product?: { id: number; code: string; name: string; display_name?: string } | null
  work_order: {
    id: number
    order_id: number
    sku_id: number
    qty: number
    sku_display_label?: string | null
  } | null
}

export type UserOut = {
  id: number
  tenant_id: number
  department_id: number | null
  username: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  created_at: string
  roles: { id: number; code: string; name: string }[]
  department: { id: number; code: string; name: string } | null
}

export const workOrderApi = {
  // 工单
  listWorkOrders(params: any) {
    return http.request<ListResp<WorkOrderOut>>({ url: '/admin/production/work-orders', method: 'GET', params })
  },
  getWorkOrder(id: number) {
    return http.request<WorkOrderDetailOut>({ url: `/admin/production/work-orders/${id}`, method: 'GET' })
  },
  printProductLabels(workOrderId: number, params?: { piece_no_from?: number; piece_no_to?: number }) {
    return http.request<{ html: string; count: number; work_order_id: number }>({
      url: `/admin/production/work-orders/${workOrderId}/print-product-labels`,
      method: 'GET',
      params,
    })
  },

  // 任务
  listTasks(params: any) {
    return http.request<ListResp<TaskOut>>({ url: '/admin/production/tasks', method: 'GET', params })
  },
  assignTask(taskId: number, data: { assigned_user_id: number | null; equipment_id?: number | null }) {
    return http.request<TaskOut>({ url: `/admin/production/tasks/${taskId}/assign`, method: 'POST', data })
  },
  getTaskAssignments(taskId: number) {
    return http.request<{
      task_id: number
      planned_qty: number
      assigned_total_qty: number
      items: TaskAssignmentOut[]
    }>({ url: `/admin/production/tasks/${taskId}/assignments`, method: 'GET' })
  },
  setTaskAssignments(
    taskId: number,
    data: { items: { user_id: number; assigned_qty: number }[]; equipment_id?: number | null },
  ) {
    return http.request<TaskOut>({ url: `/admin/production/tasks/${taskId}/assignments`, method: 'PUT', data })
  },
  listDispatchAssignments(params?: {
    keyword?: string
    order_id?: number
    user_id?: number
    process_id?: number
    offset?: number
    limit?: number
  }) {
    return http.request<{ items: DispatchAssignmentOut[]; total: number }>({
      url: '/admin/production/assignments',
      method: 'GET',
      params,
    })
  },
  getDispatchAssignmentQr(assignmentId: number) {
    return http.request<{ task_code: string; text: string; report_url: string; svg: string }>({
      url: `/admin/production/assignments/${assignmentId}/qr`,
      method: 'GET',
    })
  },
  deleteDispatchAssignment(assignmentId: number) {
    return http.request<void>({ url: `/admin/production/assignments/${assignmentId}`, method: 'DELETE' })
  },
  renderTaskLabel(taskId: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ html: string; task_id: number; task_code: string; template_id: number }>({
      url: `/admin/production/tasks/${taskId}/print-label`,
      method: 'GET',
      params,
    })
  },
  exportTaskLabelPdf(taskId: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ attachment_id: number; filename: string; url: string }>({
      url: `/admin/production/tasks/${taskId}/print-label-pdf`,
      method: 'GET',
      params,
    })
  },
  renderTaskLabelBatch(data: { task_ids: number[]; template_id?: number; template_code?: string }) {
    return http.request<{ html: string; count: number; template_id: number }>({
      url: '/admin/production/tasks/print-label-batch',
      method: 'POST',
      data,
    })
  },
  listDispatchSkills(params?: any) {
    return http.request<ListResp<{ id: number; code: string; name: string }>>({ url: '/admin/production/tasks/dispatch-skills', method: 'GET', params })
  },
  listDispatchUsers(params: any) {
    return http.request<ListResp<UserOut>>({ url: '/admin/production/tasks/dispatch-users', method: 'GET', params })
  },

  // 用户（派工用）
  listUsers(params: any) {
    return http.request<ListResp<UserOut>>({ url: '/admin/system/users', method: 'GET', params })
  },
}
