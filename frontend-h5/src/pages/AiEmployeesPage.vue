<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showDialog, showToast } from 'vant'
import { employeeOverview, executeEmployeeTool, listEmployeeTools, type EmployeeTool } from '@/api/ai'
import { handleExtensionLocked, isAccessDenied } from '@/utils/extension-gate'

const loading = ref(true)
const locked = ref(false)
const tools = ref<EmployeeTool[]>([])
const running = ref('')
const totalRuns = ref(0)
const runs24h = ref(0)

async function load() {
  loading.value = true
  try {
    const [t, o] = await Promise.all([listEmployeeTools(), employeeOverview()])
    tools.value = t.tools || []
    totalRuns.value = o.total_runs || 0
    runs24h.value = o.runs_last_24h || 0
    locked.value = false
  } catch (e: unknown) {
    tools.value = []
    if (isAccessDenied(e)) {
      locked.value = true
    } else {
      showToast(e instanceof Error ? e.message : '加载失败')
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
      message: r.report || r.rule_summary || r.error || '本次巡检无输出',
      confirmButtonText: '知道了',
    })
    await load()
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, 'AI 数字员工')) {
      showToast(e instanceof Error ? e.message : '执行失败')
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
      <div class="text-sm font-medium text-zinc-800">AI 数字员工</div>
      <div class="mt-1 text-[11px] text-zinc-500">只读巡检技能，不改写任何业务数据</div>
      <div class="mt-3 flex gap-4">
        <div>
          <div class="text-lg font-bold text-indigo-600">{{ totalRuns }}</div>
          <div class="text-[11px] text-zinc-500">累计执行</div>
        </div>
        <div>
          <div class="text-lg font-bold text-indigo-600">{{ runs24h }}</div>
          <div class="text-[11px] text-zinc-500">近 24 小时</div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">加载中…</div>

    <div v-else-if="locked" class="rounded-xl bg-white p-6 text-center shadow-sm">
      <div class="text-sm text-zinc-600">「AI 数字员工」未开通 / 未授权</div>
      <div class="mt-2 text-xs text-zinc-400">请在应用市场的扩展应用中开通，并由管理员为当前账号授权后使用。</div>
    </div>

    <div v-else class="space-y-2">
      <div v-for="t in tools" :key="t.code" class="rounded-xl bg-white p-3 shadow-sm">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-zinc-800">{{ t.name }}</div>
            <div class="mt-1 text-[11px] leading-relaxed text-zinc-500">{{ t.desc }}</div>
          </div>
          <van-button size="small" type="primary" plain :loading="running === t.code" @click="run(t)">
            执行
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>
