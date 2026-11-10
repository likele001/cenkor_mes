<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showDialog, showToast } from 'vant'
import { employeeOverview, executeEmployeeTool, listEmployeeTools, type EmployeeTool } from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const { t } = useI18n()

const loading = ref(true)
const locked = ref(false)
const tools = ref<EmployeeTool[]>([])
const running = ref('')
const totalRuns = ref(0)
const runs24h = ref(0)

async function load() {
  loading.value = true
  try {
    const [toolRes, overview] = await Promise.all([listEmployeeTools(), employeeOverview()])
    tools.value = toolRes.tools || []
    totalRuns.value = overview.total_runs || 0
    runs24h.value = overview.runs_last_24h || 0
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

async function run(tool: EmployeeTool) {
  if (running.value) return
  running.value = tool.code
  try {
    const r = await executeEmployeeTool(tool.code)
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
      <div class="text-sm font-medium text-zinc-800">{{ t('ai.employeesTitle') }}</div>
      <div class="mt-1 text-[11px] text-zinc-500">{{ t('ai.employeesSubtitle') }}</div>
      <div class="mt-3 flex gap-4">
        <div>
          <div class="text-lg font-bold text-indigo-600">{{ totalRuns }}</div>
          <div class="text-[11px] text-zinc-500">{{ t('ai.totalRuns') }}</div>
        </div>
        <div>
          <div class="text-lg font-bold text-indigo-600">{{ runs24h }}</div>
          <div class="text-[11px] text-zinc-500">{{ t('ai.runs24h') }}</div>
        </div>
      </div>
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
  </div>
</template>
