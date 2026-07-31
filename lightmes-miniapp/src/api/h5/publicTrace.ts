import { apiGet } from '../request'

export type PublicTraceStep = {
  process_name: string | null
  operator: string | null
  time: string | null
  trace_code: string | null
}

export type PublicTraceMedia = {
  id: number
  kind: 'image' | 'video'
  content_type: string
  original_filename: string
  url?: string
}

export type PublicTraceDetail = {
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

export function getPublicTrace(code: string) {
  return apiGet<PublicTraceDetail>(`/h5/public/trace/${encodeURIComponent(code.trim())}`)
}

export function publicTraceMediaUrl(attachmentId: number, code: string, apiUrl?: string | null) {
  if (apiUrl) {
    if (apiUrl.startsWith('http://') || apiUrl.startsWith('https://')) return apiUrl
    if (apiUrl.startsWith('/')) {
      const base = import.meta.env.VITE_API_BASE_URL || '/api'
      const origin = base.startsWith('http') ? base.replace(/\/api\/?$/, '') : ''
      return `${origin}${apiUrl}`
    }
  }
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const prefix = base.startsWith('http') ? base : base
  return `${prefix.replace(/\/$/, '')}/h5/public/trace/media/${attachmentId}?code=${encodeURIComponent(code.trim())}`
}
