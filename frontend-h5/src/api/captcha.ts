import { apiGet } from '@/utils/http'

export type CaptchaOut = {
  enabled: boolean
  captcha_id?: string
  image_base64?: string
  expires_in?: number
}

export function fetchLoginCaptcha() {
  return apiGet<CaptchaOut>('/auth/captcha')
}
