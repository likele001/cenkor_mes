import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type ShiftOut = {
  id: number
  code: string
  name: string
  start_time: string
  end_time: string
  rest_minutes: number
  shift_type: string
  status: string
  remark: string | null
  created_at: string
  updated_at: string
}

export type ShiftScheduleOut = {
  id: number
  user_id: number
  shift_id: number
  work_date: string
  remark: string | null
  created_at: string
  updated_at: string
  shift_name: string | null
  shift_code: string | null
  user_name: string | null
}

export const shiftApi = {
  listShifts(params?: { status?: string }) {
    return http.request<ListResp<ShiftOut>>({ url: '/admin/shift', method: 'GET', params })
  },
  createShift(data: {
    code?: string
    name: string
    start_time: string
    end_time: string
    rest_minutes?: number
    shift_type?: string
    remark?: string
  }) {
    return http.request<ShiftOut>({ url: '/admin/shift', method: 'POST', data })
  },
  updateShift(
    shiftId: number,
    data: {
      code?: string
      name?: string
      start_time?: string
      end_time?: string
      rest_minutes?: number
      shift_type?: string
      status?: string
      remark?: string
    },
  ) {
    return http.request<ShiftOut>({ url: `/admin/shift/${shiftId}`, method: 'PUT', data })
  },
  deleteShift(shiftId: number) {
    return http.request<void>({ url: `/admin/shift/${shiftId}`, method: 'DELETE' })
  },
  listSchedules(params?: { user_id?: number; work_date?: string; start_date?: string; end_date?: string }) {
    return http.request<ListResp<ShiftScheduleOut>>({ url: '/admin/shift/schedules', method: 'GET', params })
  },
  createSchedule(data: { user_id: number; shift_id: number; work_date: string; remark?: string }) {
    return http.request<ShiftScheduleOut>({ url: '/admin/shift/schedules', method: 'POST', data })
  },
  batchCreateSchedule(data: { user_ids: number[]; shift_id: number; start_date: string; end_date: string }) {
    return http.request<{ count: number }>({ url: '/admin/shift/schedules/batch', method: 'POST', data })
  },
  deleteSchedule(scheduleId: number) {
    return http.request<void>({ url: `/admin/shift/schedules/${scheduleId}`, method: 'DELETE' })
  },
}
