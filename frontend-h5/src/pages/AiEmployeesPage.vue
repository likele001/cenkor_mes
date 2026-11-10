<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showDialog, showToast } from 'vant'
import {
  employeeOverview, executeEmployeeTool, getEmployeeLog, getEmployeeToggle, listEmployeeLogs,
  listEmployeeTools, type EmployeeLog, type EmployeeLogDetail, type EmployeeTool,
} from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const loading = ref(true)
const locked = ref(false)
const tools = ref<EmployeeTool[]>([])
const running = ref('')
const totalRuns = ref(0)
const runs24h = ref(0)
const toggleEnabled = ref<boolean | null>(null)
const instruction = ref('')

const logsOpen = ref(false)
const logsLoading = ref(false)
const logs = ref<EmployeeLog[]>([])
const logTool = ref('')
const logStatus = ref('')

const logOpen = ref(false)
const logLoading = ref(false)
const logDetail = ref<EmployeeLogDetail | null>(null)

// facts 可能是几十个键，长文本截断展示，避免弹层被一条 SQL 结果撑爆
const factEntries = computed(() => {
  const f = logDetail.value?.facts || {}
  return Object.entries(f).slice(0, 30).map(([k, v]) => {
    const raw = typeof v === 'string' ? v : JSON.stringify(v)
    return { k, v: raw && raw.length > 300 ? raw.slice(0, 300) + '…' : raw }
  })
})

async function load() {
  loading.value = true
  try {
    const [toolRes, overview, toggle] = await Promise.all([
      listEmployeeTools(),
      employeeOverview(),
      getEmployeeToggle().catch(() => null),
    ])
    tools.value = toolRes.tools || []
    totalRuns.value = overview.total_runs || 0
    runs24h.value = overview.runs_last_24h || 0
    toggleEnabled.value = toggle?.enabled ?? null
    locked.value = false
  } catch (e: unknown) {
    tools.value = []
    if (isAccessDenied(e)) {
      locked.value = true
    } else {
      showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
    }
  } finally {
    loading.value = false
  }
}

async function reloadLogs() {
  logsLoading.value = true
  try {
    const r = await listEmployeeLogs({
      mine: 1,
      limit: 30,
      tool: logTool.value || undefined,
      status: logStatus.value || undefined,
    })
    logs.value = r.items || []
  } catch {
    logs.value = []
  } finally {
    logsLoading.value = false
  }
}

async function openLogs() {
  logsOpen.value = true
  await reloadLogs()
}

async function openLog(id: number) {
  logOpen.value = true
  logLoading.value = true
  logDetail.value = null
  try {
    const r = await getEmployeeLog(id)
    if (r.found === false) {
      showToast(r.error || t('ai.noLogs'))
      logOpen.value = false
      return
    }
    logDetail.value = r
  } catch (e: unknown) {
    logOpen.value = false
    if (!handleExtensionLocked(e, t('ai.nameEmployees'))) {
      showToast(e instanceof Error ? e.message : t('ai.loadFailed'))
    }
  } finally {
    logLoading.value = false
  }
}

async function run(tool: EmployeeTool) {
  if (running.value) return
  running.value = tool.code
  try {
    const r = await executeEmployeeTool(tool.code, instruction.value.trim() || undefined)
    await showDialog({
      title: tool.name,
      message: r.report || r.rule_summary || r.error || t('ai.noOutput'),
      confirmButtonText: t('ai.ok'),
    })
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, t('ai.nameEmployees'))) {
      showToast(e instanceof Error ? e.message : t('ai.executeFailed'))
    }
  } finally {
    running.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-3">
    <div class="rounded-xl bg-white p-3 shadow-sm">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0 flex-1">
          <div class="text-sm font-medium text-zinc-800">{{ t('ai.employeesTitle') }}</div>
          <div class="mt-1 text-[11px] text-zinc-500">{{ t('ai.employeesSubtitle') }}</div>
        </div>
        <van-tag v-if="toggleEnabled !== null" plain :type="toggleEnabled ? 'success' : 'warning'">
          {{ toggleEnabled ? t('ai.enabled') : t('ai.disabled') }}
        </van-tag>
      </div>
      <div class="mt-3 flex items-end gap-4">
        <div>
          <div class="text-lg font-bold text-indigo-600">{{ totalRuns }}</div>
          <div class="text-[11px] text-zinc-500">{{ t('ai.totalRuns') }}</div>
        </div>
        <div>
          <div class="text-lg font-bold text-indigo-600">{{ runs24h }}</div>
          <div class="text-[11px] text-zinc-500">{{ t('ai.runs24h') }}</div>
        </div>
        <van-button class="ml-auto" size="mini" plain @click="openLogs">{{ t('ai.logs') }}</van-button>
      </div>
      <van-field
        v-model="instruction"
        :label="t('ai.instructionLabel')"
        :placeholder="t('ai.instructionPlaceholder')"
        maxlength="200"
        class="!px-0"
      />
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>

    <div v-else-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">{{ t('ai.lockedTitle', { name: t('ai.nameEmployees') }) }}</div>
      <div class="mt-2 text-xs text-zinc-400">{{ t('ai.lockedHint') }}</div>
    </div>

    <van-empty v-else-if="!tools.length" :description="t('ai.noTools')" />

    <div v-else class="space-y-2">
      <div v-for="item in tools" :key="item.code" class="rounded-xl bg-white p-3 shadow-sm">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-zinc-800">{{ item.name }}</div>
            <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ item.desc }}</div>
          </div>
          <van-button size="small" type="primary" plain :loading="running === item.code" @click="run(item)">
            {{ t('ai.execute') }}
          </van-button>
        </div>
      </div>
    </div>

    <van-popup v-model:show="logsOpen" position="bottom" round class="pb-safe" :style="{ height: '60%' }">
      <div class="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <div class="text-sm font-medium text-zinc-800">{{ t('ai.logs') }}</div>
        <van-button size="mini" plain @click="reloadLogs">{{ t('ai.refresh') }}</van-button>
      </div>
      <div class="flex gap-2 border-b border-zinc-100 px-3 py-2">
        <select v-model="logTool" class="min-w-0 flex-1 rounded border border-zinc-200 px-2 py-1 text-xs" @change="reloadLogs">
          <option value="">{{ t('ai.logFilterTool') }}</option>
          <option v-for="item in tools" :key="item.code" :value="item.code">{{ item.name }}</option>
        </select>
        <select v-model="logStatus" class="min-w-0 flex-1 rounded border border-zinc-200 px-2 py-1 text-xs" @change="reloadLogs">
          <option value="">{{ t('ai.logFilterStatus') }}</option>
          <option value="ok">ok</option>
          <option value="degraded">degraded</option>
          <option value="error">error</option>
          <option value="locked">locked</option>
        </select>
      </div>
      <div class="h-[calc(100%-93px)] overflow-y-auto px-3 py-2">
        <div v-if="logsLoading" class="py-8 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>
        <van-empty v-else-if="!logs.length" :description="t('ai.noLogs')" />
        <div v-else class="space-y-2">
          <div v-for="l in logs" :key="l.id" class="rounded-xl bg-zinc-50 p-3">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm text-zinc-800">{{ l.tool_name || l.tool_code || '-' }}</div>
                <div v-if="l.summary" class="mt-1 line-clamp-2 text-[11px] text-zinc-500">{{ l.summary }}</div>
              </div>
              <div class="flex shrink-0 flex-col items-end gap-1">
                <van-tag plain :type="l.status === 'ok' ? 'success' : 'warning'">{{ l.status || '-' }}</van-tag>
                <van-button size="mini" plain @click="openLog(l.id)">{{ t('ai.logDetail') }}</van-button>
              </div>
            </div>
            <div class="mt-1 text-[10px] text-zinc-400">
              {{ l.created_at || '' }}<span v-if="l.duration_ms"> · {{ t('ai.duration') }} {{ l.duration_ms }}ms</span>
            </div>
          </div>
        </div>
      </div>
    </van-popup>

    <van-popup v-model:show="logOpen" position="bottom" round class="pb-safe" :style="{ height: '75%' }">
      <div class="flex h-full flex-col">
        <div class="flex shrink-0 items-center justify-between gap-2 border-b border-zinc-100 px-4 py-3">
          <div class="min-w-0 flex-1 truncate text-sm font-medium text-zinc-800">
            {{ logDetail?.tool_name || logDetail?.tool_code || t('ai.logDetail') }}
          </div>
          <div class="flex shrink-0 items-center gap-1">
            <van-tag v-if="logDetail" plain :type="logDetail.status === 'ok' ? 'success' : 'warning'">
              {{ logDetail.status || '-' }}
            </van-tag>
            <van-button size="mini" plain @click="logOpen = false">{{ t('ai.close') }}</van-button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto px-4 py-3">
          <div v-if="logLoading" class="py-8 text-center text-sm text-zinc-400">{{ t('ai.loading') }}</div>
          <template v-else-if="logDetail">
            <div class="text-[11px] text-zinc-400">
              {{ logDetail.created_at || '' }}
              <span v-if="logDetail.duration_ms"> · {{ t('ai.duration') }} {{ logDetail.duration_ms }}ms</span>
              <span v-if="logDetail.tokens_in || logDetail.tokens_out">
                · {{ t('ai.logTokens', { i: logDetail.tokens_in ?? 0, o: logDetail.tokens_out ?? 0 }) }}
              </span>
            </div>
            <div class="mt-3 rounded-lg bg-zinc-50 p-3">
              <div class="text-xs font-medium text-zinc-600">{{ t('ai.logInstruction') }}</div>
              <div class="mt-1 whitespace-pre-wrap text-xs text-zinc-600">{{ logDetail.instruction || '-' }}</div>
            </div>
            <div class="mt-2 rounded-lg bg-zinc-50 p-3">
              <div class="text-xs font-medium text-zinc-600">{{ t('ai.logOutput') }}</div>
              <div class="mt-1 whitespace-pre-wrap break-words text-xs leading-relaxed text-zinc-700">
                {{ logDetail.summary || t('ai.noOutput') }}
              </div>
            </div>
            <div class="mt-2 rounded-lg bg-zinc-50 p-3">
              <div class="text-xs font-medium text-zinc-600">{{ t('ai.logFacts') }}</div>
              <div v-if="factEntries.length" class="mt-1 space-y-1">
                <div v-for="f in factEntries" :key="f.k" class="flex gap-2 text-[11px]">
                  <span class="shrink-0 text-zinc-400">{{ f.k }}</span>
                  <span class="min-w-0 break-all text-zinc-600">{{ f.v }}</span>
                </div>
              </div>
              <div v-else class="mt-1 text-[11px] text-zinc-400">{{ t('ai.logNoFacts') }}</div>
            </div>
          </template>
        </div>
      </div>
    </van-popup>
  </div>
</template>
