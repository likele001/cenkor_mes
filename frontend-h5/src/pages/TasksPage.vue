<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { getMyTasks, type H5Task } from '@/api/tasks'
import { getTaskRecommend, type TaskRecommendItem } from '@/api/ai'
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

// AI 推荐（Task 5）
const recommends = ref<TaskRecommendItem[]>([])
const aiRecommending = ref(false)

async function loadRecommend() {
  aiRecommending.value = true
  try {
    const res = await getTaskRecommend()
    recommends.value = res.items || []
  } catch {
    // 静默失败：推荐是辅助，不打扰用户
    recommends.value = []
  } finally {
    aiRecommending.value = false
  }
}

function findTaskByCode(code: string): H5Task | undefined {
  return items.value.find((t) => t.task_code === code)
}

function goReportCode(taskCode: string, useUnit: boolean | undefined) {
  const path = useUnit === false ? '/report' : '/report-unit'
  router.push({ path: tenantH5Path(path), query: { task_code: taskCode } })
}

function onRecommendClick(rec: TaskRecommendItem) {
  const t = findTaskByCode(rec.task_code)
  if (t) {
    goReportCode(rec.task_code, t.use_unit_report)
  } else {
    // 任务可能不在当前页列表中：尝试简单按 task_code 跳转
    showToast('请到任务列表中跳转报工')
  }
}

function priorityTag(p: string) {
  if (p === 'urgent') return { type: 'danger' as const, text: '急' }
  return { type: 'primary' as const, text: '推荐' }
}

watch(statusFilter, () => load(true), { immediate: true })

onMounted(() => {
  load(true)
  loadRecommend()
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

    <!-- AI 推荐（Task 5）：急件 / 续报 / 剩最多 -->
    <div v-if="recommends.length" class="mx-2 mt-2 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-600 p-3 text-white shadow-sm">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <van-icon name="aim" />
          <span class="text-sm font-medium">AI 推荐</span>
          <van-loading v-if="aiRecommending" size="12px" color="#fff" />
        </div>
        <span class="text-[11px] opacity-80">点击直接报工</span>
      </div>
      <div class="mt-2 space-y-2">
        <div
          v-for="(rec, idx) in recommends"
          :key="rec.task_id"
          class="flex items-center justify-between rounded-lg bg-white/15 p-2 active:bg-white/25"
          @click="onRecommendClick(rec)"
        >
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="rounded bg-white/30 px-1.5 text-[10px] font-medium">TOP{{ idx + 1 }}</span>
              <van-tag :type="priorityTag(rec.priority).type" plain class="!bg-white/20 !text-white !border-transparent">
                {{ priorityTag(rec.priority).text }}
              </van-tag>
              <span class="truncate text-sm font-medium">
                {{ rec.process_name || rec.task_code }}
              </span>
            </div>
            <div class="mt-1 text-[11px] opacity-90">{{ rec.reason || '建议继续报工' }}</div>
          </div>
          <div class="ml-2 text-right text-[11px]">
            <div class="font-bold">{{ rec.remaining_qty }}</div>
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
