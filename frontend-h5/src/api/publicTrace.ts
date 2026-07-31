import { apiGet } from '@/utils/http'

export interface PublicTraceStep {
  process_name: string | null
  operator: string | null
  time: string | null
  trace_code: string | null
}

export interface PublicTraceMedia {
  id: number
  kind: 'image' | 'video'
  content_type: string
  original_filename: string
  url?: string
}

export interface PublicTraceDetail {
  product_code: string
  piece_no: number | null
  product_name: string | null
  product_code_display: string | null
  sku_name: string | null
  sku_code: string | null
  order_code: string | null
  order_name: string | null
  customer_name: string | null
  flow_steps: PublicTraceStep[]
  media: PublicTraceMedia[]
  trace_url?: string
  generated_at?: string | null
}

export function getPublicTrace(code: string, tenant?: string) {
  let url = `/h5/public/trace/${encodeURIComponent(code.trim())}`
  if (tenant) {
    url += `?tenant=${encodeURIComponent(tenant.trim())}`
  }
  return apiGet<PublicTraceDetail>(url)
}

export function publicTraceMediaUrl(attachmentId: number, code: string, apiUrl?: string | null) {
  if (apiUrl) {
    if (apiUrl.startsWith('http://') || apiUrl.startsWith('https://')) return apiUrl
    if (apiUrl.startsWith('/')) {
      const origin = typeof window !== 'undefined' ? window.location.origin : ''
      return `${origin}${apiUrl}`
    }
  }
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const prefix = base.startsWith('http') ? base : `${typeof window !== 'undefined' ? window.location.origin : ''}${base}`
  return `${prefix}/h5/public/trace/media/${attachmentId}?code=${encodeURIComponent(code.trim())}`
}
