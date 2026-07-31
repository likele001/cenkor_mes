import type { KvRow } from '@/components/admin-ui/AdminKvGrid.vue'

/** 将 "a · b · c" 摘要拆成多行 KV（用于 CRUD 等仅有 listSub 的页面） */
export function splitSummaryToKv(summary: string, label = '摘要'): KvRow[] {
  const parts = summary
    .split('·')
    .map((s) => s.trim())
    .filter(Boolean)
  if (!parts.length) return [{ label, value: '—' }]
  if (parts.length === 1) return [{ label, value: parts[0] }]
  return parts.map((p, i) => ({ label: i === 0 ? label : `字段${i + 1}`, value: p }))
}
