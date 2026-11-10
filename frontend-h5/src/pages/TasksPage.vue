<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showDialog, showToast } from 'vant'
import { getMyTasks, type H5Task } from '@/api/tasks'
import { aiChat } from '@/api/ai'
import { handleExtensionLocked } from '@/utils/extension-gate'
import { tenantH5Path } from '@/utils/tenant'

const router = useRouter()

const items = ref<H5Task[]>([])
const loading = ref(false)
const refreshing = ref(false)
const finished = ref(false)
const statusFilter = ref('')

const offset = ref(0)
const limit = 50

const tabs = [
  { key: '', label: '全部' },
  { key: 'pending', label: '待开始' },
  { key: 'working', label: '进行中' },
  { key: 'done', label: '已完成' },
]

const taskStats = computed(() => {
  const total = items.value.length
  const pending = items.value.filter((t) => t.status === 'pending').length
  const working = items.value.filter((t) => t.status === 'working').length
  const done = items.value.filter((t) => t.status === 'done').length
  return { total, pending, working, done }
})

function goDetail(code: string) {
  router.push(`/tasks/${encodeURIComponent(code)}`)
}

function goReport(t: H5Task, e: Event) {
  e.stopPropagation()
  const path = t.use_unit_report === false ? '/report' : '/report-unit'
  router.push({ path: tenantH5Path(path), query: { task_code: t.task_code } })
}

function statusTag(s: string) {
  if (s === 'pending') return { type: 'primary' as const, text: '待开始' }
  if (s === 'working') return { type: 'warning' as const, text: '进行中' }
  if (s === 'done') return { type: 'success' as const, text: '已完成' }
  return { type: 'default' as const, text: s }
}

async function load(reset = false) {
  if (loading.value) return
  if (reset) {
    offset.value = 0
    finished.value = false
    items.value = []
  }
  if (finished.value) return

  loading.value = true
  try {
    const resp = await getMyTasks({ status: statusFilter.value || undefined, offset: offset.value, limit })
    const arr = resp?.items ?? []
    items.value = reset ? arr : [...items.value, ...arr]
    offset.value += arr.length
    if (arr.length < limit) finished.value = true
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  refreshing.value = true
  try {
    await load(true)
  } finally {
    refreshing.value = false
  }
}

function onTabChange(key: string) {
  statusFilter.value = key
  load(true)
}

// 推荐报工：按剩余量排序（规则层），需要更细排序可点「问 AI」
const recommends = computed(() =>
  items.value
    .filter((t) => t.status !== 'done' && (t.remaining_qty ?? 0) > 0)
    .sort((a, b) => (b.remaining_qty ?? 0) - (a.remaining_qty ?? 0))
    .slice(0, 3)
    .map((t) => ({ task: t, reason: '剩余数量最多，建议优先报工' })),
)
const aiAsking = ref(false)

function goReportByTask(t: H5Task) {
  const path = t.use_unit_report === false ? '/report' : '/report-unit'
  router.push({ path: tenantH5Path(path), query: { task_code: t.task_code } })
}

async function askAiOrder() {
  if (!recommends.value.length) {
    showToast('暂无可报工任务')
    return
  }
  const ctx = recommends.value
    .map((r) => `${r.task.task_code} ${r.task.process?.name || ''} 剩余${r.task.remaining_qty ?? 0}`)
    .join('；')
  aiAsking.value = true
  try {
    const res = await aiChat({
      message: `我是车间工人，请根据剩余数量给出前 3 个优先报工的任务与一句理由：${ctx}`,
    })
    await showDialog({ title: 'AI 排工建议', message: res.reply, confirmButtonText: '知道了' })
  } catch (e: unknown) {
    if (!handleExtensionLocked(e, '工厂助手（AI 助手）')) {
      showToast(e instanceof Error ? e.message : 'AI 暂不可用')
    }
  } finally {
    aiAsking.value = false
  }
}

watch(statusFilter, () => load(true), { immediate: true })

onMounted(() => {
  load(true)
})
</script>

<template>
  <div>
    <div class="grid grid-cols-4 gap-2 px-1">
      <div class="rounded-lg bg-blue-50 p-2 text-center">
        <div class="text-lg font-bold text-blue-600">{{ taskStats.total }}</div>
        <div class="text-[11px] text-blue-500">全部</div>
      </div>
      <div class="rounded-lg bg-yellow-50 p-2 text-center">
        <div class="text-lg font-bold text-yellow-600">{{ taskStats.pending }}</div>
        <div class="text-[11px] text-yellow-500">待开始</div>
      </div>
      <div class="rounded-lg bg-orange-50 p-2 text-center">
        <div class="text-lg font-bold text-orange-600">{{ taskStats.working }}</div>
        <div class="text-[11px] text-orange-500">进行中</div>
      </div>
      <div class="rounded-lg bg-green-50 p-2 text-center">
        <div class="text-lg font-bold text-green-600">{{ taskStats.done }}</div>
        <div class="text-[11px] text-green-500">已完成</div>
      </div>
    </div>

    <van-tabs v-model:active="statusFilter" class="mt-2" @change="onTabChange">
      <van-tab v-for="t in tabs" :key="t.key" :title="t.label" :name="t.key" />
    </van-tabs>

    <!-- 推荐报工：规则层按剩余量排序，可再问 AI -->
    <div v-if="recommends.length" class="mx-2 mt-2 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-600 p-3 text-white shadow-sm">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <van-icon name="aim" />
          <span class="text-sm font-medium">推荐报工</span>
          <van-loading v-if="aiAsking" size="12px" color="#fff" />
        </div>
        <van-button size="mini" plain class="!text-white !border-white/60" :loading="aiAsking" @click="askAiOrder">
          问 AI
        </van-button>
      </div>
      <div class="mt-2 space-y-2">
        <div
          v-for="(rec, idx) in recommends"
          :key="rec.task.id"
          class="flex items-center justify-between rounded-lg bg-white/15 p-2 active:bg-white/25"
          @click="goReportByTask(rec.task)"
        >
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="rounded bg-white/30 px-1.5 text-[10px] font-medium">TOP{{ idx + 1 }}</span>
              <span class="truncate text-sm font-medium">
                {{ rec.task.process?.name || rec.task.task_code }}
              </span>
            </div>
            <div class="mt-1 text-[11px] opacity-90">{{ rec.reason }}</div>
          </div>
          <div class="ml-2 text-right text-[11px]">
            <div class="font-bold">{{ rec.task.remaining_qty ?? 0 }}</div>
            <div class="opacity-80">待报</div>
          </div>
        </div>
      </div>
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-list v-model:loading="loading" :finished="finished" finished-text="没有更多了" @load="load(false)">
        <div v-if="items.length" class="mt-2 space-y-3 px-2">
          <div
            v-for="t in items"
            :key="t.id"
            class="rounded-xl border border-zinc-100 bg-white p-3 shadow-sm"
            @click="goDetail(t.task_code)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-medium text-zinc-900">{{ t.process?.name || `工序#${t.process_id}` }}</span>
                  <van-tag :type="statusTag(t.status).type" plain size="medium">{{ statusTag(t.status).text }}</van-tag>
                </div>
                <div class="mt-2 text-xs text-zinc-500 space-y-1">
                  <div v-if="t.work_order">订单/工单 #{{ t.work_order.order_id }}</div>
                  <div v-if="t.work_order?.sku">
                    产品：{{ t.work_order.sku.code }}
                    <span class="text-zinc-400">{{ t.work_order.sku.name }}</span>
                  </div>
                  <div class="flex gap-4 mt-1">
                    <span>分配 <b class="text-zinc-800">{{ t.assigned_qty ?? '—' }}</b></span>
                    <span>已报 <b class="text-green-600">{{ t.reported_qty ?? 0 }}</b></span>
                    <span>待报 <b class="text-orange-500">{{ t.remaining_qty ?? 0 }}</b></span>
                  </div>
                </div>
              </div>
              <van-button
                v-if="t.status !== 'done' && (t.remaining_qty ?? 0) > 0"
                type="primary"
                size="small"
                @click="goReport(t, $event)"
              >
                报工
              </van-button>
            </div>
            <div class="mt-2 text-[11px] text-zinc-400 font-mono">{{ t.task_code }}</div>
          </div>
        </div>
        <van-empty v-else-if="!loading && !refreshing" description="暂无任务" />
      </van-list>
    </van-pull-refresh>
  </div>
</template>
