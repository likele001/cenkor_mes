import { useI18n } from 'vue-i18n'
import { setStoredLocale, type AppLocale } from '@/locales'

const LOCALE_OPTIONS: { value: AppLocale; labelKey: string }[] = [
  { value: 'zh-CN', labelKey: 'common.zhCN' },
  { value: 'en-US', labelKey: 'common.enUS' },
  { value: 'ko-KR', labelKey: 'common.koKR' },
]

export function useCustomerLocale() {
  const { t, locale } = useI18n()

  function localeLabel(loc: AppLocale) {
    const opt = LOCALE_OPTIONS.find((o) => o.value === loc)
    return opt ? t(opt.labelKey) : loc
  }

  function currentLocaleLabel() {
    return localeLabel(locale.value as AppLocale)
  }

  function pickLanguage(onPicked?: () => void) {
    const labels = LOCALE_OPTIONS.map((o) => t(o.labelKey))
    uni.showActionSheet({
      itemList: labels,
      success: (res) => {
        const picked = LOCALE_OPTIONS[res.tapIndex]
        if (!picked) return
        locale.value = picked.value
        setStoredLocale(picked.value)
        onPicked?.()
      },
    })
  }

  function setNavTitle(key: string) {
    uni.setNavigationBarTitle({ title: t(key) })
  }

  return {
    locale,
    localeOptions: LOCALE_OPTIONS,
    localeLabel,
    currentLocaleLabel,
    pickLanguage,
    setNavTitle,
  }
}
