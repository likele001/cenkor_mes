import { apiGet, apiPostQuery } from '../request'

export function getSalarySummary(month?: string) {
  return apiGet<{ items: unknown[] }>('/h5/salary/summary', month ? { month } : undefined)
}

export function getSalary(month?: string) {
  return apiGet<{ items: import('./tasks').H5SalaryItem[] }>('/h5/salary', month ? { month } : undefined)
}

export function getSalarySlip(month?: string) {
  return apiGet<Record<string, unknown>>('/h5/salary/slip', month ? { month } : undefined)
}

export function signSalarySlip(month: string, attachmentId: number) {
  return apiPostQuery('/h5/salary/slip/sign', { month, attachment_id: attachmentId })
}

export function rejectSalarySlip(month: string, reason: string) {
  return apiPostQuery('/h5/salary/slip/reject', { month, reason })
}
