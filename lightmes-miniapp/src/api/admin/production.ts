import { apiDel, apiGet, apiPost, apiPut } from '../request'

export type TaskOut = {
  id: number
  task_code?: string
  work_order_id?: number
  seq?: number
  planned_qty: number
  status: string
  assigned_total_qty?: number
  equipment_id?: number | null
  assigned_at?: string | null
  process?: { code?: string; name?: string; display_name?: string }
  order?: { id: number; code: string; customer_name?: string | null } | null
  sku?: { id: number; code: string; name: string; display_label?: string; display_name?: string } | null
  product?: { id: number; code: string; name: string; display_name?: string } | null
  work_order?: { id: number; order_id?: number; sku_display_label?: string | null }
  assignments?: { user_id: number; assigned_qty: number; reported_qty?: number; user?: { id: number; username: string; full_name?: string } }[]
}

export type DispatchAssignment = {
  id: number
  task_id: number
  task_code: string
  order_code?: string | null
  product_name?: string | null
  sku_name?: string | null
  display_label?: string | null
  process_name?: string | null
  user_id: number
  username?: string
  user_full_name?: string | null
  assigned_qty: number
  reported_qty?: number
  remaining_qty?: number
  status: string
  assigned_at?: string
}

export const productionAdminApi = {
  listTasks: (p?: Record<string, unknown>) => apiGet<{ items: TaskOut[] }>('/admin/production/tasks', p, true),
  getTaskAssignments: (taskId: number) =>
    apiGet<{
      task_id: number
      planned_qty: number
      assigned_total_qty: number
      items: { user_id: number; assigned_qty: number; reported_qty?: number; user?: { id: number; username: string; full_name?: string } }[]
    }>(`/admin/production/tasks/${taskId}/assignments`, undefined, true),
  setTaskAssignments: (taskId: number, data: { items: { user_id: number; assigned_qty: number }[]; equipment_id?: number | null }) =>
    apiPut<TaskOut>(`/admin/production/tasks/${taskId}/assignments`, data, true),
  listDispatchUsers: (p?: Record<string, unknown>) =>
    apiGet<{ items: { id: number; username: string; full_name?: string }[] }>('/admin/production/tasks/dispatch-users', p, true),
  listDispatchSkills: () => apiGet<{ items: { id: number; code: string; name: string }[] }>('/admin/production/tasks/dispatch-skills', undefined, true),
  listDispatchAssignments: (p?: Record<string, unknown>) =>
    apiGet<{ items: DispatchAssignment[]; total: number }>('/admin/production/assignments', p, true),
  getDispatchAssignmentQr: (assignmentId: number) =>
    apiGet<{ task_code: string; text: string; report_url: string; svg?: string }>(
      `/admin/production/assignments/${assignmentId}/qr`,
      undefined,
      true,
    ),
  deleteDispatchAssignment: (assignmentId: number) => apiDel(`/admin/production/assignments/${assignmentId}`, true),
  listEquipment: () => apiGet<{ items: { id: number; code: string; name: string }[] }>('/admin/equipment', { limit: 200 }, true),
  getWorkOrder: (id: number) => apiGet<Record<string, unknown>>(`/admin/production/work-orders/${id}`, undefined, true),
  listSalarySlips: (p?: Record<string, unknown>) =>
    apiGet<{ items: { id: number; user_id: number; month: string; total_amount?: number; confirmed_at?: string | null; user_full_name?: string; username?: string }[] }>(
      '/admin/production/reports/salary/slips',
      p,
      true,
    ),
  resetSalarySlipConfirm: (id: number) => apiPost(`/admin/production/reports/salary/slips/${id}/reset-confirm`, {}, true),
  traceList: (p?: Record<string, unknown>) => apiGet<{ items: { id: number; code: string; product_code?: string; order_id: number; qty: number; created_at: string }[] }>('/admin/trace', p, true),
  traceQuery: (code: string) => apiGet<Record<string, unknown>>(`/admin/trace/${encodeURIComponent(code)}`, undefined, true),
}
