<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import {
  getAnomalyOptions, getAnomalySummary, handleAlert, interpretAlert, listAiAlerts, runAiAlerts,
  type AlertItem, type AnomalyOptionItem, type AnomalySummary,
} from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
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

const canManage = computed(() => auth.hasPermission('ext.ai_anomaly.manage'))

const SEV_TYPE: Record<string, 'danger' | 'warning' | 'primary'> = { critical: 'danger', high: 'danger', warning: 'warning', mid: 'warning', info: 'primary', low: 'primary' }

function sevText(s?: string) {
  const k = (s || '').toLowerCase()
  if (k === 'critical' || k === 'high') return t('ai.sevCritical')
  if (k === 'warning' || k === 'mid') return t('ai.sevWarning')
  return t('ai.sevInfo')
}
function sevType(s?: string) {
  return SEV_TYPE[(s || '').toLowerCase()] || 'primary'
}

async function load() {
  loading.value = true
  try {
    const [list, sum, opts] = await Promise.all([
      listAiAlerts({
        dim: dim.value || undefined,
        severity: severity.value || undefined,
        status: status.value || undefined,
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

function selectDim(key: string) {
  dim.value = key
  void load()
}
function selectSeverity(key: string) {
  severity.value = key
  void load()
}
function selectStatus(key: string) {
  status.value = key
  void load()
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
  const lines = [
    a.detail,
    a.root_cause ? t('ai.rootCause', { v: a.root_cause }) : '',
    a.suggestion ? t('ai.suggestion', { v: a.suggestion }) : '',
  ].filter(Boolean).join('\n\n')
  await showDialog({ title: a.title, message: lines || t('ai.detailEmpty'), confirmButtonText: t('ai.ok') })
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
        <van-button v-if="canManage" size="small" type="primary" plain :loading="scanning" :disabled="locked" @click="scan">{{ t('ai.scan') }}</van-button>
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
          <van-tag
            v-for="s in severities"
            :key="s.key"
            :plain="severity !== s.key"
            :type="sevType(s.key)"
            size="large"
            class="shrink-0 cursor-pointer"
            @click="selectSeverity(s.key)"
          >{{ sevText(s.key) }}</van-tag>
        </div>
      </div>
      <div v-if="dimensions.length">
        <div class="mb-1 text-[11px] text-zinc-400">{{ t('ai.dimension') }}</div>
        <div class="flex gap-2 overflow-x-auto pb-1">
          <van-tag :plain="dim !== ''" type="primary" size="large" class="shrink-0 cursor-pointer" @click="selectDim('')">{{ t('ai.all') }}</van-tag>
          <van-tag
            v-for="d in dimensions"
            :key="d.key"
            :plain="dim !== d.key"
            type="primary"
            size="large"
            class="shrink-0 cursor-pointer"
            @click="selectDim(d.key)"
          >{{ d.label }}</van-tag>
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
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <van-tag :type="sevType(a.level)" plain>{{ sevText(a.level) }}</van-tag>
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
          <van-button v-if="canManage" size="mini" plain @click.stop="resolveAlert(a)">{{ t('ai.resolve') }}</van-button>
        </div>
      </div>
    </div>
  </div>
</template>
