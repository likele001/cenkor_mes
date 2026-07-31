import { apiGet } from '@/utils/http'

export function getFeishuBindUrl() {
  return apiGet<{ authorize_url: string }>('/h5/feishu/bind-url')
}

export function getFeishuBindStatus() {
  return apiGet<{
    enabled: boolean
    bound: boolean
    feishu_open_id: string | null
    feishu_bound_at: string | null
    bot_open_link?: string
  }>('/h5/feishu/bind-status')
}
