import { apiGet, apiPost, apiPut } from '@/utils/http'

export type LoginRespData = {
  token?: string
  access_token?: string
}

export type MeOut = {
  id: number
  tenant_id: number
  username: string
  full_name: string | null
  phone: string | null
  email: string | null
  feishu_bound?: boolean
  feishu_open_id?: string | null
  is_superuser: boolean
  roles: string[]
  permissions: string[]
}

export type ProfileUpdateIn = {
  full_name?: string | null
  phone?: string | null
  email?: string | null
}

export async function login(payload: {
  tenant_code: string
  username: string
  password: string
  remember_me?: boolean
  captcha_id?: string
  captcha_code?: string
}) {
  const data = await apiPost<LoginRespData>('/auth/login', payload)
  return data.token || data.access_token || ''
}

export async function me() {
  return apiGet<MeOut>('/auth/me')
}

export async function updateProfile(payload: ProfileUpdateIn) {
  return apiPut<MeOut>('/auth/profile', payload)
}

export async function changePassword(payload: { old_password: string; new_password: string }) {
  return apiPut<void>('/auth/password', payload)
}
