import { apiGet, apiPost } from '@/utils/http'

export interface H5Task {
  id: number
  task_code: string
  work_order_id: number
  process_id: number
  seq: number
  planned_qty: number
  status: string
  assigned_user_id: number | null
  assigned_at: string | null
  assigned_by: number | null
  assigned_qty?: number
  reported_qty?: number
  remaining_qty?: number
  use_unit_report?: boolean
  report_mode?: 'batch' | 'unit' | 'lot'
  equipment_id: number | null
  equipment: {
    id: number
    code: string
    name: string
    workshop: string | null
    status: string | null
  } | null
  created_at: string
  updated_at: string
  process: { id: number; code: string; name: string } | null
  work_order: {
    id: number
    order_id: number
    qty: number
    sku: { id: number; code: string; name: string } | null
  } | null
}

export function getMyTasks(params?: { status?: string; offset?: number; limit?: number }) {
  return apiGet<{ items: H5Task[] }>('/h5/tasks', { params })
}

export function getTaskDetail(taskCode: string) {
  return apiGet<H5Task>(`/h5/tasks/${encodeURIComponent(taskCode)}`)
}

export interface TaskQrOut {
  task_code: string
  text: string
  report_url: string
  svg: string
}

export function getTaskQr(taskCode: string) {
  return apiGet<TaskQrOut>(`/h5/tasks/${encodeURIComponent(taskCode)}/qr`)
}

export interface SubmitReportResult {
  id: number
  status: string
  good_qty: number
  bad_qty: number
  created_at: string
}

export function submitReport(params: {
  task_code: string
  good_qty: number
  bad_qty?: number
  remark?: string
  attachment_ids?: string
}) {
  return apiPost<SubmitReportResult>('/h5/reports', null, { params })
}

export interface H5Report {
  id: number
  task_id: number
  good_qty: number
  bad_qty: number
  status: string
  created_at: string
}

export function getMyReports() {
  return apiGet<{ items: H5Report[] }>('/h5/reports')
}

export interface H5SalaryItem {
  id: number
  report_id: number
  process_id: number
  unit_price: number
  good_qty: number
  amount: number
  month: string
  created_at: string
}

export interface H5SalarySummary {
  user_id: number
  total_amount: number
  total_qty: number
  month: string
}

export function getMySalary(params?: { month?: string; offset?: number; limit?: number }) {
  return apiGet<{ items: H5SalaryItem[] }>('/h5/salary', { params })
}

export function getMySalarySummary(params?: { month?: string }) {
  return apiGet<{ items: H5SalarySummary[] }>('/h5/salary/summary', { params })
}

export interface H5SalarySlip {
  id: number
  user_id: number
  month: string
  total_qty: number
  item_amount: number
  bonus_amount: number
  deduction_amount: number
  net_amount: number
  signature_attachment_id: number | null
  signed_at: string | null
  is_signed: boolean
  confirm_status?: string
  reject_reason?: string | null
  rejected_at?: string | null
}

export function getMySalarySlip(params?: { month?: string }) {
  return apiGet<H5SalarySlip>('/h5/salary/slip', { params })
}

export function signMySalarySlip(params: { attachment_id: number; month?: string }) {
  return apiPost<{ id: number; month: string; signature_attachment_id: number; signed_at: string }>(
    '/h5/salary/slip/sign',
    null,
    { params },
  )
}

export function rejectMySalarySlip(params: { reason: string; month?: string }) {
  return apiPost<{ id: number; month: string; confirm_status: string; reject_reason: string; rejected_at: string }>(
    '/h5/salary/slip/reject',
    null,
    { params },
  )
}

export interface H5AttendanceRecord {
  id: number
  work_date: string
  check_in_at: string | null
  check_out_at: string | null
  check_in_lat?: number | null
  check_in_lng?: number | null
  check_out_lat?: number | null
  check_out_lng?: number | null
  remark: string | null
  minutes: number | null
}

export type AttendanceGeoPayload = { latitude?: number; longitude?: number }

export function getAttendanceGeofence() {
  return apiGet<{ enabled: boolean; lat?: number; lng?: number; radius_m?: number }>('/h5/attendance/geofence')
}

function readGeo(): Promise<AttendanceGeoPayload> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve({})
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      () => resolve({}),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
    )
  })
}

export async function checkIn() {
  const geo = await readGeo()
  return apiPost<H5AttendanceRecord>('/h5/attendance/check-in', geo)
}

export async function checkOut() {
  const geo = await readGeo()
  return apiPost<H5AttendanceRecord>('/h5/attendance/check-out', geo)
}

export function listMyAttendance(params?: { date_from?: string; date_to?: string; offset?: number; limit?: number }) {
  return apiGet<{ items: H5AttendanceRecord[] }>('/h5/attendance/records', { params })
}

export interface H5Notification {
  id: number
  title: string
  content: string
  level: string
  biz_type: string | null
  biz_id: number | null
  read_at: string | null
  created_at: string
}

export function listMyNotifications(params?: {
  unread?: boolean
  level?: string
  biz_type?: string
  offset?: number
  limit?: number
}) {
  return apiGet<{ items: H5Notification[] }>('/h5/notifications', { params })
}

export function markMyNotificationRead(notification_id: number) {
  return apiPost<{ updated: number }>('/h5/notifications/read', null, { params: { notification_id } })
}

export function markMyAllNotificationsRead() {
  return apiPost<{ updated: number }>('/h5/notifications/read-all')
}

export function getMyUnreadNotificationCount() {
  return apiGet<{ count: number }>('/h5/notifications/unread-count')
}

export interface H5DashboardSummary {
  today: {
    date: string
    good_qty: number
    bad_qty: number
    total_qty: number
    yield_rate: number | null
    salary_amount: number
  }
  my_tasks: {
    pending: number
    working: number
    total: number
  }
  month: {
    month: string
    report_count: number
    salary_amount: number
  }
}

export function getMyDashboardSummary() {
  return apiGet<H5DashboardSummary>('/h5/dashboard/summary')
}
