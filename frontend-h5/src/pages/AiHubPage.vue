<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

const entries = computed(() => [
  { path: '/ai-assistant', icon: '🤖', color: 'text-indigo-500', title: t('ai.cardAssistantTitle'), desc: t('ai.cardAssistantDesc') },
  { path: '/ai-alerts', icon: '⚠️', color: 'text-orange-500', title: t('ai.cardAlertsTitle'), desc: t('ai.cardAlertsDesc') },
  { path: '/ai-employees', icon: '💬', color: 'text-green-500', title: t('ai.cardEmployeesTitle'), desc: t('ai.cardEmployeesDesc') },
  { path: '/ai-insight', icon: '📊', color: 'text-cyan-500', title: t('ai.cardInsightTitle'), desc: t('ai.cardInsightDesc') },
  { path: '/ai-scene', icon: '📝', color: 'text-amber-500', title: t('ai.cardSceneTitle'), desc: t('ai.cardSceneDesc') },
  { path: '/help', icon: '💡', color: 'text-blue-500', title: t('ai.cardHelpTitle'), desc: t('ai.cardHelpDesc') },
])
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
        class="rounded-xl bg-white p-4 shadow-sm active:bg-zinc-50"
        @click="router.push(e.path)"
      >
        <div :class="['text-2xl', e.color]">{{ e.icon }}</div>
        <div class="mt-2 text-sm font-medium text-zinc-800">{{ e.title }}</div>
        <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ e.desc }}</div>
      </div>
    </div>
  </div>
</template>
