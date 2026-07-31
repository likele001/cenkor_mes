import { apiGet, apiPost } from '../request'

export interface AttendanceRecord {
  id: number
  work_date: string
  check_in_at: string | null
  check_out_at: string | null
  remark: string | null
  minutes: number | null
}

export function checkIn() {
  return apiPost('/h5/attendance/check-in')
}

export function checkOut() {
  return apiPost('/h5/attendance/check-out')
}

export function getAttendanceRecords(params?: { offset?: number; limit?: number; month?: string }) {
  return apiGet<{ items: AttendanceRecord[] }>('/h5/attendance/records', params as Record<string, unknown>)
}
