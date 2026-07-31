import { getToken } from '@/utils/token'

export type DashboardWSMessage = { type: string; channel?: string }

/** 连接大屏 WebSocket；返回关闭函数。失败时 onFallback 会被调用。 */
export function connectDashboardWS(
  onRefresh: () => void,
  onFallback?: () => void,
): () => void {
  const token = getToken()
  if (!token) {
    onFallback?.()
    return () => {}
  }

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${window.location.host}/api/ws/dashboard?token=${encodeURIComponent(token)}`
  let ws: WebSocket | null = null
  let closed = false
  let fallbackCalled = false

  const callFallback = () => {
    if (!fallbackCalled) {
      fallbackCalled = true
      onFallback?.()
    }
  }

  try {
    ws = new WebSocket(url)
  } catch {
    callFallback()
    return () => {}
  }

  ws.onopen = () => {
    /* connected */
  }

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(String(ev.data)) as DashboardWSMessage
      if (msg.type === 'refresh') onRefresh()
    } catch {
      /* ignore */
    }
  }

  ws.onerror = () => callFallback()

  ws.onclose = () => {
    if (!closed) callFallback()
  }

  return () => {
    closed = true
    try {
      ws?.close()
    } catch {
      /* ignore */
    }
  }
}
