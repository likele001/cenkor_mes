import { http } from '@/utils/http'

export type FeishuGroup = {
  code: string
  name: string
  chat_id: string
  webhook_url?: string
  enabled: boolean
}

export type FeishuRule = {
  enabled: boolean
  targets?: string[]
  channels?: string[]
  escalation?: Record<string, string[]>
}

export type FeishuSettings = {
  enabled: boolean
  app_id: string
  app_secret_configured: boolean
  app_secret_masked: string
  tenant_key: string
  encrypt_key_configured: boolean
  verification_token_configured: boolean
  message_format: string
  h5_public_base_url: string
  admin_public_base_url: string
  api_public_base_url: string
  card_actions_enabled: boolean
  personal_urgent_enabled?: boolean
  callback_url: string
  oauth_redirect_url: string
  groups: FeishuGroup[]
  rules: Record<string, FeishuRule>
  quiet_hours: { enabled: boolean; start: string; end: string }
  card_templates: Record<string, string>
  event_catalog: { code: string; name: string; category: string }[]
  target_options: { code: string; name: string }[]
}

export type FeishuPushLog = {
  id: number
  event_code: string
  target_kind: string
  target_ref: string
  title: string
  content: string
  level: string
  status: string
  error_msg: string | null
  feishu_message_id: string | null
  created_at: string
  sent_at: string | null
}

export type FeishuUserBinding = {
  id: number
  username: string
  full_name: string | null
  phone: string | null
  email: string | null
  department_id: number | null
  feishu_open_id: string | null
  feishu_user_id: string | null
  feishu_bound_at: string | null
  bound: boolean
}

export type FeishuDeptBinding = {
  id: number
  code: string
  name: string
  parent_id: number | null
  feishu_open_department_id: string | null
  feishu_chat_group_code: string | null
}

export type FeishuSetupChecklist = {
  ready: boolean
  online_version: string
  bot_status: number
  bot_status_label: string
  bot_in_version: boolean
  app_status: number
  subscribed_events: string[]
  missing_events: { code: string; name: string }[]
  missing_scopes: { code: string; name: string }[]
  bot_open_link: string
  steps: { title: string; detail: string; done: boolean | null }[]
}

export type FeishuDeliveryDiagnostics = {
  feishu_tenant_name: string
  bot_name: string
  bot_app_id: string
  bot_open_link: string
  bound_feishu_name: string
  bound_feishu_email: string
  bound_open_id: string
  p2p_chat_id: string
  chat_open_link: string
  p2p_message_count: number
  hints: string[]
}

export type FeishuChat = {
  chat_id: string
  name: string
  description?: string
}

export const feishuApi = {
  getSettings() {
    return http.request<FeishuSettings>({ url: '/admin/system/feishu', method: 'GET' })
  },
  saveSettings(data: Partial<FeishuSettings> & { app_secret?: string; encrypt_key?: string; verification_token?: string }) {
    return http.request<FeishuSettings>({ url: '/admin/system/feishu', method: 'PUT', data })
  },
  testConnection() {
    return http.request<{ ok: boolean; token_preview?: string }>({
      url: '/admin/system/feishu/test-connection',
      method: 'POST',
    })
  },
  testSend(data: { receive_id: string; receive_id_type: string; text?: string }) {
    return http.request<{ ok: boolean; message_id?: string; delivery?: FeishuDeliveryDiagnostics }>({
      url: '/admin/system/feishu/test-send',
      method: 'POST',
      data,
    })
  },
  getDeliveryDiagnostics(userId?: number) {
    return http.request<FeishuDeliveryDiagnostics>({
      url: '/admin/system/feishu/delivery-diagnostics',
      method: 'GET',
      params: userId ? { user_id: userId } : undefined,
    })
  },
  getSetupChecklist() {
    return http.request<FeishuSetupChecklist>({
      url: '/admin/system/feishu/setup-checklist',
      method: 'GET',
    })
  },
  listChats() {
    return http.request<{ items: FeishuChat[] }>({ url: '/admin/system/feishu/chats', method: 'GET' })
  },
  listPushLogs(params?: { event_code?: string; status?: string; offset?: number; limit?: number }) {
    return http.request<{ items: FeishuPushLog[] }>({
      url: '/admin/system/feishu/push-logs',
      method: 'GET',
      params,
    })
  },
  retryPushLog(id: number) {
    return http.request({ url: `/admin/system/feishu/push-logs/${id}/retry`, method: 'POST' })
  },
  listUserBindings(params?: { keyword?: string; unbound_only?: boolean }) {
    return http.request<{ items: FeishuUserBinding[] }>({
      url: '/admin/system/feishu/user-bindings',
      method: 'GET',
      params,
    })
  },
  updateUserBinding(userId: number, data: { feishu_open_id?: string; feishu_user_id?: string }) {
    return http.request({ url: `/admin/system/feishu/user-bindings/${userId}`, method: 'PUT', data })
  },
  batchMatchMobile(refreshAll = false) {
    return http.request<{ matched: number; total: number; refreshed?: boolean }>({
      url: '/admin/system/feishu/user-bindings/batch-match-mobile',
      method: 'POST',
      params: refreshAll ? { refresh_all: true } : undefined,
    })
  },
  listDepartmentBindings() {
    return http.request<{ items: FeishuDeptBinding[] }>({
      url: '/admin/system/feishu/department-bindings',
      method: 'GET',
    })
  },
  updateDepartmentBinding(
    departmentId: number,
    data: { feishu_open_department_id?: string; feishu_chat_group_code?: string },
  ) {
    return http.request({
      url: `/admin/system/feishu/department-bindings/${departmentId}`,
      method: 'PUT',
      data,
    })
  },
  simulate(data: { event_code: string; user_id?: number; department_id?: number; workshop?: string }) {
    return http.request<{ targets: { kind: string; ref: string }[]; rule: FeishuRule }>({
      url: '/admin/system/feishu/simulate',
      method: 'POST',
      data,
    })
  },
  listFeishuDepartments() {
    return http.request<{ items: { open_department_id: string; name: string }[] }>({
      url: '/admin/system/feishu/feishu-departments',
      method: 'GET',
    })
  },
  getBindUrl(userId?: number) {
    return http.request<{ authorize_url: string; user_id: number }>({
      url: '/admin/system/feishu/bind-url',
      method: 'POST',
      data: userId ? { user_id: userId } : {},
    })
  },
  previewCard(data: {
    event_code?: string
    title?: string
    content?: string
    level?: string
    biz_type?: string
    biz_id?: number
  }) {
    return http.request<{ card: Record<string, unknown> }>({
      url: '/admin/system/feishu/preview-card',
      method: 'POST',
      data,
    })
  },
}
