import { http } from '@/utils/http'

export type ChannelOverview = {
  enabled: boolean
  configured: boolean
  agent_name: string
  agent_id?: string
  today_total: number
  callback_url: string
  oauth_redirect_url: string
}

export type MessageCenterOverview = {
  channels: {
    feishu: ChannelOverview
    wecom: ChannelOverview
    dingtalk: ChannelOverview
  }
}

export type ChannelConfig = {
  chat_id?: string
  webhook_url?: string
  webhook_secret?: string
  enabled: boolean
}

export type MessageGroup = {
  code: string
  name: string
  enabled: boolean
  channels: {
    feishu?: ChannelConfig
    wecom?: ChannelConfig
    dingtalk?: ChannelConfig
  }
}

export type MessageRule = {
  event_code: string
  feishu_rule: Record<string, unknown>
  wecom_rule: Record<string, unknown>
  dingtalk_rule: Record<string, unknown>
}

export type UserBinding = {
  id: number
  username: string
  full_name: string | null
  phone: string | null
  email: string | null
  department_id: number | null
  feishu_open_id: string | null
  feishu_bound_at: string | null
  wecom_userid: string | null
  wecom_bound_at: string | null
  dingtalk_userid: string | null
  dingtalk_bound_at: string | null
  bound: boolean
}

export type PushLog = {
  id: number
  channel: 'feishu' | 'wecom' | 'dingtalk'
  event_code: string
  target_kind: string
  target_ref: string
  title: string
  content: string
  level: string
  biz_type: string | null
  biz_id: number | null
  status: string
  error_msg: string | null
  message_id: string | null
  retry_count: number
  alerted_at: string | null
  created_at: string | null
  sent_at: string | null
}

export type AlertRecipient = {
  id: number
  username: string
  full_name: string | null
  is_superuser: boolean
}

export const messageCenterApi = {
  getOverview() {
    return http.request<MessageCenterOverview>({
      url: '/admin/system/message-center/overview',
      method: 'GET',
    })
  },
  listGroups() {
    return http.request<{ items: MessageGroup[] }>({
      url: '/admin/system/message-center/groups',
      method: 'GET',
    })
  },
  saveGroups(items: MessageGroup[]) {
    return http.request<{ items: MessageGroup[] }>({
      url: '/admin/system/message-center/groups',
      method: 'POST',
      data: { items },
    })
  },
  listRules() {
    return http.request<{
      items: MessageRule[]
      event_catalog: { code: string; name: string; category: string }[]
      target_options: { code: string; name: string }[]
    }>({
      url: '/admin/system/message-center/rules',
      method: 'GET',
    })
  },
  listUserBindings(params?: { keyword?: string; unbound_only?: boolean; offset?: number; limit?: number }) {
    return http.request<{ items: UserBinding[] }>({
      url: '/admin/system/message-center/user-bindings',
      method: 'GET',
      params,
    })
  },
  listPushLogs(params?: { channel?: 'feishu' | 'wecom' | 'dingtalk'; event_code?: string; status?: string; offset?: number; limit?: number }) {
    return http.request<{ items: PushLog[] }>({
      url: '/admin/system/message-center/push-logs',
      method: 'GET',
      params,
    })
  },
  retryPushLog(channel: 'feishu' | 'wecom' | 'dingtalk', id: number) {
    return http.request({ url: `/admin/system/${channel}/push-logs/${id}/retry`, method: 'POST' })
  },
  getAlertRecipients() {
    return http.request<{ user_ids: number[]; users: AlertRecipient[] }>({
      url: '/admin/system/message-center/alert-recipients',
      method: 'GET',
    })
  },
  saveAlertRecipients(userIds: number[]) {
    return http.request({ url: '/admin/system/message-center/alert-recipients', method: 'PUT', data: { user_ids: userIds } })
  },
  getAllBindableUsers() {
    return http.request<{ items: AlertRecipient[] }>({
      url: '/admin/system/message-center/all-bindable-users',
      method: 'GET',
    })
  },
  runMigration() {
    return http.request({ url: '/admin/system/message-center/run-migration', method: 'POST' })
  },
}
