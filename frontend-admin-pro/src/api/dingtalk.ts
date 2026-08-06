import { http } from '@/utils/http'

export type DingtalkGroup = {
  code: string
  name: string
  webhook_url?: string
  webhook_secret?: string
  enabled: boolean
}

export type DingtalkRule = {
  enabled: boolean
  targets?: string[]
  channels?: string[]
  escalation?: Record<string, string[]>
}

export type DingtalkSettings = {
  enabled: boolean
  corp_id: string
  app_key: string
  agent_id: string
  corp_id_configured?: boolean
  app_key_configured?: boolean
  agent_id_configured?: boolean
  app_secret_configured: boolean
  app_secret_masked: string
  message_format: string
  card_actions_enabled: boolean
  h5_public_base_url: string
  admin_public_base_url: string
  api_public_base_url: string
  h5_public_base_url_default?: string
  api_public_base_url_default?: string
  oauth_redirect_url: string
  groups: DingtalkGroup[]
  rules: Record<string, DingtalkRule>
  quiet_hours: { enabled: boolean; start: string; end: string }
  event_catalog: { code: string; name: string; category: string }[]
  target_options: { code: string; name: string }[]
}

export type DingtalkPushLog = {
  id: number
  event_code: string
  target_kind: string
  target_ref: string
  title: string
  content: string
  level: string
  status: string
  error_msg: string | null
  dingtalk_task_id: string | null
  created_at: string
  sent_at: string | null
}

export type DingtalkUserBinding = {
  id: number
  username: string
  full_name: string | null
  phone: string | null
  email: string | null
  department_id: number | null
  dingtalk_userid: string | null
  dingtalk_bound_at: string | null
  bound: boolean
}

export type DingtalkDeptBinding = {
  id: number
  code: string
  name: string
  parent_id: number | null
  dingtalk_dept_id: string | null
  dingtalk_chat_group_code: string | null
}

export type DingtalkSetupChecklist = {
  ready: boolean
  steps: { title: string; detail: string; done: boolean | null }[]
}

export const dingtalkApi = {
  getSettings() {
    return http.request<DingtalkSettings>({ url: '/admin/system/dingtalk', method: 'GET' })
  },
  saveSettings(data: Partial<DingtalkSettings> & { app_secret?: string }) {
    return http.request<DingtalkSettings>({ url: '/admin/system/dingtalk', method: 'PUT', data })
  },
  testConnection() {
    return http.request<{ ok: boolean; token_preview?: string }>({
      url: '/admin/system/dingtalk/test-connection',
      method: 'POST',
    })
  },
  testSend(data: { receive_id: string; receive_id_type: string; text?: string }) {
    return http.request<{ ok: boolean; task_id?: string }>({
      url: '/admin/system/dingtalk/test-send',
      method: 'POST',
      data,
    })
  },
  getSetupChecklist() {
    return http.request<DingtalkSetupChecklist>({
      url: '/admin/system/dingtalk/setup-checklist',
      method: 'GET',
    })
  },
  listPushLogs(params?: { event_code?: string; status?: string; offset?: number; limit?: number }) {
    return http.request<{ items: DingtalkPushLog[] }>({
      url: '/admin/system/dingtalk/push-logs',
      method: 'GET',
      params,
    })
  },
  retryPushLog(id: number) {
    return http.request({ url: `/admin/system/dingtalk/push-logs/${id}/retry`, method: 'POST' })
  },
  listUserBindings(params?: { keyword?: string; unbound_only?: boolean }) {
    return http.request<{ items: DingtalkUserBinding[] }>({
      url: '/admin/system/dingtalk/user-bindings',
      method: 'GET',
      params,
    })
  },
  updateUserBinding(userId: number, data: { dingtalk_userid?: string }) {
    return http.request({ url: `/admin/system/dingtalk/user-bindings/${userId}`, method: 'PUT', data })
  },
  batchMatchMobile() {
    return http.request<{ matched: number; total: number }>({
      url: '/admin/system/dingtalk/user-bindings/batch-match-mobile',
      method: 'POST',
    })
  },
  listDepartmentBindings() {
    return http.request<{ items: DingtalkDeptBinding[] }>({
      url: '/admin/system/dingtalk/department-bindings',
      method: 'GET',
    })
  },
  updateDepartmentBinding(
    departmentId: number,
    data: { dingtalk_dept_id?: string; dingtalk_chat_group_code?: string },
  ) {
    return http.request({
      url: `/admin/system/dingtalk/department-bindings/${departmentId}`,
      method: 'PUT',
      data,
    })
  },
  listDingtalkDepartments() {
    return http.request<{ items: { dept_id: number; name: string; parent_id: number }[] }>({
      url: '/admin/system/dingtalk/dingtalk-departments',
      method: 'GET',
    })
  },
  getBindUrl() {
    return http.request<{ authorize_url: string }>({
      url: '/admin/system/dingtalk/bind-url',
      method: 'POST',
    })
  },
}
