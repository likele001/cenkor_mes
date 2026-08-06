import { http } from '@/utils/http'

export type PushStatusOut = {
  timestamp: string
  healthy: boolean
  redis: {
    queues: Record<string, number>
    total: number
  }
  channels: {
    feishu: ChannelStats
    wecom: ChannelStats
    dingtalk: ChannelStats
  }
  summary: {
    total: number
    success: number
    failed: number
    pending: number
  }
}

export type ChannelStats = {
  total: number
  success: number
  failed: number
  pending: number
  success_rate: number
}

export type PushLogOut = {
  id: number
  event_code: string
  target_kind: string
  target_ref: string
  title: string
  status: string
  error_msg: string | null
  created_at: string | null
  sent_at: string | null
}

export const pushMonitorApi = {
  getStatus() {
    return http.request<PushStatusOut>({
      url: '/admin/push-monitor/status',
      method: 'GET',
    })
  },
  getLogs(channel: string, params?: { status?: string; limit?: number }) {
    return http.request<{ code: number; data: PushLogOut[] }>({
      url: `/admin/push-monitor/logs/${channel}`,
      method: 'GET',
      params,
    })
  },
  testPush(channel: string, tenantId?: number) {
    return http.request<{ code: number; data: { count: number } }>({
      url: `/admin/push-monitor/test/${channel}`,
      method: 'POST',
      params: { tenant_id: tenantId || 2 },
    })
  },
  clearQueue() {
    return http.request<{ code: number; data: { cleared: number } }>({
      url: '/admin/push-monitor/clear-queue',
      method: 'POST',
    })
  },
}
