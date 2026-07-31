import axios, { type AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { showToast } from 'vant'

export type ApiResp<T> = {
  code: number
  msg: string
  data: T
}

export class ApiError extends Error {
  code: number

  constructor(code: number, msg: string) {
    super(msg)
    this.code = code
  }
}

import { clearAuthToken, getAuthToken } from '@/utils/session-token'

const TOKEN_KEY = 'cenkormes_token'

function getToken() {
  return getAuthToken(TOKEN_KEY) || ''
}

export function clearToken() {
  clearAuthToken(TOKEN_KEY)
}

export const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = {
      ...(config.headers as any),
      Authorization: `Bearer ${token}`,
      token,
    } as any
  }
  return config
})

http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && typeof body.code === 'number') {
      if (body.code === 200) return body.data
      const msg = body.msg || '请求失败'
      showToast(msg)
      return Promise.reject(new ApiError(body.code, msg))
    }
    return body
  },
  (error: AxiosError) => {
    const msg = (error.response?.data as any)?.msg || error.message || '网络错误'
    showToast(msg)
    return Promise.reject(error)
  },
)

export function apiGet<T>(url: string, config?: AxiosRequestConfig) {
  return http.get<any, T>(url, config)
}

export function apiPost<T>(url: string, data?: any, config?: AxiosRequestConfig) {
  return http.post<any, T>(url, data, config)
}

export function apiPut<T>(url: string, data?: any, config?: AxiosRequestConfig) {
  return http.put<any, T>(url, data, config)
}

export function apiPostForm<T>(url: string, form: FormData, config?: AxiosRequestConfig) {
  return http.post<any, T>(url, form, {
    ...(config || {}),
    headers: { ...(config?.headers || {}), 'Content-Type': 'multipart/form-data' },
  })
}
