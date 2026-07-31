/** 从扫码结果或粘贴文本解析任务码 */
export function parseTaskCodeFromScan(raw: string): string {
  const s = (raw || '').trim()
  if (!s) return ''
  try {
    const u = s.includes('://') ? new URL(s) : new URL(s, 'http://local')
    const q = u.searchParams.get('task_code')
    if (q) return decodeURIComponent(q).trim()
    const hash = u.hash || ''
    const m = hash.match(/[?&]task_code=([^&]+)/i)
    if (m) return decodeURIComponent(m[1]).trim()
  } catch {
    /* 非 URL */
  }
  const m2 = s.match(/task_code=([^&\s#]+)/i)
  if (m2) return decodeURIComponent(m2[1]).trim()
  return s
}
