import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'
import koKR from './ko-KR'

export const LOCALE_STORAGE_KEY = 'cenkormes-customer-locale'

export type AppLocale = 'zh-CN' | 'en-US' | 'ko-KR'

export function detectDefaultLocale(): AppLocale {
  try {
    const stored = uni.getStorageSync(LOCALE_STORAGE_KEY) as AppLocale
    if (stored === 'en-US' || stored === 'ko-KR' || stored === 'zh-CN') return stored
  } catch {
    /* ignore */
  }
  try {
    const lang = (uni.getSystemInfoSync().language || '').toLowerCase()
    if (lang.startsWith('ko')) return 'ko-KR'
    if (lang.startsWith('en')) return 'en-US'
  } catch {
    /* ignore */
  }
  return 'zh-CN'
}

export function setStoredLocale(locale: AppLocale) {
  uni.setStorageSync(LOCALE_STORAGE_KEY, locale)
}

export const i18n = createI18n({
  legacy: false,
  locale: detectDefaultLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
    'ko-KR': koKR,
  },
})
