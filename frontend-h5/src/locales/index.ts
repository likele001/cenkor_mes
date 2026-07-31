import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'
import koKR from './ko-KR'

const STORAGE_KEY = 'cenkormes-h5-locale'

export type AppLocale = 'zh-CN' | 'en-US' | 'ko-KR'

export function getStoredLocale(): AppLocale {
  const v = localStorage.getItem(STORAGE_KEY)
  if (v === 'en-US' || v === 'ko-KR') return v
  return 'zh-CN'
}

export function setStoredLocale(locale: AppLocale) {
  localStorage.setItem(STORAGE_KEY, locale)
}

export const i18n = createI18n({
  legacy: false,
  locale: getStoredLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
    'ko-KR': koKR,
  },
})
