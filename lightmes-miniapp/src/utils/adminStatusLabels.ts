import { statusLabel } from '@/utils/format'

const ORDER_STATUS: Record<string, string> = {
  draft: '草稿',
  pending_confirm: '待审核',
  confirmed: '已确认',
  producing: '生产中',
  done: '已完成',
  shipped: '已发货',
  cancelled: '已取消',
}

const ORDER_TONE: Record<string, string> = {
  draft: 'tone-draft',
  pending_confirm: 'tone-pending',
  confirmed: 'tone-violet',
  producing: 'tone-active',
  done: 'tone-success',
  shipped: 'tone-success',
  cancelled: 'tone-danger',
}

export function adminOrderStatusLabel(s: string) {
  return statusLabel(ORDER_STATUS, s)
}

export function adminOrderStatusTone(s: string) {
  return ORDER_TONE[s] || 'tone-draft'
}

const REPORT_STATUS: Record<string, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
}

const REPORT_TONE: Record<string, string> = {
  pending: 'tone-pending',
  approved: 'tone-success',
  rejected: 'tone-danger',
}

export function adminReportStatusLabel(s: string) {
  return statusLabel(REPORT_STATUS, s)
}

export function adminReportStatusTone(s: string) {
  return REPORT_TONE[s] || 'tone-draft'
}
