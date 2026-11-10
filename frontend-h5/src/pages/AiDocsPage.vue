<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import {
  getKnowledgeDoc, listKnowledgeDocs, type KnowledgeDoc, type KnowledgeDocItem,
} from '@/api/ai'
import { copyText as copyToClipboard } from '@/utils/clipboard'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const loading = ref(true)
const locked = ref(false)
const items = ref<KnowledgeDocItem[]>([])
const total = ref(0)
const page = ref(1)
const loadingMore = ref(false)
const keyword = ref('')
const activeScope = ref('')
const scopes = ref<string[]>([])

const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<KnowledgeDoc | null>(null)

// 业务域标签由后端按文档聚合下发（逗号分隔），这里只做展示用的去重收集
function collectScopes(list: KnowledgeDocItem[]) {
  const set = new Set(scopes.value)
  for (const it of list) {
    for (const raw of (it.scope || '').split(',')) {
      const v = raw.trim()
      if (v) set.add(v)
    }
  }
  scopes.value = Array.from(set).slice(0, 12)
}

async function load(reset = true) {
  if (reset) {
    loading.value = true
    page.value = 1
  }
  try {
    const r = await listKnowledgeDocs({
      q: keyword.value.trim() || undefined,
      scope: activeScope.value || undefined,
      page: page.value,
      page_size: 20,
    })
    const list = r.items || []
    items.value = reset ? list : [...items.value, ...list]
    total.value = r.total || 0
    collectScopes(list)
    locked.value = false
  } catch (e: unknown) {
    if (reset) items.value = []
    if (isAccessDenied(e)) {
      locked.value = true
    } else if (!handleExtensionLocked(e, t('ai.nameKnowledge'))) {
      showToast(e instanceof Error ? e.message : t('ai.docsLoadFailed'))
    }
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || items.value.length >= total.value) return
  loadingMore.value = true
  page.value += 1
  await load(false)
  loadingMore.value = false
}

function pickScope(s: string) {
  activeScope.value = activeScope.value === s ? '' : s
  void load()
}

async function openDoc(id: number) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const r = await getKnowledgeDoc(id)
    if (r.ok === false) {
      showToast(r.error || t('ai.docsLoadFailed'))
      detailOpen.value = false
      return
    }
    detail.value = r
  } catch (e: unknown) {
    detailOpen.value = false
    showToast(e instanceof Error ? e.message : t('ai.docsLoadFailed'))
  } finally {
    detailLoading.value = false
  }
}

async function copyDetail() {
  const content = detail.value?.content || ''
  if (!content) return
  const done = await copyToClipboard(content)
  showToast(done ? t('ai.docsCopied') : t('ai.copyFailed'))
}

const detailMeta = computed(() => {
  const d = detail.value
  if (!d) return ''
  return [
    d.source ? `《${d.source}》` : '',
    d.scope || '',
    d.chunk_count ? t('ai.docsChunks', { n: d.chunk_count }) : '',
    d.updated_at ? t('ai.docsUpdated', { v: d.updated_at }) : '',
  ].filter(Boolean).join(' · ')
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-white p-3 shadow-sm">
      <div class="text-sm font-medium text-zinc-800">{{ t('ai.docsTitle') }}</div>
      <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ t('ai.docsSubtitle') }}</div>
      <div class="mt-2 flex items-center gap-2">
        <van-field
          v-model="keyword"
          :placeholder="t('ai.docsSearchPlaceholder')"
          class="!min-w-0 !flex-1 !px-0"
          @keyup.enter="load()"
        />
        <van-button size="small" type="primary" plain @click="load()">{{ t('ai.docsSearch') }}</van-button>
      </div>
      <div v-if="total" class="mt-2 text-[11px] text-zinc-400">{{ t('ai.docsTotal', { n: total }) }}</div>
      <div v-if="scopes.length" class="mt-2 flex flex-wrap gap-1">
        <span
          class="cursor-pointer rounded-full border px-2 py-0.5 text-[11px]"
          :class="activeScope === '' ? 'border-indigo-500 text-indigo-600' : 'border-zinc-200 text-zinc-500'"
          @click="pickScope('')"
        >{{ t('ai.docsScopeAll') }}</span>
        <span
          v-for="s in scopes"
          :key="s"
          class="cursor-pointer rounded-full border px-2 py-0.5 text-[11px]"
          :class="activeScope === s ? 'border-indigo-500 text-indigo-600' : 'border-zinc-200 text-zinc-500'"
          @click="pickScope(s)"
        >{{ s }}</span>
      </div>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>

    <div v-else-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">{{ t('ai.lockedTitle', { name: t('ai.nameKnowledge') }) }}</div>
      <div class="mt-2 text-xs text-zinc-400">{{ t('ai.lockedHint') }}</div>
    </div>

    <van-empty v-else-if="!items.length" :description="t('ai.docsEmpty')" />

    <template v-else>
      <div class="space-y-2">
        <div
          v-for="d in items"
          :key="d.id"
          class="rounded-xl bg-white p-3 shadow-sm active:bg-zinc-50"
          @click="openDoc(d.id)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium text-zinc-800">{{ d.title }}</div>
              <div class="mt-1 flex flex-wrap items-center gap-1">
                <span v-if="d.source" class="text-[10px] text-zinc-400">《{{ d.source }}》</span>
                <van-tag
                  v-for="s in (d.scope || '').split(',').filter(Boolean)"
                  :key="s"
                  plain
                  type="primary"
                >{{ s.trim() }}</van-tag>
              </div>
              <div class="mt-1 text-[10px] text-zinc-400">
                {{ d.updated_at || '' }}<span v-if="d.content_len"> · {{ t('ai.docsContentLen', { n: d.content_len }) }}</span>
              </div>
            </div>
            <van-tag plain :type="d.vectorized ? 'success' : 'warning'" class="shrink-0">
              {{ d.vectorized ? t('ai.docsVectorized') : t('ai.docsNotVectorized') }}
            </van-tag>
          </div>
        </div>
      </div>
      <div v-if="items.length < total" class="py-2 text-center">
        <van-button size="mini" plain :loading="loadingMore" @click="loadMore">{{ t('ai.loadMore') }}</van-button>
      </div>
    </template>

    <van-popup v-model:show="detailOpen" position="bottom" round class="pb-safe" :style="{ height: '85%' }">
      <div class="flex items-center justify-between gap-2 border-b border-zinc-100 px-4 py-3">
        <div class="min-w-0 flex-1 truncate text-sm font-medium text-zinc-800">{{ detail?.title || t('ai.docsDetail') }}</div>
        <div class="flex shrink-0 gap-1">
          <van-button size="mini" plain :disabled="!detail?.content" @click="copyDetail">{{ t('ai.copy') }}</van-button>
          <van-button size="mini" plain @click="detailOpen = false">{{ t('ai.ok') }}</van-button>
        </div>
      </div>
      <div class="h-[calc(100%-49px)] overflow-y-auto px-4 py-3">
        <div v-if="detailLoading" class="py-8 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>
        <template v-else-if="detail">
          <div class="mb-2 text-[10px] text-zinc-400">{{ detailMeta }}</div>
          <div class="whitespace-pre-wrap break-words text-sm leading-relaxed text-zinc-700">{{ detail.content }}</div>
        </template>
        <van-empty v-else :description="t('ai.docsEmpty')" />
      </div>
    </van-popup>
  </div>
</template>
