export function formatMoney(n: number | null | undefined): string {
  const v = Number(n ?? 0)
  return v.toFixed(2)
}

export function formatPercent(rate: number | null | undefined): string {
  if (rate == null) return '-'
  return `${(rate * 100).toFixed(1)}%`
}

export function formatDate(d: string | null | undefined): string {
  if (!d) return '-'
  return d.slice(0, 10)
}

export function statusLabel(map: Record<string, string>, s: string): string {
  return map[s] || s
}
