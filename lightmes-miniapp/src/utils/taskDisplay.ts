import type { H5Task } from '@/api/h5/tasks'

export function taskSkuTitle(task: H5Task): string {
  const sku = task.work_order?.sku
  if (sku?.display_label) return sku.display_label
  if (sku) return sku.name ? `${sku.code} - ${sku.name}` : sku.code
  return task.process?.name || task.task_code
}

export function taskOrderLabel(task: H5Task): string {
  const code = task.work_order?.order_code
  if (code) return code
  const oid = task.work_order?.order_id
  return oid ? `#${oid}` : '—'
}

export function formatMoney(v: number | string | null | undefined): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '0.00'
  return n.toFixed(2)
}

export function formatDateTime(raw: string | null | undefined): string {
  if (!raw) return '—'
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return String(raw)
  const pad = (x: number) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
