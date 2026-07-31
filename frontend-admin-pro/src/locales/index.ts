import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'
import koKRPartial from './ko-KR'
import koKRShell from './ko-KR-shell'
import { deepMerge } from './deepMerge'

/** 韩文：英文基底 + 已有韩文翻译 + 导航/首页等 shell */
const koKR = deepMerge(deepMerge(enUS, koKRPartial), koKRShell)

const STORAGE_KEY = 'cenkormes-locale'

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
  fallbackLocale: {
    'ko-KR': ['zh-CN'],
    'en-US': ['zh-CN'],
    default: ['zh-CN'],
  },
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
    'ko-KR': koKR,
  },
})
