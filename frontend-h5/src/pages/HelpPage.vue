<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import {
  aiHelp, getKnowledgeStatus, knowledgeAsk, knowledgeSearch,
  type KnowledgeHit, type KnowledgeAskOut, type KnowledgeSearchOut,
} from '@/api/ai'
import { isAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const question = ref('')
const loading = ref(false)
const useLlm = ref(true)
const searched = ref(false)
const basicMode = ref(false)
const answer = ref('')
const notice = ref('')
const mode = ref('')
const hits = ref<KnowledgeHit[]>([])
const docCount = ref<number | null>(null)

onMounted(() => {
  void getKnowledgeStatus()
    .then((r) => { docCount.value = typeof r.docs === 'number' ? r.docs : null })
    .catch(() => { /* 知识库扩展未开通时静默，提问时再降级 */ })
})

async function fallback(q: string) {
  basicMode.value = true
  try {
    const r = await aiHelp(q)
    answer.value = r.answer || t('ai.helpNoResult')
    hits.value = (r.sources || []).map((s, i) => ({
      doc_id: 0, title: s.title, seq: i + 1, score: 0,
      excerpt: s.snippet || '', scope: s.source,
    }))
  } catch {
    answer.value = t('ai.helpNoResult')
  }
}

function renderSearchHits(list: KnowledgeHit[]) {
  if (!list.length) return t('ai.helpNoResult')
  return list.map((h, i) => `${i + 1}. 《${h.title}》：${h.excerpt || h.text || ''}`).join('\n\n')
}

async function ask() {
  const q = question.value.trim()
  if (!q || loading.value) return
  loading.value = true
  searched.value = true
  answer.value = ''
  hits.value = []
  notice.value = ''
  mode.value = ''
  try {
    if (basicMode.value) {
      await fallback(q)
      return
    }
    let res: KnowledgeAskOut | KnowledgeSearchOut
    try {
      res = useLlm.value ? await knowledgeAsk(q, true) : await knowledgeSearch(q)
    } catch (e: unknown) {
      if (isAccessDenied(e)) {
        notice.value = t('ai.helpFallback')
        await fallback(q)
        return
      }
      throw e
    }
    if (res.ok === false || res.locked) {
      notice.value = res.error || t('ai.helpFallback')
      await fallback(q)
      return
    }
    const list = res.hits || []
    hits.value = list
    mode.value = res.mode || ''
    const askRes = res as unknown as { answer?: string; note?: string; ai_unavailable?: boolean; ai_hint?: string; ai_disabled?: boolean }
    if (useLlm.value) {
      answer.value = askRes.answer || askRes.note || t('ai.helpNoResult')
      if (askRes.ai_unavailable) notice.value = t('ai.helpDegraded')
      if (askRes.ai_hint) notice.value = t('ai.helpAiHint', { v: askRes.ai_hint })
    } else {
      answer.value = renderSearchHits(list)
      if (list.length) notice.value = t('ai.helpAiDisabled')
    }
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.helpAskFailed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="space-y-3 p-4">
    <div class="rounded-xl bg-white p-4 shadow-sm">
      <div class="flex items-start justify-between gap-2">
        <div>
          <div class="text-base font-semibold text-zinc-800">{{ t('ai.helpTitle') }}</div>
          <div class="mt-1 text-xs text-zinc-500">{{ t('ai.helpSubtitle') }}</div>
        </div>
        <van-tag v-if="basicMode" plain type="warning">{{ t('ai.helpFallbackHint') }}</van-tag>
      </div>
      <div v-if="docCount !== null" class="mt-2 text-[11px] text-zinc-400">{{ t('ai.helpDocCount', { n: docCount }) }}</div>
      <van-field
        v-model="question"
        type="textarea"
        rows="3"
        class="mt-3"
        :placeholder="t('ai.helpPlaceholder')"
        :disabled="loading"
      />
      <div class="mt-2 flex items-center justify-between">
        <div class="flex items-center gap-2 text-xs text-zinc-600">
          <van-switch v-model="useLlm" size="20px" :disabled="loading || basicMode" />
          <span>{{ useLlm ? t('ai.helpUseLlm') : t('ai.helpSearchOnly') }}</span>
        </div>
        <van-button type="primary" size="small" :loading="loading" :disabled="!question.trim()" @click="ask">{{ t('ai.helpAsk') }}</van-button>
      </div>
    </div>

    <div v-if="notice" class="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">{{ notice }}</div>
    <div v-if="mode" class="text-[11px] text-zinc-400">{{ t('ai.helpMode', { v: mode }) }}</div>

    <div v-if="searched && !loading && answer" class="rounded-xl bg-white p-4 shadow-sm">
      <div class="mb-2 text-sm font-medium text-zinc-700">{{ t('ai.helpAnswer') }}</div>
      <div class="whitespace-pre-wrap text-sm text-zinc-600">{{ answer }}</div>
      <div v-if="hits.length" class="mt-3 border-t border-zinc-100 pt-3">
        <div class="mb-1 text-xs text-zinc-500">{{ t('ai.helpSources') }}</div>
        <div v-for="(h, i) in hits" :key="i" class="mb-2 rounded-lg bg-zinc-50 p-2">
          <div class="flex items-center justify-between gap-2">
            <span class="truncate text-xs font-medium text-zinc-700">《{{ h.title }}》</span>
            <span class="shrink-0 text-[10px] text-zinc-400">{{ t('ai.helpScore', { v: (h.score ?? 0).toFixed(2) }) }}</span>
          </div>
          <div v-if="h.excerpt || h.text" class="mt-1 line-clamp-3 text-[11px] text-zinc-500">{{ h.excerpt || h.text }}</div>
          <div class="mt-1 text-[10px] text-zinc-400">{{ t('ai.helpSeq', { n: h.seq }) }}<span v-if="h.scope"> · {{ h.scope }}</span></div>
        </div>
      </div>
    </div>
    <div v-else-if="!searched && !loading" class="rounded-xl bg-white p-6 text-center text-xs text-zinc-400 shadow-sm">
      {{ t('ai.helpEmpty') }}
    </div>
  </div>
</template>
