import { adminHeaders } from '@/utils/portal'

const TOKEN_KEY = 'cenkormes_token'

export type ApiResp<T> = { code: number; msg: string; data: T }

export class ApiError extends Error {
  code: number
  constructor(code: number, msg: string) {
    super(msg)
    this.code = code
  }
}

export function getToken(): string {
  try {
    return uni.getStorageSync(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setToken(token: string): void {
  uni.setStorageSync(TOKEN_KEY, token)
}

export function clearToken(): void {
  uni.removeStorageSync(TOKEN_KEY)
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: Record<string, unknown> | object
  params?: Record<string, unknown>
  admin?: boolean
  timeout?: number
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  let url = path.startsWith('http') ? path : `${base.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`
  if (params && Object.keys(params).length) {
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join('&')
    if (qs) url += (url.includes('?') ? '&' : '?') + qs
  }
  return url
}

export function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', data, params, admin = false, timeout = 30000 } = options
  const token = getToken()
  const header: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(admin ? adminHeaders() : {}),
  }

  const queryParams =
    method === 'GET'
      ? { ...params, ...(data as Record<string, unknown> | undefined) }
      : params

  return new Promise((resolve, reject) => {
    uni.request({
      url: buildUrl(path, queryParams as Record<string, unknown> | undefined),
      method,
      data: method !== 'GET' && data ? data : undefined,
      header,
      timeout,
      success(res) {
        const body = res.data as ApiResp<T> | T
        if (body && typeof body === 'object' && 'code' in body && typeof (body as ApiResp<T>).code === 'number') {
          const wrapped = body as ApiResp<T>
          if (wrapped.code === 200) {
            resolve(wrapped.data as T)
            return
          }
          if (wrapped.code === 401) {
            clearToken()
            uni.reLaunch({ url: '/pages/shared/login/index' })
            reject(new ApiError(401, wrapped.msg || '登录已过期'))
            return
          }
          uni.showToast({ title: wrapped.msg || '请求失败', icon: 'none' })
          reject(new ApiError(wrapped.code, wrapped.msg || '请求失败'))
          return
        }
        resolve(body as T)
      },
      fail(err) {
        const raw = err.errMsg || '网络错误'
        const msg = /timeout/i.test(raw) ? '请求超时，请检查网络、API 域名与后端是否可访问' : raw
        uni.showToast({ title: msg, icon: 'none', duration: 3000 })
        reject(new Error(msg))
      },
    })
  })
}

export const apiGet = <T>(path: string, params?: Record<string, unknown>, admin = false) =>
  request<T>(path, { method: 'GET', params, admin })

export const apiPost = <T>(path: string, data?: object, admin = false) =>
  request<T>(path, { method: 'POST', data, admin })

/** POST 且参数走 query（与 H5 报工等接口一致） */
export const apiPostQuery = <T>(path: string, params?: Record<string, unknown>, admin = false) =>
  request<T>(path, { method: 'POST', params, admin })

export const apiPut = <T>(path: string, data?: object, admin = false) =>
  request<T>(path, { method: 'PUT', data, admin })

export const apiPutQuery = <T>(path: string, params?: Record<string, unknown>, admin = false) =>
  request<T>(path, { method: 'PUT', params, admin })

export const apiDel = <T>(path: string, admin = false) => request<T>(path, { method: 'DELETE', admin })
