import { apiGet } from '../request'

export function getDingtalkBindUrl() {
  return apiGet<{ authorize_url: string }>('/h5/dingtalk/bind-url')
}

export function getDingtalkBindStatus() {
  return apiGet<{
    enabled: boolean
    bound: boolean
    dingtalk_userid: string | null
    dingtalk_bound_at: string | null
  }>('/h5/dingtalk/bind-status')
}
