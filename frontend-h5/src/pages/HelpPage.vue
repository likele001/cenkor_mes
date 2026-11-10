<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import {
  aiHelp, getKnowledgeStatus, knowledgeAsk, knowledgeSearch, listKnowledgeLogs,
  type KnowledgeHit, type KnowledgeAskOut, type KnowledgeLog, type KnowledgeSearchOut,
} from '@/api/ai'
import { copyText as copyToClipboard } from '@/utils/clipboard'
import { isAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()
const router = useRouter()

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
const usage = ref<{ i: number; o: number; m: string } | null>(null)

const HISTORY_KEY = 'cenkormes_h5_ai_help_history'
type HelpHistoryItem = { q: string; a: string; mode: string; at: string }
const history = ref<HelpHistoryItem[]>([])
const serverOpen = ref(false)
const serverLoading = ref(false)
const serverLogs = ref<KnowledgeLog[]>([])

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    history.value = Array.isArray(parsed) ? parsed.slice(0, 20) : []
  } catch {
    history.value = []
  }
}

// 问答历史只落在本人浏览器，避免服务端 /logs 里的全局日志跨账号可见
function pushHistory(q: string, a: string) {
  const item: HelpHistoryItem = {
    q, a, mode: mode.value, at: new Date().toLocaleString(),
  }
  const next = [item, ...history.value.filter((h) => h.q !== q)].slice(0, 20)
  history.value = next
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
  } catch {
    // 隐私模式 / 配额不足：内存里仍可用，忽略持久化失败
  }
}

function replay(h: HelpHistoryItem) {
  question.value = h.q
  answer.value = h.a
  mode.value = h.mode || ''
  usage.value = null
  hits.value = []
  notice.value = ''
  searched.value = true
}

function clearHistory() {
  history.value = []
  try {
    localStorage.removeItem(HISTORY_KEY)
  } catch {
    // 忽略
  }
  showToast(t('ai.helpHistoryCleared'))
}

// 服务端只留问题与命中数（无答案），换设备也能看到自己问过什么
async function openServerHistory() {
  serverOpen.value = true
  serverLoading.value = true
  try {
    const r = await listKnowledgeLogs({ mine: 1, page_size: 20 })
    serverLogs.value = r.items || []
  } catch {
    serverLogs.value = []
  } finally {
    serverLoading.value = false
  }
}

async function replayServer(l: KnowledgeLog) {
  serverOpen.value = false
  question.value = l.query_text || ''
  if (!question.value) return
  await ask()
}

onMounted(() => {
  loadHistory()
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

// 贴工单/群里时通常只要那一段，整条答案太长
async function copyHit(h: KnowledgeHit) {
  const text = [h.title ? `《${h.title}》` : '', h.excerpt || h.text || ''].filter(Boolean).join('\n')
  if (!text.trim()) return
  const done = await copyToClipboard(text)
  showToast(done ? t('ai.copied') : t('ai.copyFailed'))
}

// 依据来源直达全文：答案里的《文档名》要能点开，不然还得自己去资料页翻
function openSourceDoc(h: KnowledgeHit) {
  if (!h.doc_id) return
  void router.push({ name: 'aiDocs', query: { doc: String(h.doc_id) } })
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
  usage.value = null
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
    const askRes = res as unknown as {
      answer?: string
      note?: string
      ai_unavailable?: boolean
      ai_hint?: string
      ai_disabled?: boolean
      tokens_in?: number | null
      tokens_out?: number | null
      ai_model?: string
    }
    if (useLlm.value) {
      answer.value = askRes.answer || askRes.note || t('ai.helpNoResult')
      if (askRes.ai_unavailable) notice.value = t('ai.helpDegraded')
      if (askRes.ai_hint) notice.value = t('ai.helpAiHint', { v: askRes.ai_hint })
      if (askRes.tokens_in || askRes.tokens_out) {
        usage.value = { i: askRes.tokens_in ?? 0, o: askRes.tokens_out ?? 0, m: askRes.ai_model || '' }
      }
    } else {
      answer.value = renderSearchHits(list)
      if (list.length) notice.value = t('ai.helpAiDisabled')
    }
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.helpAskFailed'))
  } finally {
    loading.value = false
    if (answer.value) pushHistory(q, answer.value)
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
      <div v-if="usage" class="mt-2 text-[10px] text-zinc-400">
        <span v-if="usage.m">{{ t('ai.usageModel', { m: usage.m }) }} · </span>{{ t('ai.usageTokens', { i: usage.i, o: usage.o }) }}
      </div>
      <div v-if="hits.length" class="mt-3 border-t border-zinc-100 pt-3">
        <div class="mb-1 text-xs text-zinc-500">{{ t('ai.helpSources') }}</div>
        <div v-for="(h, i) in hits" :key="i" class="mb-2 rounded-lg bg-zinc-50 p-2">
          <div class="flex items-center justify-between gap-2">
            <span class="truncate text-xs font-medium text-zinc-700">《{{ h.title }}》</span>
            <span class="shrink-0 text-[10px] text-zinc-400">{{ t('ai.helpScore', { v: (h.score ?? 0).toFixed(2) }) }}</span>
          </div>
          <div v-if="h.excerpt || h.text" class="mt-1 line-clamp-3 text-[11px] text-zinc-500">{{ h.excerpt || h.text }}</div>
          <div class="mt-1 flex items-center justify-between gap-2">
            <div class="text-[10px] text-zinc-400">{{ t('ai.helpSeq', { n: h.seq }) }}<span v-if="h.scope"> · {{ h.scope }}</span></div>
            <div class="flex shrink-0 gap-1">
              <van-button size="mini" plain @click="copyHit(h)">{{ t('ai.helpCopySnippet') }}</van-button>
              <van-button v-if="h.doc_id" size="mini" plain type="primary" @click="openSourceDoc(h)">
                {{ t('ai.helpOpenDoc') }}
              </van-button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="!searched && !loading" class="rounded-xl bg-white p-6 text-center text-xs text-zinc-400 shadow-sm">
      {{ t('ai.helpEmpty') }}
    </div>

    <div v-if="history.length" class="rounded-xl bg-white p-4 shadow-sm">
      <div class="flex items-center justify-between gap-2">
        <div class="text-sm font-medium text-zinc-700">{{ t('ai.helpHistory') }}</div>
        <div class="flex gap-1">
          <van-button size="mini" plain @click="openServerHistory">{{ t('ai.helpServerHistory') }}</van-button>
          <van-button size="mini" plain @click="clearHistory">{{ t('ai.helpHistoryClear') }}</van-button>
        </div>
      </div>
      <div class="mt-1 text-[10px] text-zinc-400">{{ t('ai.helpHistoryLocal') }}</div>
      <div class="mt-2 space-y-2">
        <div
          v-for="(h, i) in history"
          :key="i"
          class="cursor-pointer rounded-lg bg-zinc-50 p-2 active:bg-zinc-100"
          @click="replay(h)"
        >
          <div class="truncate text-xs text-zinc-700">{{ h.q }}</div>
          <div class="mt-1 line-clamp-2 text-[11px] text-zinc-500">{{ h.a }}</div>
          <div class="mt-1 text-[10px] text-zinc-400">{{ h.at }}</div>
        </div>
      </div>
    </div>
    <van-popup v-model:show="serverOpen" position="bottom" round class="pb-safe" :style="{ height: '60%' }">
      <div class="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <div class="text-sm font-medium text-zinc-800">{{ t('ai.helpServerHistory') }}</div>
        <van-button size="mini" plain @click="openServerHistory">{{ t('ai.refresh') }}</van-button>
      </div>
      <div class="px-4 pb-1 pt-2 text-[10px] leading-relaxed text-zinc-400">{{ t('ai.helpServerHistoryHint') }}</div>
      <div class="h-[calc(100%-80px)] overflow-y-auto px-3 py-2">
        <div v-if="serverLoading" class="py-8 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>
        <van-empty v-else-if="!serverLogs.length" :description="t('ai.helpServerEmpty')" />
        <div v-else class="space-y-2">
          <div
            v-for="l in serverLogs"
            :key="l.id"
            class="cursor-pointer rounded-xl bg-zinc-50 p-3 active:bg-zinc-100"
            @click="replayServer(l)"
          >
            <div class="truncate text-xs text-zinc-800">{{ l.query_text }}</div>
            <div class="mt-1 flex items-center gap-2 text-[10px] text-zinc-400">
              <span>{{ l.created_at || '' }}</span>
              <span v-if="l.mode">· {{ l.mode }}</span>
              <span>· {{ t('ai.helpHitCount', { n: l.hit_count ?? 0 }) }}</span>
              <span class="ml-auto text-indigo-500">{{ t('ai.helpReplay') }}</span>
            </div>
          </div>
        </div>
      </div>
    </van-popup>

  </div>
</template>
