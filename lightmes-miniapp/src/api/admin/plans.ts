import { apiGet, apiPost, apiPut, apiPutQuery } from '../request'

export type PlanOut = {
  id: number
  order_id: number
  code: string
  status: string
  start_date?: string | null
  end_date?: string | null
  work_days?: number | null
  remark?: string | null
  can_release?: boolean
  order_code?: string | null
  customer_name?: string | null
  qty?: number
  done_qty?: number
  progress?: number
  pipeline_queued?: boolean
}

export const plansAdminApi = {
  list: (p?: Record<string, unknown>) => apiGet<{ items: PlanOut[] }>('/admin/plans', p, true),
  get: (id: number) => apiGet<PlanOut>(`/admin/plans/${id}`, undefined, true),
  formOptions: () =>
    apiGet<{
      orders: { id: number; code: string; customer_name?: string; qty?: number; due_date?: string }[]
    }>('/admin/plans/meta/form-options', undefined, true),
  create: (data: object) => apiPost<PlanOut>('/admin/plans', data, true),
  update: (id: number, data: object) => apiPut<PlanOut>(`/admin/plans/${id}`, data, true),
  release: (id: number, allowShortage = false) =>
    apiPost<{ work_order_count?: number; task_count?: number }>(
      `/admin/plans/${id}/release`,
      { allow_shortage: allowShortage },
      true,
    ),
  autoSchedule: (id: number, mode: 'backward' | 'forward' = 'backward') =>
    apiPost<PlanOut>(`/admin/plans/${id}/auto-schedule?mode=${mode}`, {}, true),
  readiness: (planId: number) =>
    apiGet<{
      ready?: boolean
      blockers?: string[]
      kitting?: { items?: { material_code?: string; material_name?: string; demand_qty: number; stock_qty: number; shortage_qty: number }[] }
      process?: {
        missing_routes?: { product_code?: string; product_name?: string }[]
        missing_prices?: { sku_name?: string; process_name?: string }[]
      }
    }>(`/admin/plans/${planId}/readiness`, undefined, true),
  getCapacity: () =>
    apiGet<{ capacity: number; unit: 'pieces' | 'minutes'; unit_label: string }>('/admin/plans/capacity', undefined, true),
  setCapacity: (capacity: number) =>
    apiPutQuery<{ capacity: number; unit: 'pieces' | 'minutes'; unit_label: string }>(
      '/admin/plans/capacity',
      { capacity },
      true,
    ),
  setCapacityUnit: (unit: 'pieces' | 'minutes') =>
    apiPutQuery<{ capacity: number; unit: 'pieces' | 'minutes'; unit_label: string }>(
      '/admin/plans/capacity/unit',
      { unit },
      true,
    ),
  getUserCapacities: () =>
    apiGet<{ items: { user_id: number; capacity_minutes: number }[]; default_capacity: number; unit: string }>(
      '/admin/plans/capacity/users',
      undefined,
      true,
    ),
  getUserCapacityRows: () =>
    apiGet<{
      items: { user_id: number; name: string; capacity_minutes: number }[]
      default_capacity: number
      unit: string
    }>('/admin/plans/capacity/user-rows', undefined, true),
  setUserCapacities: (items: { user_id: number; capacity_minutes: number }[]) =>
    apiPut<{ items: { user_id: number; capacity_minutes: number }[] }>(
      '/admin/plans/capacity/users',
      { items },
      true,
    ),
  getWorkshopCapacities: () =>
    apiGet<{ items: { workshop: string; capacity_minutes: number }[]; default_capacity: number; unit: string }>(
      '/admin/plans/capacity/workshops',
      undefined,
      true,
    ),
  setWorkshopCapacities: (items: { workshop: string; capacity_minutes: number }[]) =>
    apiPut<{ items: { workshop: string; capacity_minutes: number }[] }>(
      '/admin/plans/capacity/workshops',
      { items },
      true,
    ),
}
