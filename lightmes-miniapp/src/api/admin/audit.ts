import { apiGet, apiPost, apiPostQuery } from '../request'

export type AttachmentMeta = {
  id: number
  content_type: string
  original_filename: string
  size: number
  play_url: string
}

export type AuditRecord = {
  id: number
  auditor_id: number
  audit_level: string
  action: string
  attachment_ids: string | null
  reason: string | null
  created_at: string
}

export type ReportRow = {
  id: number
  task_id?: number
  good_qty: number
  bad_qty: number
  status: string
  remark?: string | null
  created_at?: string
  report_user?: { full_name?: string; username?: string } | null
  task?: { task_code?: string } | null
}

export type ReportUnitRow = {
  id: number
  task_id?: number
  unit_seq?: number
  status: string
  result_type?: string | null
  submitted_at?: string | null
  prescreen_level?: string | null
  prescreen_json?: string | null
  prescreen_at?: string | null
  remark?: string | null
  report_user?: { id?: number; full_name?: string; username?: string } | null
  task?: { id?: number; task_code?: string; process_id?: number; process_name?: string } | null
  product?: { id?: number; name?: string; code?: string } | null
  order?: { id?: number; code?: string } | null
  employee_attachments?: AttachmentMeta[]
  qc_attachments?: AttachmentMeta[]
  audits?: AuditRecord[]
}

export const auditAdminApi = {
  listReports: (p?: Record<string, unknown>) => apiGet<{ items: ReportRow[] }>('/admin/production/reports', p, true),
  getReport: (id: number) => apiGet<ReportRow & Record<string, unknown>>(`/admin/production/reports/${id}`, undefined, true),
  leaderApproveReport: (id: number) => apiPost(`/admin/production/reports/${id}/leader-approve`, {}, true),
  qcApproveReport: (id: number) => apiPost(`/admin/production/reports/${id}/qc-approve`, {}, true),
  rejectReport: (id: number, reason: string) => apiPostQuery(`/admin/production/reports/${id}/reject`, { reason }, true),
  listReportUnits: (p?: Record<string, unknown>) =>
    apiGet<{ items: ReportUnitRow[] }>('/admin/production/report-units', p, true),
  getReportUnit: (id: number) => apiGet<ReportUnitRow>(`/admin/production/report-units/${id}`, undefined, true),
  leaderApproveUnit: (id: number, data?: Record<string, unknown>) =>
    apiPost(`/admin/production/report-units/${id}/approve`, data || {}, true),
  qcApproveUnit: (id: number, data?: Record<string, unknown>) =>
    apiPost(`/admin/production/report-units/${id}/approve`, data || {}, true),
  rejectReportUnit: (id: number, reason: string) =>
    apiPostQuery(`/admin/production/report-units/${id}/reject`, { reason }, true),
}

export function reportStatusLabel(s: string) {
  const map: Record<string, string> = {
    draft: '未报工',
    submitted: '待初审',
    leader_approved: '待终审',
    qc_approved: '已通过',
    rejected: '已驳回',
  }
  return map[s] || s || '-'
}

export function prescreenLabel(level?: string | null) {
  const map: Record<string, string> = {
    green: '低风险',
    yellow: '关注',
    red: '高风险',
  }
  return level ? map[level] || level : ''
}

export function prescreenTagClass(level?: string | null) {
  if (level === 'red') return 'prescreen-red'
  if (level === 'yellow') return 'prescreen-yellow'
  if (level === 'green') return 'prescreen-green'
  return 'prescreen-none'
}
