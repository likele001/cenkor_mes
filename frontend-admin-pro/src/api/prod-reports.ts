import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type ReportOut = {
  id: number
  task_id: number
  report_user_id: number
  good_qty: number
  bad_qty: number
  remark: string | null
  attachment_ids: string | null
  status: string
  created_at: string
  updated_at: string
  report_user: { id: number; full_name: string } | null
  product?: { id: number; name: string; code: string } | null
  order?: { id: number; code: string } | null
  task: { id: number; task_code: string; process_id: number; process_name?: string | null } | null
}

export type ReportUnitOut = {
  id: number
  task_id: number
  task_assignment_id: number
  user_id: number
  unit_seq: number
  result_type: string | null
  employee_attachment_ids: string | null
  qc_attachment_ids: string | null
  remark: string | null
  status: string
  prescreen_level?: string | null
  prescreen_json?: string | null
  prescreen_at?: string | null
  submitted_at: string | null
  created_at: string
  updated_at: string
  task: { id: number; task_code: string; process_id: number; process_name?: string | null } | null
  report_user: { id: number; full_name: string } | null
  product?: { id: number; name: string; code: string } | null
  order?: { id: number; code: string } | null
}

export type AttachmentMetaOut = {
  id: number
  content_type?: string | null
  original_filename?: string | null
  size?: number
}

export type ReportUnitDetailOut = ReportUnitOut & {
  employee_attachments?: AttachmentMetaOut[]
  qc_attachments?: AttachmentMetaOut[]
  audits: {
    id: number
    auditor_id: number
    audit_level: string
    action: string
    attachment_ids: string | null
    reason: string | null
    created_at: string
  }[]
}

export const prodReportApi = {
  // 报工审核
  listReports(params: any) {
    return http.request<ListResp<ReportOut>>({ url: '/admin/production/reports', method: 'GET', params })
  },
  getReport(id: number) {
    return http.request<any>({ url: `/admin/production/reports/${id}`, method: 'GET' })
  },
  leaderApprove(id: number) {
    return http.request<any>({ url: `/admin/production/reports/${id}/leader-approve`, method: 'POST' })
  },
  qcApprove(id: number) {
    return http.request<any>({ url: `/admin/production/reports/${id}/qc-approve`, method: 'POST' })
  },
  rejectReport(id: number, reason?: string) {
    return http.request<any>({
      url: `/admin/production/reports/${id}/reject`,
      method: 'POST',
      params: { reason },
    })
  },

  listReportUnits(params: any) {
    return http.request<ListResp<ReportUnitOut>>({
      url: '/admin/production/report-units',
      method: 'GET',
      params,
    })
  },
  getReportUnit(id: number) {
    return http.request<ReportUnitDetailOut>({ url: `/admin/production/report-units/${id}`, method: 'GET' })
  },
  leaderApproveReportUnit(id: number) {
    return http.request<any>({ url: `/admin/production/report-units/${id}/leader-approve`, method: 'POST' })
  },
  qcApproveReportUnit(id: number, data: { qc_attachment_ids: string; inspection_results?: Array<{
    template_item_id: number; result: string; measured_value?: string | null; defect_code_id?: number | null; remark?: string | null
  }> }) {
    return http.request<any>({ url: `/admin/production/report-units/${id}/qc-approve`, method: 'POST', data })
  },
  /** 获取该任务工序的质检检查项 */
  getInspectionForm(processId: number) {
    return http.request<{
      items: Array<{
        id: number
        seq: number
        item_name: string
        item_type: string
        standard_value: string | null
        upper_limit: string | null
        lower_limit: string | null
        unit: string | null
        is_required: boolean
        remark: string | null
      }>
    }>({ url: '/admin/production/inspection-templates', method: 'GET', params: { process_id: processId } })
  },
  /** 获取缺陷代码列表 */
  listDefectCodes() {
    return http.request<{
      items: Array<{ id: number; code: string; name: string; severity: string }>
    }>({ url: '/admin/production/defect-codes', method: 'GET' })
  },
  rejectReportUnit(id: number, reason?: string) {
    return http.request<any>({
      url: `/admin/production/report-units/${id}/reject`,
      method: 'POST',
      params: { reason },
    })
  },
}
