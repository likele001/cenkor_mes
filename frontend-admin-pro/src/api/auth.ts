import { http } from '@/utils/http'

export type LoginIn = {
  username: string
  password: string
  tenant_code?: string
  remember_me?: boolean
  captcha_id?: string
  captcha_code?: string
}

export type LoginOut = {
  access_token: string
  token_type: string
  expires_in?: number
  remember_me?: boolean
}

export type MeOut = {
  id: number
  tenant_id: number
  tenant_code: string
  tenant_name: string | null
  logo_url: string | null
  username: string
  full_name: string | null
  phone: string | null
  email: string | null
  is_superuser: boolean
  roles: string[]
  permissions: string[]
}

export type ProfileUpdateIn = {
  full_name?: string | null
  phone?: string | null
  email?: string | null
}

export type ChangePasswordIn = {
  old_password: string
  new_password: string
}

export function loginApi(payload: LoginIn) {
  return http.request<LoginOut>({
    url: '/auth/login',
    method: 'POST',
    data: payload,
  })
}

export function meApi() {
  return http.request<MeOut>({
    url: '/auth/me',
    method: 'GET',
  })
}

export function updateProfileApi(payload: ProfileUpdateIn) {
  return http.request<MeOut>({
    url: '/auth/profile',
    method: 'PUT',
    data: payload,
  })
}

export function changePasswordApi(payload: ChangePasswordIn) {
  return http.request<void>({
    url: '/auth/password',
    method: 'PUT',
    data: payload,
  })
}
