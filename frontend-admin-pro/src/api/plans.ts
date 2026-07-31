import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type PlanOut = {
  id: number
  tenant_id: number
  order_id: number
  code: string
  status: string
  start_date: string | null
  end_date: string | null
  work_days: number | null
  remark: string | null
  created_by: number
  released_at?: string | null
  released_by?: number | null
  order_status?: string
  can_release?: boolean
  has_work_orders?: boolean
  created_at: string
  updated_at: string
  order_code: string | null
  customer_name: string | null
  qty: number
  /** 保存后是否已入队 Celery 自动化流水线 */
  pipeline_queued?: boolean
}

export type PlanOrderOption = {
  id: number
  code: string
  customer_id: number
  customer_name: string | null
  due_date: string | null
  qty: number
  remark: string | null
}

export type PlanCreateIn = {
  order_id: number
  code: string
  status?: string
  start_date?: string | null
  end_date?: string | null
  work_days?: number | null
  remark?: string | null
}

export type PlanUpdateIn = Partial<PlanCreateIn>

export type PlanReadinessKittingOut = {
  items: {
    material_id: number
    material_code: string
    material_name: string
    unit?: string | null
    spec?: string | null
    supplier_id?: number | null
    sku_id?: number | null
    demand_qty: number
    stock_qty: number
    shortage_qty: number
  }[]
  missing_boms: { sku_id: number; sku_code: string; sku_name: string }[]
  shortage_count: number
  missing_bom_count: number
  ok: boolean
}

export type PlanReadinessProcessOut = {
  missing_routes: { product_id: number; product_code: string; product_name: string }[]
  missing_prices: {
    sku_id: number
    sku_code: string
    sku_name: string
    product_id: number
    process_id: number
    process_code: string
    process_name: string
  }[]
  missing_route_count: number
  missing_price_count: number
  ok: boolean
}

export type PlanReadinessOut = {
  plan_id: number | null
  plan_code: string | null
  order_id: number
  order_code: string
  customer_name: string | null
  kitting: PlanReadinessKittingOut
  process: PlanReadinessProcessOut
  ready: boolean
  blockers: string[]
}

export type PlanLoadItemOut = { date: string; count: number; overload: boolean; capacity: number; is_workday: boolean }

export type PlanLoadDetailItemOut = {
  id: number
  code: string
  order_id: number
  status: string
  start_date: string | null
  end_date: string | null
  work_days: number | null
  remark: string | null
  qty: number
  total_minutes: number
  daily_minutes: number
  purchase_received_qty: number
  purchase_total_qty: number
}

export type PlanLoadWorkshopOut = {
  workshop: string
  minutes: number
  capacity: number
  overload: boolean
}

export type PlanLoadUserOut = {
  user_id: number
  name: string
  minutes: number
  capacity: number
  overload: boolean
}

export type PlanLoadEquipmentOut = {
  equipment_id: number
  name: string
  minutes: number
  capacity: number
  overload: boolean
}

export type PlanCalendarDayOut = {
  day: string
  is_workday: boolean
  capacity_minutes: number | null
  remark: string | null
}

export type PlanWorkshopCapacityOut = { workshop: string; capacity_minutes: number }
export type PlanUserCapacityOut = { user_id: number; capacity_minutes: number }
export type PlanEquipmentCapacityOut = { equipment_id: number; capacity_minutes: number }

export const plansApi = {
  getPlanFormOptions(params?: { keyword?: string }) {
    return http.request<{ orders: PlanOrderOption[] }>({
      url: '/admin/plans/meta/form-options',
      method: 'GET',
      params,
    })
  },
  listPlans(params: any) {
    return http.request<ListResp<PlanOut>>({ url: '/admin/plans', method: 'GET', params })
  },
  getPlan(id: number) {
    return http.request<PlanOut>({ url: `/admin/plans/${id}`, method: 'GET' })
  },
  previewPlanReadiness(orderId: number) {
    return http.request<PlanReadinessOut>({
      url: '/admin/plans/readiness/preview',
      method: 'GET',
      params: { order_id: orderId },
    })
  },
  getPlanReadiness(planId: number) {
    return http.request<PlanReadinessOut>({ url: `/admin/plans/${planId}/readiness`, method: 'GET' })
  },
  createPlan(data: PlanCreateIn) {
    return http.request<PlanOut>({ url: '/admin/plans', method: 'POST', data })
  },
  updatePlan(id: number, data: PlanUpdateIn) {
    return http.request<PlanOut>({ url: `/admin/plans/${id}`, method: 'PUT', data })
  },
  releasePlan(id: number, data?: { allow_shortage?: boolean }) {
    return http.request<{
      plan_id: number
      order_id: number
      order_status: string
      work_order_count: number
      task_count: number
    }>({ url: `/admin/plans/${id}/release`, method: 'POST', data: data || {} })
  },
  autoSchedule(id: number, params?: { mode?: 'backward' | 'forward' }) {
    return http.request<PlanOut>({ url: `/admin/plans/${id}/auto-schedule`, method: 'POST', params })
  },
  getCapacity() {
    return http.request<{ capacity: number; unit: 'pieces' | 'minutes'; unit_label: string }>({
      url: '/admin/plans/capacity',
      method: 'GET',
    })
  },
  setCapacity(capacity: number) {
    return http.request<{ capacity: number; unit: 'pieces' | 'minutes'; unit_label: string }>({
      url: '/admin/plans/capacity',
      method: 'PUT',
      params: { capacity },
    })
  },
  setCapacityUnit(unit: 'pieces' | 'minutes') {
    return http.request<{ capacity: number; unit: 'pieces' | 'minutes'; unit_label: string }>({
      url: '/admin/plans/capacity/unit',
      method: 'PUT',
      params: { unit },
    })
  },
  load(params: { date_from: string; date_to: string; capacity?: number | null }) {
    return http.request<{ items: PlanLoadItemOut[]; capacity: number; metric: string; default_workdays?: number[] }>({
      url: '/admin/plans/load',
      method: 'GET',
      params,
    })
  },
  loadDetail(params: { day: string }) {
    return http.request<{
      day: string
      items: PlanLoadDetailItemOut[]
      metric: string
      is_workday?: boolean
      capacity?: number
      workshops?: PlanLoadWorkshopOut[]
      users?: PlanLoadUserOut[]
      equipments?: PlanLoadEquipmentOut[]
    }>({
      url: '/admin/plans/load/detail',
      method: 'GET',
      params,
    })
  },
  getWorkshopCapacities() {
    return http.request<{ items: PlanWorkshopCapacityOut[]; default_capacity: number }>({ url: '/admin/plans/capacity/workshops', method: 'GET' })
  },
  setWorkshopCapacities(items: PlanWorkshopCapacityOut[]) {
    return http.request<{ items: PlanWorkshopCapacityOut[] }>({ url: '/admin/plans/capacity/workshops', method: 'PUT', data: { items } })
  },
  getUserCapacities() {
    return http.request<{ items: PlanUserCapacityOut[]; default_capacity: number }>({ url: '/admin/plans/capacity/users', method: 'GET' })
  },
  getUserCapacityRows() {
    return http.request<{
      items: { user_id: number; name: string; capacity_minutes: number }[]
      default_capacity: number
      unit: string
    }>({ url: '/admin/plans/capacity/user-rows', method: 'GET' })
  },
  setUserCapacities(items: PlanUserCapacityOut[]) {
    return http.request<{ items: PlanUserCapacityOut[] }>({ url: '/admin/plans/capacity/users', method: 'PUT', data: { items } })
  },
  getEquipmentCapacities() {
    return http.request<{ items: PlanEquipmentCapacityOut[]; default_capacity: number }>({
      url: '/admin/plans/capacity/equipments',
      method: 'GET',
    })
  },
  setEquipmentCapacities(items: PlanEquipmentCapacityOut[]) {
    return http.request<{ items: PlanEquipmentCapacityOut[] }>({ url: '/admin/plans/capacity/equipments', method: 'PUT', data: { items } })
  },
  autoDispatch(planId: number, data?: { user_ids?: number[]; unassigned_only?: boolean }) {
    return http.request<{
      assigned_count: number
      task_count: number
      span_workdays: number
      users: any[]
      workshops: any[]
      overloads: any[]
    }>({ url: `/admin/plans/${planId}/auto-dispatch`, method: 'POST', data: data || {} })
  },
  listCalendar(params: { date_from: string; date_to: string }) {
    return http.request<{ items: PlanCalendarDayOut[]; default_workdays: number[]; default_capacity: number }>({
      url: '/admin/plans/calendar',
      method: 'GET',
      params,
    })
  },
  upsertCalendarDay(data: { day: string; is_workday: boolean; capacity_minutes?: number | null; remark?: string | null }) {
    return http.request<PlanCalendarDayOut>({ url: '/admin/plans/calendar/day', method: 'PUT', data })
  },
  deleteCalendarDay(day: string) {
    return http.request<{ deleted: boolean }>({ url: '/admin/plans/calendar/day', method: 'DELETE', params: { day } })
  },
}
