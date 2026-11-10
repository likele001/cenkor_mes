<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import {
  analyzeInsight, batchDeleteInsightRuns, deleteInsightRun, getInsightRun, listAiInsight,
  listInsightAxes, listInsightRuns,
  type AiInsightItem, type InsightAxis, type InsightRun,
} from '@/api/ai'
import { copyText as copyToClipboard } from '@/utils/clipboard'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const loading = ref(true)
const locked = ref(false)
const items = ref<AiInsightItem[]>([])
const axes = ref<InsightAxis[]>([])
const generatedAt = ref('')
const analyzing = ref('')

const runsOpen = ref(false)
const runsLoading = ref(false)
const runs = ref<InsightRun[]>([])
const selectMode = ref(false)
const selected = ref<number[]>([])

function descOf(code: string) {
  return axes.value.find((a) => a.code === code)?.desc || ''
}

function joinLines(parts: Array<string | undefined>) {
  return parts.filter(Boolean).join('\n\n')
}

async function load() {
  loading.value = true
  try {
    const [r, ax] = await Promise.all([listAiInsight(), listInsightAxes().catch(() => null)])
    items.value = r.items || []
    generatedAt.value = r.generated_at || ''
    axes.value = ax?.axes || []
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

async function openRuns() {
  runsOpen.value = true
  runsLoading.value = true
  try {
    const r = await listInsightRuns({ page_size: 30 })
    runs.value = r.items || []
  } catch {
    runs.value = []
  } finally {
    runsLoading.value = false
  }
}

async function openRun(id: number) {
  try {
    const r = await getInsightRun(id)
    if (r.ok === false) {
      showToast(r.error || t('ai.noAnalysis'))
      return
    }
    const text = joinLines([
      r.summary || r.rule_summary || r.report,
      r.risks?.length ? `${t('ai.risks')}：${r.risks.join('；')}` : '',
      r.suggestions?.length ? `${t('ai.suggestions')}：${r.suggestions.join('；')}` : '',
    ]) || t('ai.noAnalysis')
    await showDialog({ title: t('ai.runDetail'), message: text, confirmButtonText: t('ai.ok') })
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameInsight'))) {
      showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
    }
  }
}

async function copyRun(id: number) {
  try {
    const r = await getInsightRun(id)
    const text = joinLines([
      r.summary || r.rule_summary || r.report,
      r.risks?.length ? `${t('ai.risks')}：${r.risks.join('；')}` : '',
      r.suggestions?.length ? `${t('ai.suggestions')}：${r.suggestions.join('；')}` : '',
    ])
    if (!text) {
      showToast(t('ai.noAnalysis'))
      return
    }
    const done = await copyToClipboard(text)
    showToast(done ? t('ai.copied') : t('ai.copyFailed'))
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
  }
}

async function removeRun(id: number) {
  try {
    await showConfirmDialog({
      title: t('ai.runDelete'),
      message: t('ai.runDeleteConfirm'),
      confirmButtonText: t('ai.delete'),
    })
  } catch {
    return
  }
  try {
    const r = await deleteInsightRun(id)
    if (r.ok === false) {
      showToast(r.error || t('ai.actionFailed'))
      return
    }
    showToast(t('ai.runDeleted'))
    await openRuns()
    await load()
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.actionFailed'))
  }
}

function exportRuns() {
  if (!runs.value.length) {
    showToast(t('ai.runExportEmpty'))
    return
  }
  try {
    const esc = (v: unknown) => '"' + String(v ?? '').replace(/"/g, '""') + '"'
    const head = [
      t('ai.runColTime'), t('ai.runColAxis'), t('ai.runColDays'), t('ai.runColExcerpt'),
    ]
    const rows = runs.value.map((r) => [
      r.created_at || '',
      r.axis_name || r.axis,
      r.days ?? '',
      (r.excerpt || '').replace(/\s+/g, ' '),
    ].map(esc).join(','))
    const csv = '\uFEFF' + [head.map(esc).join(','), ...rows].join('\r\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `insight-runs-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    showToast(t('ai.exportDone'))
  } catch {
    showToast(t('ai.exportFailed'))
  }
}

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  selected.value = []
}

function toggleSelect(id: number) {
  const i = selected.value.indexOf(id)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(id)
}

function toggleAll() {
  selected.value = selected.value.length === runs.value.length ? [] : runs.value.map((r) => r.id)
}

function onRunClick(id: number) {
  if (selectMode.value) toggleSelect(id)
  else void openRun(id)
}

async function removeSelected() {
  if (!selected.value.length) return
  try {
    await showConfirmDialog({
      title: t('ai.runBatchDelete'),
      message: t('ai.runBatchConfirm', { n: selected.value.length }),
      confirmButtonText: t('ai.delete'),
    })
  } catch {
    return
  }
  try {
    const r = await batchDeleteInsightRuns(selected.value)
    if (r.ok === false) {
      showToast(r.error || t('ai.actionFailed'))
      return
    }
    const done = r.succeeded?.length || 0
    const miss = r.missing?.length || 0
    showToast(miss ? t('ai.runBatchPartial', { n: done, m: miss }) : t('ai.runBatchDone', { n: done }))
    selectMode.value = false
    selected.value = []
    await openRuns()
    await load()
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : t('ai.actionFailed'))
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
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0 flex-1">
          <div class="text-sm font-medium text-zinc-800">{{ t('ai.insightTitle') }}</div>
          <div class="mt-1 text-[11px] text-zinc-500">{{ t('ai.insightSubtitle') }}</div>
          <div v-if="generatedAt" class="mt-1 text-[11px] text-zinc-400">{{ t('ai.dataTime', { v: generatedAt }) }}</div>
        </div>
        <van-button size="mini" plain @click="openRuns">{{ t('ai.runs') }}</van-button>
      </div>
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
            <div v-if="descOf(it.axis)" class="mt-1 text-[11px] text-zinc-400">{{ descOf(it.axis) }}</div>
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

    <van-popup v-model:show="runsOpen" position="bottom" round class="pb-safe" :style="{ height: '60%' }">
      <div class="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <div class="text-sm font-medium text-zinc-800">{{ t('ai.runs') }}</div>
        <div class="flex shrink-0 gap-1">
          <van-button size="mini" plain @click="toggleSelectMode">
            {{ selectMode ? t('ai.selectCancel') : t('ai.select') }}
          </van-button>
          <van-button size="mini" plain :disabled="!runs.length" @click="exportRuns">{{ t('ai.runExport') }}</van-button>
          <van-button size="mini" plain @click="openRuns">{{ t('ai.refresh') }}</van-button>
        </div>
      </div>
      <div
        v-if="selectMode"
        class="flex items-center justify-between gap-2 border-b border-zinc-100 px-4 py-2 text-[11px] text-zinc-500"
      >
        <span class="cursor-pointer text-indigo-600" @click="toggleAll">
          {{ selected.length === runs.length && runs.length ? t('ai.selectNone') : t('ai.selectAll') }}
        </span>
        <span>{{ t('ai.selectedCount', { n: selected.length }) }}</span>
        <van-button size="mini" type="danger" plain :disabled="!selected.length" @click="removeSelected">
          {{ t('ai.runBatchDelete') }}
        </van-button>
      </div>
      <div
        class="overflow-y-auto px-3 py-2"
        :class="selectMode ? 'h-[calc(100%-93px)]' : 'h-[calc(100%-49px)]'"
      >
        <div v-if="runsLoading" class="py-8 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>
        <van-empty v-else-if="!runs.length" :description="t('ai.noRuns')" />
        <div v-else class="space-y-2">
          <div
            v-for="r in runs"
            :key="r.id"
            class="rounded-xl bg-zinc-50 p-3"
            :class="selected.includes(r.id) ? 'ring-2 ring-indigo-400' : ''"
            @click="onRunClick(r.id)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm text-zinc-800">{{ r.axis_name || r.axis }}</div>
                <div v-if="r.excerpt" class="mt-1 line-clamp-2 text-[11px] text-zinc-500">{{ r.excerpt }}</div>
              </div>
              <div v-if="!selectMode" class="flex shrink-0 flex-col gap-1">
                <van-button size="mini" plain @click.stop="openRun(r.id)">{{ t('ai.view') }}</van-button>
                <van-button size="mini" plain @click.stop="copyRun(r.id)">{{ t('ai.runCopy') }}</van-button>
                <van-button size="mini" plain type="danger" @click.stop="removeRun(r.id)">{{ t('ai.runDelete') }}</van-button>
              </div>
              <van-icon
                v-else
                class="shrink-0 text-lg"
                :name="selected.includes(r.id) ? 'checked' : 'circle'"
                :color="selected.includes(r.id) ? '#4f46e5' : '#d4d4d8'"
              />
            </div>
            <div class="mt-1 text-[10px] text-zinc-400">{{ r.created_at || '' }}</div>
          </div>
        </div>
      </div>
    </van-popup>
  </div>
</template>
