<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <div class="admin-brand flex items-center gap-3 min-w-0" :class="{ 'admin-brand--compact': compact }">
    <div v-if="resolvedLogo" class="admin-brand__logo-img shrink-0 overflow-hidden rounded-lg border border-[var(--admin-brand-mark-border)]">
      <img :src="resolvedLogo" :alt="displayTitle" class="w-full h-full object-cover" />
    </div>
    <div
      v-else
      class="admin-brand__mark shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold border"
    >
      {{ markText }}
    </div>
    <div v-if="!compact" class="admin-brand__text min-w-0">
      <div class="admin-brand__title text-[15px] font-semibold tracking-tight truncate">{{ displayTitle }}</div>
      <div class="admin-brand__subtitle text-[11px] font-medium truncate">{{ resolvedSubtitle }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppConfigStore } from '@/stores/app-config'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    logoUrl?: string | null
    compact?: boolean
  }>(),
  {
    compact: false,
  }
)

const appConfig = useAppConfigStore()

// 后台「系统设置 → 企业信息」是品牌名与 logo 的唯一来源；登录前也能读到
const resolvedLogo = computed(() => (props.logoUrl !== undefined ? props.logoUrl : appConfig.logoUrl || null))

const displayTitle = computed(() => props.title || appConfig.brandTitle)

const markText = computed(() => {
  const s = displayTitle.value.trim()
  if (!s) return 'LM'
  if (s.length <= 2) return s.toUpperCase()
  return s.slice(0, 2).toUpperCase()
})

const resolvedSubtitle = computed(() => props.subtitle || t('common.enterpriseManagement'))
</script>

<style scoped>
.admin-brand__mark {
  color: var(--admin-brand-mark-text);
  background: var(--admin-brand-mark-bg);
  border-color: var(--admin-brand-mark-border);
}

.admin-brand__logo-img {
  width: 36px;
  height: 36px;
}

.admin-brand__title {
  color: var(--admin-brand-title);
}

.admin-brand__subtitle {
  color: var(--admin-brand-subtitle);
}
</style>
