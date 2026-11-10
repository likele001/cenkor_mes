<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showConfirmDialog, showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import {
  employeeOverview, getAiExtensionStatus, getAnomalySummary,
  type AiExtensionStatus,
} from '@/api/ai'
import { copyText as copyToClipboard } from '@/utils/clipboard'

type Entry = {
  path: string
  icon: string
  color: string
  title: string
  desc: string
  perm?: string
  ext?: string
}

type BlockState = 'missing' | 'disabled' | 'denied' | 'local' | ''

const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()

const statuses = ref<Record<string, AiExtensionStatus>>({})
const checking = ref(false)
const checked = ref(false)

const entries = computed<Entry[]>(() => [
  { path: '/ai-assistant', icon: '🤖', color: 'text-indigo-500', title: t('ai.cardAssistantTitle'), desc: t('ai.cardAssistantDesc'), perm: 'ext.ai_assistant.view', ext: 'ai_assistant' },
  { path: '/ai-alerts', icon: '⚠️', color: 'text-orange-500', title: t('ai.cardAlertsTitle'), desc: t('ai.cardAlertsDesc'), perm: 'ext.ai_anomaly.view', ext: 'ai_anomaly' },
  { path: '/ai-employees', icon: '💬', color: 'text-green-500', title: t('ai.cardEmployeesTitle'), desc: t('ai.cardEmployeesDesc'), perm: 'ext.ai_employee.view', ext: 'ai_employee' },
  { path: '/ai-insight', icon: '📊', color: 'text-cyan-500', title: t('ai.cardInsightTitle'), desc: t('ai.cardInsightDesc'), perm: 'ext.ai_insight.view', ext: 'ai_insight' },
  { path: '/ai-scene', icon: '📝', color: 'text-amber-500', title: t('ai.cardSceneTitle'), desc: t('ai.cardSceneDesc'), perm: 'ext.ai_scene_reports.view', ext: 'ai_scene_reports' },
  { path: '/ai-docs', icon: '📚', color: 'text-sky-500', title: t('ai.cardDocsTitle'), desc: t('ai.cardDocsDesc'), perm: 'ext.ai_knowledge.view', ext: 'ai_knowledge' },
  { path: '/help', icon: '💡', color: 'text-blue-500', title: t('ai.cardHelpTitle'), desc: t('ai.cardHelpDesc') },
])

const summary = computed(() => {
  const list = entries.value.filter((e) => e.ext)
  return { ready: list.filter((e) => !blockedState(e)).length, total: list.length }
})

// 最近使用只记本机、只记成功进入的入口；本机不记角色/权限，换人登录也不会越权（仍走 blockedState 校验）
const RECENT_KEY = 'cenkormes_h5_ai_hub_recent'
const recentPaths = ref<string[]>([])

function loadRecent() {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    recentPaths.value = Array.isArray(parsed)
      ? parsed.filter((x) => typeof x === 'string').slice(0, 4)
      : []
  } catch {
    recentPaths.value = []
  }
}

function pushRecent(path: string) {
  const next = [path, ...recentPaths.value.filter((p) => p !== path)].slice(0, 4)
  recentPaths.value = next
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {
    // 隐私模式 / 配额不足：只在内存里留着，不影响进入页面
  }
}

function clearRecent() {
  recentPaths.value = []
  try {
    localStorage.removeItem(RECENT_KEY)
  } catch {
    // 忽略
  }
}

const recentEntries = computed<Entry[]>(() =>
  recentPaths.value
    .map((p) => entries.value.find((e) => e.path === p))
    .filter((e): e is Entry => !!e && !blockedState(e)),
)

// 今日概览：只向「当前用户确实能进」的扩展取数；任一接口失败就当作没这项，
// 不能让某个扩展挂掉把首页拖成白屏（员工端最需要的是能点进去，而不是看指标）
const overview = ref<{ health: number | null; active: number | null; runs: number | null }>({
  health: null,
  active: null,
  runs: null,
})

const hasOverview = computed(
  () => overview.value.health !== null || overview.value.active !== null || overview.value.runs !== null,
)

function healthTone(score: number) {
  if (score >= 80) return 'text-emerald-600'
  if (score >= 60) return 'text-amber-600'
  return 'text-rose-600'
}

function entryOf(path: string) {
  return entries.value.find((x) => x.path === path)
}

function allowed(path: string) {
  const e = entryOf(path)
  return !!e && !blockedState(e)
}

function goPath(path: string) {
  const e = entryOf(path)
  if (e) go(e)
}

async function loadOverview() {
  // 先清空：权限被收回后不能还留着上一次的数字
  overview.value = { health: null, active: null, runs: null }
  const jobs: Promise<void>[] = []
  if (allowed('/ai-alerts')) {
    jobs.push((async () => {
      try {
        const sum = await getAnomalySummary()
        overview.value.health = typeof sum.health_score === 'number' ? sum.health_score : null
        overview.value.active = typeof sum.total_active === 'number' ? sum.total_active : null
      } catch {
        // 预警扩展不可用：概览少一项，不影响进入
      }
    })())
  }
  if (allowed('/ai-employees')) {
    jobs.push((async () => {
      try {
        const o = await employeeOverview()
        overview.value.runs = typeof o.runs_last_24h === 'number' ? o.runs_last_24h : null
      } catch {
        // 数字员工扩展不可用：同上
      }
    })())
  }
  await Promise.all(jobs)
}

// 后端状态不可用时退回本地权限判断，避免接口异常把整页卡死
function localLocked(e: Entry) {
  return !!e.perm && auth.permissions.length > 0 && !auth.hasPermission(e.perm)
}

function blockedState(e: Entry): BlockState {
  if (!e.ext) return ''
  if (checked.value) {
    const s = statuses.value[e.ext]
    if (s) {
      if (!s.installed) return 'missing'
      if (!s.enabled) return 'disabled'
      if (!s.granted) return 'denied'
      return ''
    }
  }
  return localLocked(e) ? 'local' : ''
}

// 拿「到底缺哪条权限」：优先后端下发的 permission（与真实校验一致），退回落本地常量
function permOf(e: Entry): string {
  const s = e.ext ? statuses.value[e.ext] : undefined
  return e.perm || s?.permission || ''
}

// 未授权不该只回一句「无权限」：把权限码摆出来并支持一键复制，员工才能一句话发给管理员
async function explainDenied(e: Entry) {
  const perm = permOf(e)
  try {
    await showConfirmDialog({
      title: t('ai.hubDeniedTitle'),
      message: perm ? t('ai.hubDeniedMsg', { v: perm }) : t('ai.hubLockedDenied'),
      confirmButtonText: perm ? t('ai.hubDeniedCopy') : t('ai.ok'),
      cancelButtonText: t('ai.ok'),
    })
  } catch {
    // 点了取消：不复制，免得剪贴板被悄悄改写
    return
  }
  if (!perm) return
  const done = await copyToClipboard(perm)
  showToast(done ? t('ai.hubDeniedCopied') : t('ai.copyFailed'))
}

function tagText(e: Entry): string {
  const s = blockedState(e)
  if (s === 'missing') return t('ai.hubStatusMissing')
  if (s === 'disabled') return t('ai.hubStatusDisabled')
  if (s === 'denied') return t('ai.hubStatusDenied')
  if (s === 'local') return t('ai.hubLocked')
  return ''
}

function tagType(e: Entry): 'warning' | 'danger' {
  return blockedState(e) === 'denied' ? 'danger' : 'warning'
}

function go(e: Entry) {
  const s = blockedState(e)
  if (s === 'missing') return showToast(t('ai.hubLockedMissing'))
  if (s === 'disabled') return showToast(t('ai.hubLockedDisabled'))
  if (s === 'denied' || s === 'local') return void explainDenied(e)
  pushRecent(e.path)
  void router.push(e.path)
}

async function check() {
  checking.value = true
  try {
    const r = await getAiExtensionStatus()
    const map: Record<string, AiExtensionStatus> = {}
    for (const it of r.items || []) map[it.key] = it
    statuses.value = map
    checked.value = true
    await loadOverview()
  } catch {
    checked.value = false
  } finally {
    checking.value = false
  }
}

onMounted(async () => {
  loadRecent()
  if (!auth.permissions.length) await auth.fetchMe()
  await check()
})
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-gradient-to-r from-violet-500 to-indigo-600 p-4 text-white shadow-sm">
      <div class="text-lg font-semibold">{{ t('ai.hubTitle') }}</div>
      <div class="mt-1 text-xs opacity-90">{{ t('ai.hubIntro') }}</div>
      <div class="mt-2 flex items-center justify-between gap-2 text-xs">
        <span class="opacity-90">{{ t('ai.hubStatusSummary', { n: summary.ready, m: summary.total }) }}</span>
        <span class="shrink-0 cursor-pointer underline opacity-90" @click="check">
          {{ checking ? t('ai.loading') : t('ai.hubStatusRefresh') }}
        </span>
      </div>
    </div>
    <div v-if="hasOverview" class="rounded-xl bg-white p-3 shadow-sm">
      <div class="flex items-center justify-between">
        <span class="text-[10px] text-zinc-400">{{ t('ai.hubOverview') }}</span>
        <span class="cursor-pointer text-[10px] text-zinc-400" @click="check">
          {{ checking ? t('ai.loading') : t('ai.hubStatusRefresh') }}
        </span>
      </div>
      <div class="mt-2 grid grid-cols-3 gap-2 text-center">
        <div v-if="overview.health !== null">
          <div class="text-lg font-semibold" :class="healthTone(overview.health)">{{ overview.health }}</div>
          <div class="text-[10px] text-zinc-400">{{ t('ai.hubMetricHealth') }}</div>
        </div>
        <div v-if="overview.active !== null" class="cursor-pointer" @click="goPath('/ai-alerts')">
          <div class="text-lg font-semibold text-orange-600">{{ overview.active }}</div>
          <div class="text-[10px] text-zinc-400">{{ t('ai.hubMetricActive') }}</div>
        </div>
        <div v-if="overview.runs !== null" class="cursor-pointer" @click="goPath('/ai-employees')">
          <div class="text-lg font-semibold text-emerald-600">{{ overview.runs }}</div>
          <div class="text-[10px] text-zinc-400">{{ t('ai.hubMetricRuns') }}</div>
        </div>
      </div>
    </div>
    <div v-if="recentEntries.length" class="rounded-xl bg-white p-3 shadow-sm">
      <div class="flex items-center justify-between">
        <span class="text-[10px] text-zinc-400">{{ t('ai.hubRecent') }}</span>
        <span class="cursor-pointer text-[10px] text-zinc-400" @click="clearRecent">{{ t('ai.hubRecentClear') }}</span>
      </div>
      <div class="mt-1 flex flex-wrap gap-1">
        <span
          v-for="e in recentEntries"
          :key="e.path"
          class="cursor-pointer rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] text-zinc-600"
          @click="go(e)"
        >{{ e.icon }} {{ e.title }}</span>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div
        v-for="e in entries"
        :key="e.path"
        class="relative rounded-xl bg-white p-4 shadow-sm active:bg-zinc-50"
        @click="go(e)"
      >
        <div v-if="tagText(e)" class="absolute right-2 top-2">
          <van-tag plain :type="tagType(e)">{{ tagText(e) }}</van-tag>
        </div>
        <div :class="['text-2xl', e.color]">{{ e.icon }}</div>
        <div class="mt-2 text-sm font-medium text-zinc-800">{{ e.title }}</div>
        <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ e.desc }}</div>
        <div
          v-if="blockedState(e) === 'denied' || blockedState(e) === 'local'"
          class="mt-1 truncate text-[9px] text-zinc-400"
        >{{ permOf(e) }}</div>
      </div>
    </div>
  </div>
</template>
