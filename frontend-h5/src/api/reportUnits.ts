import { apiGet, apiPost } from '@/utils/http'

export interface ReportUnitItem {
  id: number
  task_id: number
  task_assignment_id: number
  unit_seq: number
  piece_id?: number | null
  piece_no?: number | null
  product_code?: string | null
  unit_label?: string | null
  result_type: string | null
  employee_attachment_ids: string | null
  qc_attachment_ids: string | null
  remark: string | null
  status: string
  submitted_at: string | null
  created_at: string
  updated_at: string
  task_code?: string | null
}

export interface TaskFlowContext {
  is_first_process: boolean
  requires_parent_trace: boolean
  auto_bind_piece: boolean
  piece_pool_enabled?: boolean
  pool_total?: number
  pool_available?: number
  report_mode?: string
  prev_process_id: number | null
  prev_process_name: string | null
  current_task_seq: number
}

export interface TaskUnitsOut {
  task_code: string
  assigned_qty: number
  reported_qty: number
  remaining_qty: number
  flow?: TaskFlowContext
  items: ReportUnitItem[]
}

export function getTaskUnits(taskCode: string) {
  return apiGet<TaskUnitsOut>(`/h5/tasks/${encodeURIComponent(taskCode)}/units`)
}

export interface AnomalyWarning {
  anomaly_warning: true
  anomaly_level: 'suspect' | 'abnormal'
  anomaly_reason: string
  anomaly_detail: Record<string, unknown> | null
}

export type SubmitReportUnitResult = ReportUnitItem | AnomalyWarning

export function submitReportUnit(data: {
  task_code: string
  unit_seq?: number
  result_type: 'good' | 'bad'
  attachment_ids: string
  remark?: string
  anomaly_confirmed?: boolean
}) {
  return apiPost<SubmitReportUnitResult>('/h5/report-units', data)
}

export function getMyReportUnits(params?: { status?: string; offset?: number; limit?: number }) {
  return apiGet<{ items: ReportUnitItem[] }>('/h5/report-units', { params })
}

export function getReportUnitDetail(unitId: number) {
  return apiGet<ReportUnitItem & { audits?: unknown[] }>(`/h5/report-units/${unitId}`)
}
