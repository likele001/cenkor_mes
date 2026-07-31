import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type EquipmentOut = {
  id: number
  code: string
  name: string
  model: string | null
  workshop: string | null
  status: string
  last_maintenance_date: string | null
  next_maintenance_date: string | null
  created_at: string
}

export type EquipmentMaintenancePlanOut = {
  id: number
  equipment_id: number
  plan_type: string
  check_items: string | null
  interval_days: number | null
  responsible_user_id: number | null
  next_date: string | null
  remark: string | null
  created_at: string
  updated_at: string
}

export type EquipmentMaintenanceLogOut = {
  id: number
  plan_id: number | null
  equipment_id: number
  check_result: string
  description: string | null
  attachments: string | null
  checked_by: number | null
  created_at: string
}

export const equipmentApi = {
  list(params?: { status?: string }) {
    return http.request<ListResp<EquipmentOut>>({ url: '/admin/equipment', method: 'GET', params })
  },
  create(data: { code?: string; name: string; model?: string; workshop?: string; remark?: string }) {
    return http.request<EquipmentOut>({ url: '/admin/equipment', method: 'POST', data })
  },
  update(
    equipmentId: number,
    data: {
      code?: string
      name?: string
      model?: string
      workshop?: string
      status?: string
      last_maintenance_date?: string | null
      next_maintenance_date?: string | null
      maintenance_interval_days?: number | null
      remark?: string
    },
  ) {
    return http.request<EquipmentOut>({ url: `/admin/equipment/${equipmentId}`, method: 'PUT', data })
  },
  check(equipmentId: number, params?: { check_type?: string; result?: string; description?: string }) {
    return http.request<void>({ url: `/admin/equipment/${equipmentId}/check`, method: 'POST', params })
  },
  listMaintenancePlans(params?: { equipment_id?: number }) {
    return http.request<ListResp<EquipmentMaintenancePlanOut>>({
      url: '/admin/equipment/maintenance-plans',
      method: 'GET',
      params,
    })
  },
  createMaintenancePlan(data: {
    equipment_id: number
    plan_type: string
    check_items?: string
    interval_days?: number
    responsible_user_id?: number
    next_date?: string
    remark?: string
  }) {
    return http.request<EquipmentMaintenancePlanOut>({
      url: '/admin/equipment/maintenance-plans',
      method: 'POST',
      data,
    })
  },
  updateMaintenancePlan(
    planId: number,
    data: {
      equipment_id?: number
      plan_type?: string
      check_items?: string
      interval_days?: number
      responsible_user_id?: number | null
      next_date?: string | null
      remark?: string
    },
  ) {
    return http.request<void>({ url: `/admin/equipment/maintenance-plans/${planId}`, method: 'PUT', data })
  },
  deleteMaintenancePlan(planId: number) {
    return http.request<void>({ url: `/admin/equipment/maintenance-plans/${planId}`, method: 'DELETE' })
  },
  listMaintenanceLogs(params?: { equipment_id?: number }) {
    return http.request<ListResp<EquipmentMaintenanceLogOut>>({
      url: '/admin/equipment/maintenance-logs',
      method: 'GET',
      params,
    })
  },
  createMaintenanceLog(data: {
    equipment_id: number
    plan_id?: number
    check_result: string
    description?: string
  }) {
    return http.request<EquipmentMaintenanceLogOut>({
      url: '/admin/equipment/maintenance-logs',
      method: 'POST',
      data,
    })
  },

  exportEquipment(params?: any) {
    return http.downloadBlob({ url: '/admin/equipment/export', method: 'GET', params })
  },
}
