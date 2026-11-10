<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import {
  batchHandleAlerts, getAlertDetail, getAnomalyOptions, getAnomalySummary,
  handleAlert, interpretAlert, listAiAlerts, runAiAlerts,
  type AlertItem, type AnomalyOptionItem, type AnomalySummary,
} from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const loading = ref(true)
const locked = ref(false)
const scanning = ref(false)
const items = ref<AlertItem[]>([])
const summary = ref<AnomalySummary | null>(null)
const dimensions = ref<AnomalyOptionItem[]>([])
const severities = ref<AnomalyOptionItem[]>([])
const dim = ref('')
const severity = ref('')
const status = ref('all')
const interpreting = ref(0)
const pageLimit = ref(100)
const batchMode = ref(false)
const batching = ref(false)
const selected = ref<number[]>([])

// 详情弹层：列表项只带摘要字段，完整 facts / AI 解读 / 时间戳走 /alerts/{id}
const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<AlertItem | null>(null)
const insight = ref('')
const insightCached = ref(false)
const interpretingDetail = ref(false)
const handlingDetail = ref(false)

const canManage = computed(() => auth.hasPermission('ext.ai_anomaly.manage'))
const hasMore = computed(() => items.value.length >= pageLimit.value && pageLimit.value < 500)
const factRows = computed(() => {
  const f = detail.value?.facts
  if (!f || typeof f !== 'object') return []
  return Object.entries(f).map(([k, v]) => ({ k, v: String(v ?? '-') }))
})

const SEV_TYPE: Record<string, 'danger' | 'warning' | 'primary'> = { critical: 'danger', high: 'danger', warning: 'warning', mid: 'warning', info: 'primary', low: 'primary' }

// 后端 _alert_out 输出 severity，早期前端类型写成 level；这里兼容两种，修掉严重度永远显示"信息"的问题
function sevOf(a: AlertItem) {
  return a.severity || a.level || ''
}
function sevText(s?: string) {
  const k = (s || '').toLowerCase()
  if (k === 'critical' || k === 'high') return t('ai.sevCritical')
  if (k === 'warning' || k === 'mid') return t('ai.sevWarning')
  return t('ai.sevInfo')
}
function sevType(s?: string) {
  return SEV_TYPE[(s || '').toLowerCase()] || 'primary'
}

function statusLabel(st: string) {
  if (st === 'acked') return t('ai.statusAckedLabel')
  if (st === 'resolved') return t('ai.statusResolvedLabel')
  if (st === 'ignored') return t('ai.statusIgnoredLabel')
  return t('ai.statusOpen')
}

async function load() {
  loading.value = true
  try {
    const [list, sum, opts] = await Promise.all([
      listAiAlerts({
        dim: dim.value || undefined,
        severity: severity.value || undefined,
        status: status.value || undefined,
        limit: pageLimit.value,
      }),
      getAnomalySummary().catch(() => null),
      getAnomalyOptions().catch(() => null),
    ])
    items.value = list.items || []
    summary.value = sum
    dimensions.value = opts?.dimensions || []
    severities.value = opts?.severities || []
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

function resetLimit() {
  pageLimit.value = 100
}
function loadMore() {
  if (!hasMore.value) return
  pageLimit.value = Math.min(500, pageLimit.value + 100)
  void load()
}
function selectDim(key: string) {
  dim.value = key
  resetLimit()
  void load()
}
function selectSeverity(key: string) {
  severity.value = key
  resetLimit()
  void load()
}
function selectStatus(key: string) {
  status.value = key
  resetLimit()
  void load()
}

function exportAlertsCsv() {
  try {
    const esc = (v: unknown) => '"' + String(v ?? '').replace(/"/g, '""') + '"'
    const head = [t('ai.detailBasic'), t('ai.detailPhenomenon'), t('ai.dimension'), t('ai.filterSeverity'), t('ai.statusLabel'), t('ai.detailTimes')]
    const rows = items.value.map((a) => [
      a.title, a.detail || '', a.dim_label || '', sevText(sevOf(a)),
      a.status_label || a.status || '', a.last_seen_at || '',
    ].map(esc).join(','))
    const csv = '\uFEFF' + [head.map(esc).join(','), ...rows].join('\r\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `alerts-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    showToast(t('ai.exportDone'))
  } catch {
    showToast(t('ai.exportFailed'))
  }
}

// 预警 → 相关制度：拿维度名（没有就用标题）去资料页搜，别让用户自己猜关键词
function findDocs() {
  const q = (detail.value?.dim_label || detail.value?.title || '').trim()
  detailOpen.value = false
  void router.push({ name: 'aiDocs', query: q ? { q } : {} })
}

async function scan() {
  scanning.value = true
  try {
    const r = await runAiAlerts()
    showToast(t('ai.scanDone', { n: r.events ?? 0 }))
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameAlerts'))) {
      showToast(e instanceof Error ? e.message : t('ai.scanFailed'))
    }
  } finally {
    scanning.value = false
  }
}

async function openAlert(a: AlertItem) {
  detail.value = a
  insight.value = ''
  insightCached.value = false
  detailOpen.value = true
  detailLoading.value = true
  try {
    const r = await getAlertDetail(a.id)
    if (r.found && r.alert) {
      detail.value = r.alert
      insight.value = r.alert.ai_insight || ''
      insightCached.value = !!r.alert.ai_insight
    }
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameAlerts'))) {
      showToast(e instanceof Error ? e.message : t('ai.detailLoadFailed'))
    }
  } finally {
    detailLoading.value = false
  }
}

async function refreshInsight() {
  if (!detail.value || interpretingDetail.value) return
  interpretingDetail.value = true
  try {
    const r = await interpretAlert(detail.value.id, true)
    insight.value = r.insight || r.hint || t('ai.noInterpret')
    insightCached.value = !!r.cached
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameAlerts'))) {
      showToast(e instanceof Error ? e.message : t('ai.interpretFailed'))
    }
  } finally {
    interpretingDetail.value = false
  }
}

async function changeStatus(st: string) {
  if (!detail.value || handlingDetail.value) return
  handlingDetail.value = true
  try {
    await handleAlert(detail.value.id, st)
    detail.value = { ...detail.value, status: st, status_label: statusLabel(st) }
    showToast(t('ai.detailStatusChanged'))
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameAlerts'))) {
      showToast(e instanceof Error ? e.message : t('ai.actionFailed'))
    }
  } finally {
    handlingDetail.value = false
  }
}

async function interpret(a: AlertItem) {
  interpreting.value = a.id
  try {
    const r = await interpretAlert(a.id)
    const text = r.insight || r.hint || t('ai.noInterpret')
    await showDialog({ title: t('ai.aiInterpret'), message: text, confirmButtonText: t('ai.ok') })
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameAlerts'))) {
      showToast(e instanceof Error ? e.message : t('ai.interpretFailed'))
    }
  } finally {
    interpreting.value = 0
  }
}

async function resolveAlert(a: AlertItem) {
  try {
    await showConfirmDialog({ title: t('ai.resolveTitle'), message: t('ai.resolveConfirm', { title: a.title }), confirmButtonText: t('ai.ok') })
  } catch {
    return
  }
  try {
    await handleAlert(a.id, 'resolved')
    showToast(t('ai.resolved'))
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameAlerts'))) {
      showToast(e instanceof Error ? e.message : t('ai.actionFailed'))
    }
  }
}

function toggleSelect(id: number) {
  const i = selected.value.indexOf(id)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(id)
}
function toggleAll() {
  const ids = items.value.map((a) => a.id)
  selected.value = selected.value.length === ids.length ? [] : ids.slice(0, 50)
}
function clearSelection() {
  selected.value = []
}
function closeBatch() {
  batchMode.value = false
  selected.value = []
}

async function doBatch(st: string) {
  if (!selected.value.length) {
    showToast(t('ai.batchEmpty'))
    return
  }
  try {
    await showConfirmDialog({
      title: t('ai.batchMode'),
      message: t('ai.batchConfirm', { n: selected.value.length, v: statusLabel(st) }),
      confirmButtonText: t('ai.ok'),
    })
  } catch {
    return
  }
  batching.value = true
  try {
    const r = await batchHandleAlerts(selected.value, st)
    if (!r.ok) {
      showToast(r.error || t('ai.batchFailed'))
      return
    }
    showToast(r.missing?.length
      ? t('ai.batchPartial', { n: r.total, m: r.missing.length })
      : t('ai.batchDone', { n: r.total }))
    closeBatch()
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameAlerts'))) {
      showToast(e instanceof Error ? e.message : t('ai.batchFailed'))
    }
  } finally {
    batching.value = false
  }
}

onMounted(async () => {
  if (!auth.permissions.length) await auth.fetchMe()
  await load()
})
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-white p-3 shadow-sm">
      <div class="flex items-center justify-between gap-2">
        <div>
          <div class="text-sm font-medium text-zinc-800">{{ t('ai.alertsTitle') }}</div>
          <div class="mt-1 text-[11px] text-zinc-500">{{ t('ai.alertsSubtitle') }}</div>
        </div>
        <div v-if="canManage" class="flex shrink-0 gap-1">
          <van-button size="small" plain :disabled="locked || !items.length" @click="batchMode ? closeBatch() : (batchMode = true)">
            {{ batchMode ? t('ai.batchExit') : t('ai.batchMode') }}
          </van-button>
          <van-button size="small" type="primary" plain :loading="scanning" :disabled="locked" @click="scan">{{ t('ai.scan') }}</van-button>
        </div>
        <van-tag v-else plain type="warning">{{ t('ai.manageOnly') }}</van-tag>
      </div>
      <div v-if="summary" class="mt-3 grid grid-cols-4 gap-2 text-center">
        <div><div class="text-base font-bold text-indigo-600">{{ summary.health_score ?? '-' }}</div><div class="text-[10px] text-zinc-500">{{ t('ai.healthScore') }}</div></div>
        <div><div class="text-base font-bold text-orange-500">{{ summary.total_active ?? 0 }}</div><div class="text-[10px] text-zinc-500">{{ t('ai.activeAlerts') }}</div></div>
        <div><div class="text-base font-bold text-green-600">{{ summary.total_resolved ?? 0 }}</div><div class="text-[10px] text-zinc-500">{{ t('ai.resolvedAlerts') }}</div></div>
        <div><div class="text-base font-bold text-zinc-700">{{ summary.total_events ?? 0 }}</div><div class="text-[10px] text-zinc-500">{{ t('ai.totalEvents') }}</div></div>
      </div>
    </div>

    <div class="space-y-2 rounded-xl bg-white p-3 shadow-sm">
      <div>
        <div class="mb-1 text-[11px] text-zinc-400">{{ t('ai.filterStatus') }}</div>
        <div class="flex gap-2 overflow-x-auto pb-1">
          <van-tag :plain="status !== 'all'" type="primary" size="large" class="shrink-0 cursor-pointer" @click="selectStatus('all')">{{ t('ai.statusAll') }}</van-tag>
          <van-tag :plain="status !== 'open'" type="warning" size="large" class="shrink-0 cursor-pointer" @click="selectStatus('open')">{{ t('ai.statusOpen') }}</van-tag>
          <van-tag :plain="status !== 'acked'" type="primary" size="large" class="shrink-0 cursor-pointer" @click="selectStatus('acked')">{{ t('ai.statusAcked') }}</van-tag>
          <van-tag :plain="status !== 'resolved'" type="success" size="large" class="shrink-0 cursor-pointer" @click="selectStatus('resolved')">{{ t('ai.statusResolved') }}</van-tag>
          <van-tag :plain="status !== 'ignored'" type="default" size="large" class="shrink-0 cursor-pointer" @click="selectStatus('ignored')">{{ t('ai.statusIgnored') }}</van-tag>
        </div>
      </div>
      <div v-if="severities.length">
        <div class="mb-1 text-[11px] text-zinc-400">{{ t('ai.filterSeverity') }}</div>
        <div class="flex gap-2 overflow-x-auto pb-1">
          <van-tag :plain="severity !== ''" type="primary" size="large" class="shrink-0 cursor-pointer" @click="selectSeverity('')">{{ t('ai.sevAll') }}</van-tag>
          <van-tag v-for="s in severities" :key="s.key" :plain="severity !== s.key" :type="sevType(s.key)" size="large" class="shrink-0 cursor-pointer" @click="selectSeverity(s.key)">{{ sevText(s.key) }}</van-tag>
        </div>
      </div>
      <div v-if="dimensions.length">
        <div class="mb-1 text-[11px] text-zinc-400">{{ t('ai.dimension') }}</div>
        <div class="flex gap-2 overflow-x-auto pb-1">
          <van-tag :plain="dim !== ''" type="primary" size="large" class="shrink-0 cursor-pointer" @click="selectDim('')">{{ t('ai.all') }}</van-tag>
          <van-tag v-for="d in dimensions" :key="d.key" :plain="dim !== d.key" type="primary" size="large" class="shrink-0 cursor-pointer" @click="selectDim(d.key)">{{ d.label }}</van-tag>
        </div>
      </div>
      <div class="flex items-center justify-between gap-2 border-t border-zinc-100 pt-2">
        <span class="text-[11px] text-zinc-400">{{ t('ai.alertCount', { n: items.length, m: pageLimit }) }}</span>
        <div class="flex gap-1">
          <van-button size="mini" plain :disabled="!items.length" @click="exportAlertsCsv">{{ t('ai.exportCsv') }}</van-button>
          <van-button v-if="hasMore" size="mini" plain type="primary" @click="loadMore">{{ t('ai.loadMore') }}</van-button>
          <van-tag v-else-if="pageLimit >= 500 && items.length >= 500" plain type="warning">{{ t('ai.limitReached') }}</van-tag>
        </div>
      </div>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>

    <div v-else-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">{{ t('ai.lockedTitle', { name: t('ai.nameAlerts') }) }}</div>
      <div class="mt-2 text-xs text-zinc-400">{{ t('ai.lockedHint') }}</div>
    </div>

    <van-empty v-else-if="!items.length" :description="t('ai.emptyAlerts')" />

    <div v-else class="space-y-2">
      <div v-for="a in items" :key="a.id" class="rounded-xl bg-white p-3 shadow-sm" @click="openAlert(a)">
        <div class="flex items-start justify-between gap-2">
          <div v-if="batchMode" class="shrink-0 pt-1" @click.stop="toggleSelect(a.id)">
            <van-checkbox :model-value="selected.includes(a.id)" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <van-tag :type="sevType(sevOf(a))" plain>{{ sevText(sevOf(a)) }}</van-tag>
              <span class="truncate text-sm font-medium text-zinc-800">{{ a.title }}</span>
            </div>
            <div v-if="a.detail" class="mt-1 line-clamp-2 text-xs text-zinc-500">{{ a.detail }}</div>
            <div class="mt-1 text-[11px] text-zinc-400">
              {{ a.dim_label || '' }}<span v-if="a.entity_name"> · {{ a.entity_name }}</span>
              <span v-if="a.last_seen_at"> · {{ a.last_seen_at }}</span>
            </div>
          </div>
          <van-tag plain type="default">{{ a.status_label || a.status || t('ai.pending') }}</van-tag>
        </div>
        <div v-if="a.status !== 'resolved'" class="mt-2 flex justify-end gap-2">
          <van-button size="mini" plain :loading="interpreting === a.id" @click.stop="interpret(a)">{{ t('ai.aiInterpret') }}</van-button>
          <van-button size="mini" plain @click.stop="openAlert(a)">{{ t('ai.detailTitle') }}</van-button>
          <van-button v-if="canManage" size="mini" plain @click.stop="resolveAlert(a)">{{ t('ai.resolve') }}</van-button>
        </div>
      </div>
    </div>

    <div v-if="batchMode" class="sticky bottom-2 z-10 flex flex-wrap items-center gap-2 rounded-xl bg-white p-3 shadow-lg">
      <van-button size="mini" plain @click="toggleAll">{{ t('ai.batchSelectAll') }}</van-button>
      <van-button size="mini" plain @click="clearSelection">{{ t('ai.batchClear') }}</van-button>
      <span class="text-xs text-zinc-600">{{ t('ai.batchSelected', { n: selected.length }) }}</span>
      <div class="ml-auto flex flex-wrap gap-1">
        <van-button size="mini" plain type="primary" :loading="batching" @click="doBatch('acked')">{{ t('ai.batchAck') }}</van-button>
        <van-button size="mini" plain type="success" :loading="batching" @click="doBatch('resolved')">{{ t('ai.batchResolve') }}</van-button>
        <van-button size="mini" plain :loading="batching" @click="doBatch('ignored')">{{ t('ai.batchIgnore') }}</van-button>
        <van-button size="mini" plain :loading="batching" @click="doBatch('open')">{{ t('ai.batchReopen') }}</van-button>
      </div>
    </div>

    <van-popup v-model:show="detailOpen" position="bottom" round class="pb-safe" :style="{ height: '80%' }">
      <div class="flex h-full flex-col">
        <div class="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
          <div class="text-sm font-medium text-zinc-800">{{ t('ai.detailTitle') }}</div>
          <div class="flex shrink-0 gap-1">
            <van-button size="mini" plain type="primary" @click="findDocs">{{ t('ai.alertFindDocs') }}</van-button>
            <van-button size="mini" plain @click="detailOpen = false">{{ t('ai.close') }}</van-button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto px-4 py-3">
          <div v-if="detailLoading" class="py-8 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>
          <template v-else-if="detail">
            <div class="flex flex-wrap items-center gap-2">
              <van-tag :type="sevType(sevOf(detail))" plain>{{ sevText(sevOf(detail)) }}</van-tag>
              <van-tag plain type="primary">{{ detail.dim_label || detail.dim || '-' }}</van-tag>
              <van-tag plain type="default">{{ detail.status_label || detail.status || t('ai.pending') }}</van-tag>
            </div>
            <div class="mt-2 text-base font-medium text-zinc-800">{{ detail.title }}</div>
            <div class="mt-1 text-[11px] text-zinc-400">
              {{ detail.code || '-' }} · {{ t('ai.statusLabel') }} {{ detail.score ?? '-' }}
              <span v-if="detail.entity_name"> · {{ detail.entity_name }}</span>
            </div>
            <div class="mt-3 space-y-2">
              <div v-if="detail.detail" class="rounded-lg bg-zinc-50 p-3">
                <div class="text-xs font-medium text-zinc-600">{{ t('ai.detailPhenomenon') }}</div>
                <div class="mt-1 whitespace-pre-wrap text-xs text-zinc-600">{{ detail.detail }}</div>
              </div>
              <div v-if="detail.root_cause" class="rounded-lg bg-zinc-50 p-3">
                <div class="text-xs font-medium text-zinc-600">{{ t('ai.detailRootCause') }}</div>
                <div class="mt-1 whitespace-pre-wrap text-xs text-zinc-600">{{ detail.root_cause }}</div>
              </div>
              <div v-if="detail.suggestion" class="rounded-lg bg-zinc-50 p-3">
                <div class="text-xs font-medium text-zinc-600">{{ t('ai.detailSuggestion') }}</div>
                <div class="mt-1 whitespace-pre-wrap text-xs text-zinc-600">{{ detail.suggestion }}</div>
              </div>
              <div v-if="factRows.length" class="rounded-lg bg-zinc-50 p-3">
                <div class="text-xs font-medium text-zinc-600">{{ t('ai.detailFacts') }}</div>
                <div v-for="f in factRows" :key="f.k" class="mt-1 text-xs text-zinc-600">{{ f.k }}：{{ f.v }}</div>
              </div>
              <div class="text-[11px] text-zinc-400">
                {{ t('ai.detailTimes') }}：{{ detail.first_seen_at || '-' }} / {{ detail.last_seen_at || '-' }}
              </div>
            </div>
            <div class="mt-4 border-t border-zinc-100 pt-3">
              <div class="flex items-center justify-between gap-2">
                <div class="text-xs font-medium text-zinc-700">{{ t('ai.detailAiInsight') }}</div>
                <van-button size="mini" plain type="primary" :loading="interpretingDetail" @click="refreshInsight">
                  {{ insight ? t('ai.detailRefresh') : t('ai.detailGenerate') }}
                </van-button>
              </div>
              <div v-if="insightCached" class="mt-1 text-[10px] text-zinc-400">
                {{ t('ai.detailInsightCached') }}<span v-if="detail.ai_insight_at"> · {{ detail.ai_insight_at }}</span>
              </div>
              <div v-if="insight" class="mt-2 whitespace-pre-wrap rounded-lg bg-indigo-50 p-3 text-xs leading-relaxed text-indigo-900">{{ insight }}</div>
              <div v-else class="mt-2 text-xs text-zinc-400">{{ t('ai.noInterpret') }}</div>
            </div>
            <div v-if="canManage" class="mt-4 border-t border-zinc-100 pt-3">
              <div class="mb-2 text-xs font-medium text-zinc-700">{{ t('ai.detailStatus') }}</div>
              <div class="flex flex-wrap gap-2">
                <van-button size="small" plain type="primary" :loading="handlingDetail" @click="changeStatus('acked')">{{ t('ai.detailAck') }}</van-button>
                <van-button size="small" plain type="success" :loading="handlingDetail" @click="changeStatus('resolved')">{{ t('ai.detailResolve') }}</van-button>
                <van-button size="small" plain :loading="handlingDetail" @click="changeStatus('ignored')">{{ t('ai.detailIgnore') }}</van-button>
                <van-button v-if="detail.status !== 'open'" size="small" plain :loading="handlingDetail" @click="changeStatus('open')">{{ t('ai.detailReopen') }}</van-button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </van-popup>
  </div>
</template>
