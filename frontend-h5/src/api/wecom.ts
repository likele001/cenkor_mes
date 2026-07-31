import { apiGet } from '@/utils/http'

export function getWecomBindUrl() {
  return apiGet<{ authorize_url: string }>('/h5/wecom/bind-url')
}

export function getWecomBindStatus() {
  return apiGet<{
    enabled: boolean
    bound: boolean
    wecom_userid: string
    wecom_bound_at: string | null
  }>('/h5/wecom/bind-status')
}
