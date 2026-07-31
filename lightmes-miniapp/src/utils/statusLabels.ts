export const TASK_STATUS: Record<string, { text: string; tone: string }> = {
  pending: { text: '待开始', tone: 'warn' },
  working: { text: '进行中', tone: 'info' },
  done: { text: '已完成', tone: 'ok' },
}

export const REPORT_STATUS: Record<string, { text: string; tone: string }> = {
  submitted: { text: '待初审', tone: 'warn' },
  leader_approved: { text: '待终审', tone: 'info' },
  qc_approved: { text: '已审核', tone: 'ok' },
  rejected: { text: '已驳回', tone: 'danger' },
  draft: { text: '草稿', tone: 'muted' },
}

export function taskStatusLabel(status: string) {
  return TASK_STATUS[status] || { text: status, tone: 'muted' }
}

export function reportStatusLabel(status: string) {
  return REPORT_STATUS[status] || { text: status, tone: 'muted' }
}
