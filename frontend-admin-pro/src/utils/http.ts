import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResp } from '@/types/api'
import { i18n } from '@/locales'
import { getToken, clearToken } from '@/utils/token'

type BizError = Error & { bizCode?: number }

function isApiResp(x: unknown): x is ApiResp<unknown> {
  if (!x || typeof x !== 'object') return false
  const o = x as Record<string, unknown>
  return typeof o.code === 'number' && typeof o.msg === 'string' && 'data' in o
}

export class HttpClient {
  private ins: AxiosInstance

  constructor(baseURL: string) {
    this.ins = axios.create({
      baseURL,
      timeout: 20000,
      paramsSerializer: {
        serialize: (params) => {
          const cleaned = Object.fromEntries(
            Object.entries(params).filter(([_, v]) => v !== undefined && v !== null)
          )
          const searchParams = new URLSearchParams()
          for (const [k, v] of Object.entries(cleaned)) {
            if (Array.isArray(v)) {
              v.forEach((item) => searchParams.append(k, String(item)))
            } else {
              searchParams.append(k, String(v))
            }
          }
          return searchParams.toString()
        },
      },
    })

    this.ins.interceptors.request.use((config) => {
      const token = getToken()
      if (token) config.headers.set('Authorization', `Bearer ${token}`)
      else config.headers.delete('Authorization')
      if (config.data instanceof FormData) {
        config.headers.delete('Content-Type')
      }
      return config
    })

    this.ins.interceptors.response.use(
      (resp) => {
        const data = resp.data
        if (!isApiResp(data)) return resp
        if (data.code === 200) return resp
        const err: BizError = new Error(data.msg || i18n.global.t('utils.http.bizError'))
        err.bizCode = data.code
        ;(err as BizError & { bizData?: unknown }).bizData = data.data
        throw err
      },
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          clearToken()
          location.href = '/login'
          return Promise.reject(error)
        }
        return Promise.reject(error)
      },
    )
  }

  async request<T>(config: AxiosRequestConfig): Promise<T> {
    try {
      const resp = await this.ins.request(config)
      const data = resp.data
      if (isApiResp(data)) return data.data as T
      return data as T
    } catch (e) {
      const msg = this.toMessage(e)
      if (msg) ElMessage.error(msg)
      throw e
    }
  }

  get<T>(url: string, config?: Omit<AxiosRequestConfig, 'url' | 'method'>) {
    return this.request<T>({ ...config, url, method: 'GET' })
  }

  post<T>(url: string, data?: unknown, config?: Omit<AxiosRequestConfig, 'url' | 'method' | 'data'>) {
    return this.request<T>({ ...config, url, method: 'POST', data })
  }

  put<T>(url: string, data?: unknown, config?: Omit<AxiosRequestConfig, 'url' | 'method' | 'data'>) {
    return this.request<T>({ ...config, url, method: 'PUT', data })
  }

  delete<T>(url: string, config?: Omit<AxiosRequestConfig, 'url' | 'method'>) {
    return this.request<T>({ ...config, url, method: 'DELETE' })
  }

  /** 下载二进制文件（图片/视频/PDF）；仅当 Content-Type 为 JSON 时解析业务错误 */
  async downloadBlob(config: AxiosRequestConfig): Promise<Blob> {
    try {
      const resp = await this.ins.request({
        ...config,
        responseType: 'blob',
        timeout: config.timeout ?? 120000,
      })
      const blob = resp.data as Blob
      if (!(blob instanceof Blob)) {
        throw new Error(i18n.global.t('utils.http.downloadFailed'))
      }
      const ct = String(resp.headers?.['content-type'] || '').toLowerCase()
      if (ct.includes('application/json') || ct.includes('text/json')) {
        const text = await blob.text()
        try {
          const j = JSON.parse(text) as { code?: number; msg?: string }
          if (typeof j.code === 'number' && j.code !== 200) {
            const err: BizError = new Error(j.msg || i18n.global.t('utils.http.downloadFailed'))
            err.bizCode = j.code
            throw err
          }
        } catch (e) {
          if (e instanceof Error && typeof (e as BizError).bizCode === 'number') throw e
        }
        throw new Error(i18n.global.t('utils.http.downloadFailed'))
      }
      if (blob.size === 0) {
        throw new Error(i18n.global.t('utils.http.fileEmpty'))
      }
      return blob
    } catch (e) {
      const msg = this.toMessage(e)
      if (msg) ElMessage.error(msg)
      throw e
    }
  }

  private toMessage(e: unknown): string | null {
    if (e instanceof Error) {
      const anyErr = e as BizError & { bizData?: { errors?: Array<{ loc?: unknown[]; msg?: string }> } }
      if (typeof anyErr.bizCode === 'number') {
        const errs = anyErr.bizData?.errors
        if (Array.isArray(errs) && errs.length) {
          const detail = errs
            .slice(0, 3)
            .map((x) => x.msg || JSON.stringify(x.loc))
            .join('；')
          return i18n.global.t('utils.http.bizErrorWithDetail', { message: e.message || i18n.global.t('utils.http.bizError'), detail })
        }
        return e.message || i18n.global.t('utils.http.bizError')
      }
    }
    if (axios.isAxiosError(e)) {
      const data = e.response?.data as any
      if (data && typeof data === 'object' && typeof data.detail === 'string') return data.detail
      if (typeof e.message === 'string') return e.message
    }
    return null
  }
}

export const http = new HttpClient(import.meta.env.VITE_API_BASE || '/api')
