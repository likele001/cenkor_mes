const PENDING_TRACE_KEY = 'cenkormes_pending_trace_code'

/** 从启动参数解析溯源码（仅认 code 或 trace: 前缀 / scene 内 code=） */
export function parseTraceCodeFromLaunch(query?: Record<string, string | undefined>): string {
  if (!query) return ''
  const code = String(query.code || '').trim()
  if (code) return code

  const scene = query.scene ? decodeURIComponent(String(query.scene)).trim() : ''
  if (!scene) return ''
  if (scene.startsWith('trace:')) return scene.slice(6).trim()

  const m = scene.match(/(?:^|&)code=([^&]+)/)
  return m?.[1] ? decodeURIComponent(m[1]).trim() : ''
}

export function stashPendingTraceCode(code: string) {
  if (!code) return
  uni.setStorageSync(PENDING_TRACE_KEY, code)
}

export function consumePendingTraceCode(): string {
  const code = String(uni.getStorageSync(PENDING_TRACE_KEY) || '').trim()
  if (code) uni.removeStorageSync(PENDING_TRACE_KEY)
  return code
}

/** 须在首屏 onShow 之后调用，避免 appLaunch with non-empty page stack */
export function navigateToTracePage(code: string) {
  const c = String(code || '').trim()
  if (!c) return
  const url = `/pages/shared/trace/index?code=${encodeURIComponent(c)}`
  setTimeout(() => {
    uni.reLaunch({ url })
  }, 50)
}
