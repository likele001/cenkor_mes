/** 部署后旧 tab 仍引用已删除的 lazy chunk 时，自动刷新一次加载新版本 */

const RELOAD_KEY = 'cenkormes_h5_chunk_reload'
const COOLDOWN_MS = 15_000

const CHUNK_ERROR_RE =
  /Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk [\d]+ failed|error loading dynamically imported module|MIME type.*text\/html/i

export function isChunkLoadError(reason: unknown): boolean {
  if (!reason) return false
  const parts: string[] = []
  if (reason instanceof Error) {
    parts.push(reason.message)
    if (reason.stack) parts.push(reason.stack)
  } else {
    parts.push(String(reason))
  }
  return CHUNK_ERROR_RE.test(parts.join('\n'))
}

export function reloadForStaleChunk(storageKey = RELOAD_KEY): boolean {
  try {
    const now = Date.now()
    const last = Number(sessionStorage.getItem(storageKey) || 0)
    if (now - last < COOLDOWN_MS) return false
    sessionStorage.setItem(storageKey, String(now))
  } catch {
    /* sessionStorage 不可用时仍尝试刷新 */
  }
  window.location.reload()
  return true
}

export function tryRecoverStaleChunk(reason: unknown, storageKey = RELOAD_KEY): boolean {
  if (!isChunkLoadError(reason)) return false
  return reloadForStaleChunk(storageKey)
}

export function installChunkReloadHandlers(storageKey = RELOAD_KEY): void {
  window.addEventListener('unhandledrejection', (event) => {
    if (tryRecoverStaleChunk(event.reason, storageKey)) {
      event.preventDefault()
    }
  })
}
