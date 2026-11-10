<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showDialog, showToast } from 'vant'
import { analyzeInsight, listAiInsight, type AiInsightItem } from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const loading = ref(true)
const locked = ref(false)
const items = ref<AiInsightItem[]>([])
const generatedAt = ref('')
const analyzing = ref('')

async function load() {
  loading.value = true
  try {
    const r = await listAiInsight()
    items.value = r.items || []
    generatedAt.value = r.generated_at || ''
    locked.value = false
  } catch (e: unknown) {
    items.value = []
    if (isAccessDenied(e)) {
      locked.value = true
    } else {
      showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
    }
  } finally {
    loading.value = false
  }
}

async function analyze(it: AiInsightItem) {
  analyzing.value = it.axis
  try {
    const r = await analyzeInsight(it.axis)
    await showDialog({
      title: it.name,
      message: r.report || r.rule_summary || r.error || t('ai.noAnalysis'),
      confirmButtonText: t('ai.ok'),
    })
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameInsight'))) {
      showToast(e instanceof Error ? e.message : t('ai.analyzeFailed'))
    }
  } finally {
    analyzing.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-white p-3 shadow-sm">
      <div class="text-sm font-medium text-zinc-800">{{ t('ai.insightTitle') }}</div>
      <div class="mt-1 text-[11px] text-zinc-500">{{ t('ai.insightSubtitle') }}</div>
      <div v-if="generatedAt" class="mt-1 text-[11px] text-zinc-400">{{ t('ai.dataTime', { v: generatedAt }) }}</div>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>

    <div v-else-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">{{ t('ai.lockedTitle', { name: t('ai.nameInsight') }) }}</div>
      <div class="mt-2 text-xs text-zinc-400">{{ t('ai.lockedHint') }}</div>
    </div>

    <van-empty v-else-if="!items.length" :description="t('ai.noData')" />

    <div v-else class="space-y-2">
      <div v-for="it in items" :key="it.axis" class="rounded-xl bg-white p-3 shadow-sm">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-zinc-800">{{ it.name }}</div>
            <div class="mt-1 text-xs leading-relaxed text-zinc-600">
              {{ it.headline || (it.error ? t('ai.fetchFailed', { v: it.error }) : t('ai.noData')) }}
            </div>
          </div>
          <van-button size="small" type="primary" plain :loading="analyzing === it.axis" @click="analyze(it)">
            {{ t('ai.analyze') }}
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>
