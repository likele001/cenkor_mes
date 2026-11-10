<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'

type Entry = {
  path: string
  icon: string
  color: string
  title: string
  desc: string
  perm?: string
}

const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()

const entries = computed<Entry[]>(() => [
  { path: '/ai-assistant', icon: '🤖', color: 'text-indigo-500', title: t('ai.cardAssistantTitle'), desc: t('ai.cardAssistantDesc'), perm: 'ext.ai_assistant.view' },
  { path: '/ai-alerts', icon: '⚠️', color: 'text-orange-500', title: t('ai.cardAlertsTitle'), desc: t('ai.cardAlertsDesc'), perm: 'ext.ai_anomaly.view' },
  { path: '/ai-employees', icon: '💬', color: 'text-green-500', title: t('ai.cardEmployeesTitle'), desc: t('ai.cardEmployeesDesc'), perm: 'ext.ai_employee.view' },
  { path: '/ai-insight', icon: '📊', color: 'text-cyan-500', title: t('ai.cardInsightTitle'), desc: t('ai.cardInsightDesc'), perm: 'ext.ai_insight.view' },
  { path: '/ai-scene', icon: '📝', color: 'text-amber-500', title: t('ai.cardSceneTitle'), desc: t('ai.cardSceneDesc'), perm: 'ext.ai_scene_reports.view' },
  { path: '/help', icon: '💡', color: 'text-blue-500', title: t('ai.cardHelpTitle'), desc: t('ai.cardHelpDesc') },
])

// 只在权限列表已加载后提示，避免 fetchMe 完成前把全部卡片误标成未授权
function isLocked(e: Entry) {
  return !!e.perm && auth.permissions.length > 0 && !auth.hasPermission(e.perm)
}

function go(e: Entry) {
  if (isLocked(e)) showToast(t('ai.hubLockedHint'))
  router.push(e.path)
}

onMounted(async () => {
  if (!auth.permissions.length) await auth.fetchMe()
})
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-gradient-to-r from-violet-500 to-indigo-600 p-4 text-white shadow-sm">
      <div class="text-lg font-semibold">{{ t('ai.hubTitle') }}</div>
      <div class="mt-1 text-xs opacity-90">{{ t('ai.hubIntro') }}</div>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div
        v-for="e in entries"
        :key="e.path"
        class="relative rounded-xl bg-white p-4 shadow-sm active:bg-zinc-50"
        @click="go(e)"
      >
        <div v-if="isLocked(e)" class="absolute right-2 top-2">
          <van-tag plain type="warning">{{ t('ai.hubLocked') }}</van-tag>
        </div>
        <div :class="['text-2xl', e.color]">{{ e.icon }}</div>
        <div class="mt-2 text-sm font-medium text-zinc-800">{{ e.title }}</div>
        <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ e.desc }}</div>
      </div>
    </div>
  </div>
</template>
