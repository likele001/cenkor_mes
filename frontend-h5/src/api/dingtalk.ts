import { apiGet } from '@/utils/http'

export function getDingtalkBindUrl() {
  return apiGet<{ authorize_url: string }>('/h5/dingtalk/bind-url')
}

export function getDingtalkBindStatus() {
  return apiGet<{
    enabled: boolean
    bound: boolean
    dingtalk_userid: string
    dingtalk_bound_at: string | null
  }>('/h5/dingtalk/bind-status')
}
