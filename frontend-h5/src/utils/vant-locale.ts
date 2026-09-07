// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { Locale } from 'vant'
import vantEnUS from 'vant/es/locale/lang/en-US'
import vantZhCN from 'vant/es/locale/lang/zh-CN'
import type { AppLocale } from '@/locales'

export function applyVantLocale(locale: AppLocale) {
  if (locale === 'zh-CN') {
    Locale.use('zh-CN', vantZhCN)
    return
  }
  // Vant 无韩文包，英文组件文案用于 en-US / ko-KR
  Locale.use('en-US', vantEnUS)
}
