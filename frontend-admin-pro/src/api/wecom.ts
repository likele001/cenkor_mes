import { http } from '@/utils/http'

export type WecomGroup = {
  code: string
  name: string
  webhook_url?: string
  enabled: boolean
}

export type WecomRule = {
  enabled: boolean
  targets?: string[]
  channels?: string[]
  escalation?: Record<string, string[]>
}

export type WecomSettings = {
  enabled: boolean
  corp_id: string
  agent_id: string
  corp_id_configured?: boolean
  agent_id_configured?: boolean
  corp_secret_configured: boolean
  corp_secret_masked: string
  token: string
  token_configured?: boolean
  encoding_aes_key: string
  encoding_aes_key_configured?: boolean
  message_format: string
  h5_public_base_url: string
  admin_public_base_url: string
  api_public_base_url: string
  h5_public_base_url_default?: string
  api_public_base_url_default?: string
  callback_url: string
  oauth_redirect_url: string
  groups: WecomGroup[]
  rules: Record<string, WecomRule>
  quiet_hours: { enabled: boolean; start: string; end: string }
  event_catalog: { code: string; name: string; category: string }[]
  target_options: { code: string; name: string }[]
}

export type WecomPushLog = {
  id: number
  event_code: string
  target_kind: string
  target_ref: string
  title: string
  content: string
  level: string
  status: string
  error_msg: string | null
  wecom_msgid: string | null
  created_at: string
  sent_at: string | null
}

export type WecomUserBinding = {
  id: number
  username: string
  full_name: string | null
  phone: string | null
  email: string | null
  department_id: number | null
  wecom_userid: string | null
  wecom_bound_at: string | null
  bound: boolean
}

export type WecomDeptBinding = {
  id: number
  code: string
  name: string
  parent_id: number | null
  wecom_department_id: string | null
  wecom_chat_group_code: string | null
}

export type WecomSetupChecklist = {
  ready: boolean
  agent_name: string
  steps: { title: string; detail: string; done: boolean | null }[]
}

export type WecomDeliveryDiagnostics = {
  corp_id: string
  agent_id: string
  agent_name: string
  wecom_userid: string
  user_name: string
  user_mobile: string
  user_status: number
  hints: string[]
}

export const wecomApi = {
  getSettings() {
    return http.request<WecomSettings>({ url: '/admin/system/wecom', method: 'GET' })
  },
  saveSettings(data: Partial<WecomSettings> & { corp_secret?: string; encoding_aes_key?: string; token?: string }) {
    return http.request<WecomSettings>({ url: '/admin/system/wecom', method: 'PUT', data })
  },
  testConnection() {
    return http.request<{ ok: boolean; token_preview?: string }>({
      url: '/admin/system/wecom/test-connection',
      method: 'POST',
    })
  },
  testSend(data: { receive_id: string; receive_id_type: string; text?: string }) {
    return http.request<{ ok: boolean; message_id?: string }>({
      url: '/admin/system/wecom/test-send',
      method: 'POST',
      data,
    })
  },
  getSetupChecklist() {
    return http.request<WecomSetupChecklist>({
      url: '/admin/system/wecom/setup-checklist',
      method: 'GET',
    })
  },
  getDeliveryDiagnostics(userId?: number) {
    return http.request<WecomDeliveryDiagnostics>({
      url: '/admin/system/wecom/delivery-diagnostics',
      method: 'GET',
      params: userId ? { user_id: userId } : undefined,
    })
  },
  listPushLogs(params?: { event_code?: string; status?: string; offset?: number; limit?: number }) {
    return http.request<{ items: WecomPushLog[] }>({
      url: '/admin/system/wecom/push-logs',
      method: 'GET',
      params,
    })
  },
  retryPushLog(id: number) {
    return http.request({ url: `/admin/system/wecom/push-logs/${id}/retry`, method: 'POST' })
  },
  listUserBindings(params?: { keyword?: string; unbound_only?: boolean }) {
    return http.request<{ items: WecomUserBinding[] }>({
      url: '/admin/system/wecom/user-bindings',
      method: 'GET',
      params,
    })
  },
  updateUserBinding(userId: number, data: { wecom_userid?: string }) {
    return http.request({ url: `/admin/system/wecom/user-bindings/${userId}`, method: 'PUT', data })
  },
  batchMatchMobile() {
    return http.request<{ matched: number; total: number }>({
      url: '/admin/system/wecom/user-bindings/batch-match-mobile',
      method: 'POST',
    })
  },
  listDepartmentBindings() {
    return http.request<{ items: WecomDeptBinding[] }>({
      url: '/admin/system/wecom/department-bindings',
      method: 'GET',
    })
  },
  updateDepartmentBinding(
    departmentId: number,
    data: { wecom_department_id?: string; wecom_chat_group_code?: string },
  ) {
    return http.request({
      url: `/admin/system/wecom/department-bindings/${departmentId}`,
      method: 'PUT',
      data,
    })
  },
  listWecomDepartments() {
    return http.request<{ items: { department_id: number; name: string; parentid: number }[] }>({
      url: '/admin/system/wecom/wecom-departments',
      method: 'GET',
    })
  },
  simulate(data: { event_code: string; user_id?: number; department_id?: number; workshop?: string }) {
    return http.request<{ targets: { kind: string; ref: string }[]; rule: WecomRule }>({
      url: '/admin/system/wecom/simulate',
      method: 'POST',
      data,
    })
  },
}
