// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fetchPublicConfig } from '@/api/public'

const DEFAULT_TITLE = '辰科MES'

export const useAppConfigStore = defineStore('app-config', () => {
  const companyName = ref('')
  const logoUrl = ref('')
  const loginCaptchaEnabled = ref(false)
  const sessionExpireMinutes = ref(0)
  const rememberMeExpireMinutes = ref(0)
  const loaded = ref(false)

  const brandTitle = computed(() => companyName.value.trim() || DEFAULT_TITLE)
  const browserTitle = computed(() => `${brandTitle.value} 管理后台`)

  async function load(force = false) {
    if (loaded.value && !force) return
    try {
      const cfg = await fetchPublicConfig()
      companyName.value = cfg.company_name || ''
      logoUrl.value = cfg.logo_url || ''
      loginCaptchaEnabled.value = Boolean(cfg.login_captcha_enabled)
      sessionExpireMinutes.value = Number(cfg.session_expire_minutes) || 0
      rememberMeExpireMinutes.value = Number(cfg.remember_me_expire_minutes) || 0
      loaded.value = true
    } catch {
      /* 拿不到就走默认品牌，不能让登录页白屏 */
    }
    applyBrowserTitle()
  }

  function applyBrowserTitle() {
    document.title = browserTitle.value
  }

  return {
    companyName,
    logoUrl,
    loginCaptchaEnabled,
    sessionExpireMinutes,
    rememberMeExpireMinutes,
    loaded,
    brandTitle,
    browserTitle,
    load,
    applyBrowserTitle,
  }
})
