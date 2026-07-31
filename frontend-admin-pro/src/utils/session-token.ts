const REMEMBER_PREF_KEY = 'cenkormes_remember_login'

export function loadRememberPreference(): boolean {
  return localStorage.getItem(REMEMBER_PREF_KEY) === '1'
}

export function saveRememberPreference(remember: boolean) {
  localStorage.setItem(REMEMBER_PREF_KEY, remember ? '1' : '0')
}

function modeKey(tokenKey: string) {
  return `${tokenKey}_storage_mode`
}

/** 记住登录 → localStorage（7天）；否则 sessionStorage（关浏览器失效，且 token 8 小时过期） */
export function setAuthToken(tokenKey: string, token: string, remember: boolean) {
  sessionStorage.removeItem(tokenKey)
  localStorage.removeItem(tokenKey)
  const store = remember ? localStorage : sessionStorage
  store.setItem(tokenKey, token)
  localStorage.setItem(modeKey(tokenKey), remember ? 'local' : 'session')
}

export function getAuthToken(tokenKey: string): string | null {
  const mode = localStorage.getItem(modeKey(tokenKey)) || 'session'
  const store = mode === 'local' ? localStorage : sessionStorage
  return store.getItem(tokenKey)
}

export function clearAuthToken(tokenKey: string) {
  sessionStorage.removeItem(tokenKey)
  localStorage.removeItem(tokenKey)
  localStorage.removeItem(modeKey(tokenKey))
}
