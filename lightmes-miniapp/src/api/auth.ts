import { apiGet, apiPost, apiPut } from './request'

export type MeOut = {
  id: number
  tenant_id: number
  username: string
  full_name: string | null
  phone: string | null
  email: string | null
  is_superuser: boolean
  roles: string[]
  permissions: string[]
  crm_module_enabled?: boolean
  silent_customer_days?: number
}

export type MiniappLoginData = {
  token?: string
  need_bind?: boolean
  openid?: string
  user?: { id: number; username: string; full_name: string | null; roles: string[] }
}

export function miniappLogin(code: string) {
  const q = `code=${encodeURIComponent(code)}`
  return apiPost<MiniappLoginData>(`/miniapp/auth/login?${q}`).then((data) => {
    if (data && typeof data === 'object' && 'need_bind' in data && data.need_bind && !data.token) {
      return data
    }
    return data
  })
}

export function bindOpenid(payload: { username: string; password: string; openid: string }) {
  return apiPost<MiniappLoginData>('/miniapp/auth/bind-openid', payload)
}

export function loginWithPassword(payload: {
  username: string
  password: string
  remember_me?: boolean
  captcha_id?: string
  captcha_code?: string
}) {
  return apiPost<{ token?: string; access_token?: string }>('/auth/login', payload)
}

export function fetchMe() {
  return apiGet<MeOut>('/auth/me')
}

export function updateProfile(payload: { full_name?: string; phone?: string; email?: string }) {
  return apiPut<MeOut>('/auth/profile', payload)
}

export function changePassword(payload: { old_password: string; new_password: string }) {
  return apiPut<void>('/auth/password', payload)
}
