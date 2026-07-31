<template>
  <div class="admin-brand flex items-center gap-3 min-w-0" :class="{ 'admin-brand--compact': compact }">
    <div v-if="logoUrl" class="admin-brand__logo-img shrink-0 overflow-hidden rounded-lg border border-[var(--admin-brand-mark-border)]">
      <img :src="logoUrl" :alt="displayTitle" class="w-full h-full object-cover" />
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
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    logoUrl?: string | null
    compact?: boolean
    useTenant?: boolean
  }>(),
  {
    subtitle: '企业生产管理',
    compact: false,
    useTenant: true,
  }
)

const auth = useAuthStore()

const resolvedLogo = computed(() => {
  if (props.logoUrl !== undefined) return props.logoUrl
  if (props.useTenant) return auth.me?.logo_url ?? null
  return null
})

const logoUrl = computed(() => resolvedLogo.value || null)

const displayTitle = computed(() => {
  if (props.title) return props.title
  if (props.useTenant && auth.me?.tenant_name) return auth.me.tenant_name
  return '辰科MES'
})

const markText = computed(() => {
  const t = displayTitle.value.trim()
  if (!t) return 'LM'
  if (t.length <= 2) return t.toUpperCase()
  return t.slice(0, 2).toUpperCase()
})

const resolvedSubtitle = computed(() => {
  return props.subtitle || t('common.enterpriseManagement')
})
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
