<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showDialog, showLoadingToast, closeToast, showToast } from 'vant'
import { getMyDashboardSummary, type H5DashboardSummary } from '@/api/tasks'
import { getAiBrief, listAiAlerts, runAiAlerts, shiftAiSummary, type AlertItem, type AiBriefOut, type ShiftSummaryOut } from '@/api/ai'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const summary = ref<H5DashboardSummary | null>(null)
const aiAlerts = ref<AlertItem[]>([])
const alertScanning = ref(false)
const briefLoading = ref(false)
const brief = ref<AiBriefOut | null>(null)

const canAi = computed(() => auth.hasPermission('ai.use'))
const canAiAlert = computed(() => auth.hasPermission('ai.alert.view'))
const canAiBrief = computed(() => canAi.value && canAiAlert.value)
const canAiEmployee = computed(() => auth.hasPermission("ai_employee.use"))
const canShiftSummary = computed(() => auth.hasPermission('ai.report_assist'))
const showAiHub = computed(() => canAi.value || canAiAlert.value || canAiEmployee.value)
const showStaffHome = computed(() => !auth.isCustomer)

// 交接摘要（Task 6）
const shiftSummaryLoading = ref(false)
const shiftSummary = ref<ShiftSummaryOut | null>(null)

const todayLabel = computed(() => {
  const d = new Date()
  const y = d.getFullYear()
  const m = d.getMonth() + 1
  const day = d.getDate()
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  return `${y}年${m}月${day}日 星期${weekdays[d.getDay()]}`
})

function formatMoney(v: number | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  return v.toFixed(2)
}

function formatRate(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${(v * 100).toFixed(1)}%`
}

async function refresh() {
  loading.value = true
  try {
    if (auth.isEmployee) {
      summary.value = await getMyDashboardSummary()
    }
  } finally {
    loading.value = false
  }
  if (canAiAlert.value) {
    try {
      const res = await listAiAlerts()
      aiAlerts.value = (res.items || []).slice(0, 5)
    } catch {
      aiAlerts.value = []
    }
  }
  if (canAiBrief.value) {
    briefLoading.value = true
    try {
      brief.value = await getAiBrief()
    } catch {
      brief.value = null
    } finally {
      briefLoading.value = false
    }
  }
}

async function scanAlerts() {
  alertScanning.value = true
  try {
    const res = await runAiAlerts()
    showToast(`扫描 ${res.events ?? 0} 条`)
    const list = await listAiAlerts()
    aiAlerts.value = (list.items || []).slice(0, 5)
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : '扫描失败')
  } finally {
    alertScanning.value = false
  }
}

// AI 生成换班/交接摘要
async function generateShiftSummary() {
  shiftSummaryLoading.value = true
  showLoadingToast({ message: 'AI 正在汇总本班次…', duration: 0 })
  try {
    shiftSummary.value = await shiftAiSummary({ shift_hours: 8 })
    closeToast()
    await showDialog({
      title: '交接摘要',
      message: buildShiftSummaryText(shiftSummary.value!),
      confirmButtonText: '知道了',
    })
  } catch (e: unknown) {
    closeToast()
    showToast(e instanceof Error ? e.message : '生成摘要失败')
  } finally {
    shiftSummaryLoading.value = false
  }
}

function buildShiftSummaryText(s: ShiftSummaryOut): string {
  const t = s.totals
  const lines = [
    `时段：${s.shift_start} ~ ${s.shift_end}`,
    `报工 ${t.report_count} 单 / 件次 ${t.unit_count}`,
    `合格 ${t.good} · 不良 ${t.bad} · 驳回 ${t.rejected}`,
    `未交接 ${t.open_assignments}`,
    '',
    s.summary,
  ]
  if (s.highlights?.length) {
    lines.push('', '✨ 亮点:')
    lines.push(...s.highlights.map((h) => `· ${h}`))
  }
  if (s.alerts?.length) {
    lines.push('', '⚠️ 异常:')
    lines.push(...s.alerts.map((h) => `· ${h}`))
  }
  if (s.unfinished?.length) {
    lines.push('', '🔧 未完成待交接:')
    lines.push(...s.unfinished.map((h) => `· ${h}`))
  }
  return lines.join('\n')
}

function go(path: string) {
  router.push(path)
}

onMounted(async () => {
  if (auth.isCustomer) {
    router.replace({ name: 'customerOrder' })
    return
  }
  if (!auth.permissions.length) await auth.fetchMe()
  refresh()
  auth.refreshUnreadNotificationCount()
})
</script>

<template>
  <div v-if="showStaffHome">
    <!-- 头部问候 -->
    <div class="rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 p-4 text-white">
      <div class="text-sm opacity-80">{{ todayLabel }}</div>
      <div class="mt-2 text-lg font-semibold">今日工作概况</div>
      <div class="mt-4 grid grid-cols-3 gap-3 text-center">
        <div>
          <div class="text-2xl font-bold">{{ summary?.today.good_qty ?? '—' }}</div>
          <div class="mt-0.5 text-xs opacity-80">今日合格</div>
        </div>
        <div>
          <div class="text-2xl font-bold">{{ summary?.today.bad_qty ?? '—' }}</div>
          <div class="mt-0.5 text-xs opacity-80">今日不良</div>
        </div>
        <div>
          <div class="text-2xl font-bold">{{ formatRate(summary?.today.yield_rate) }}</div>
          <div class="mt-0.5 text-xs opacity-80">良率</div>
        </div>
      </div>
    </div>

    <div v-if="canShiftSummary" class="mx-4 mt-4 rounded-xl bg-white p-4 shadow-sm">
      <div class="flex items-center justify-between mb-2">
        <div class="text-sm font-medium text-zinc-700">换班/交接摘要（AI）</div>
        <van-button
          size="mini"
          type="primary"
          plain
          :loading="shiftSummaryLoading"
          icon="exchange"
          @click="generateShiftSummary"
        >
          生成摘要
        </van-button>
      </div>
      <div v-if="!shiftSummary" class="text-xs text-zinc-400">
        点击「生成摘要」AI 将汇总近 8 小时本班次的报工/不良/待交接，自动生成一段交接话术。
      </div>
      <div v-else class="space-y-2">
        <div class="grid grid-cols-4 gap-2 text-center text-xs">
          <div class="rounded bg-green-50 p-2">
            <div class="font-bold text-green-600">{{ shiftSummary.totals.good }}</div>
            <div class="text-zinc-500">合格</div>
          </div>
          <div class="rounded bg-red-50 p-2">
            <div class="font-bold text-red-500">{{ shiftSummary.totals.bad }}</div>
            <div class="text-zinc-500">不良</div>
          </div>
          <div class="rounded bg-orange-50 p-2">
            <div class="font-bold text-orange-500">{{ shiftSummary.totals.rejected }}</div>
            <div class="text-zinc-500">驳回</div>
          </div>
          <div class="rounded bg-blue-50 p-2">
            <div class="font-bold text-blue-500">{{ shiftSummary.totals.open_assignments }}</div>
            <div class="text-zinc-500">待交接</div>
          </div>
        </div>
        <div class="text-xs text-zinc-500 whitespace-pre-wrap leading-relaxed">{{ shiftSummary.summary }}</div>
      </div>
    </div>

    <div v-if="canAiBrief" class="mx-4 mt-4 rounded-xl bg-white p-4 shadow-sm">
      <div class="flex items-center justify-between mb-2">
        <div class="text-sm font-medium text-zinc-700">今日简报</div>
        <span v-if="brief?.mode" class="text-xs text-zinc-400">{{ brief.mode === 'llm' ? 'AI 生成' : '规则汇总' }}</span>
      </div>
      <div v-if="briefLoading" class="text-xs text-zinc-400">加载中…</div>
      <div v-else-if="brief?.content" class="text-sm text-zinc-600 whitespace-pre-wrap leading-relaxed">{{ brief.content }}</div>
      <div v-else class="text-xs text-zinc-400">暂无简报</div>
    </div>

    <div v-if="showAiHub" class="mx-4 mt-4">
      <div class="mb-2 text-sm font-medium text-zinc-700">智能中心</div>
      <div class="grid grid-cols-3 gap-3">
        <div class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer" @click="go('/ai-hub')">
          <div class="text-violet-500 text-2xl">🧠</div>
          <div class="mt-1 text-sm font-medium">智能中心</div>
        </div>
        <div class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer" @click="go('/help')">
          <div class="text-blue-500 text-2xl">💡</div>
          <div class="mt-1 text-sm font-medium">智能帮助</div>
        </div>
        <div
          v-if="canAi"
          class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer"
          @click="go('/ai-assistant')"
        >
          <div class="text-indigo-500 text-2xl">🤖</div>
          <div class="mt-1 text-sm font-medium">工厂助手</div>
        </div>
        <div
          v-else-if="canAiAlert"
          class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer"
          @click="go('/ai-alerts')"
        >
          <div class="text-orange-500 text-2xl">⚠️</div>
          <div class="mt-1 text-sm font-medium">数据预警</div>
        </div>
        <div
          v-if="canAiEmployee"
          class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer"
          @click="go('/ai-employees')"
        >
          <div class="text-green-500 text-2xl">💬</div>
          <div class="mt-1 text-sm font-medium">AI 员工</div>
        </div>
      </div>
    </div>

    <div v-if="canAiAlert" class="mx-4 mt-4 rounded-xl bg-white p-4 shadow-sm">
      <div class="flex items-center justify-between mb-2">
        <div class="text-sm font-medium text-zinc-700">AI 数据预警</div>
        <van-button v-if="canAi" size="mini" plain :loading="alertScanning" @click="scanAlerts">扫描</van-button>
      </div>
      <div v-if="!aiAlerts.length" class="text-xs text-zinc-400">暂无预警</div>
      <div v-for="a in aiAlerts" :key="a.id" class="py-2 border-b border-zinc-50 last:border-0">
        <div class="text-sm font-medium">{{ a.title }}</div>
        <div v-if="a.summary" class="text-xs text-zinc-500 mt-1">{{ a.summary }}</div>
      </div>
    </div>

    <!-- 今日预估工资 -->
    <div v-if="auth.isEmployee" class="mx-4 -mt-3 rounded-xl bg-white p-4 shadow-sm">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-xs text-zinc-500">今日预估工资</div>
          <div class="mt-1 text-2xl font-bold text-orange-500">
            ¥{{ formatMoney(summary?.today.salary_amount) }}
          </div>
        </div>
        <div class="text-right">
          <div class="text-xs text-zinc-500">本月工资</div>
          <div class="mt-1 text-lg font-semibold text-orange-400">
            ¥{{ formatMoney(summary?.month.salary_amount) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 今日三指标 -->
    <div v-if="auth.isEmployee" class="mx-4 mt-4 grid grid-cols-3 gap-2">
      <div class="rounded-xl bg-blue-500 p-3 text-center text-white">
        <div class="text-xl font-bold">{{ summary?.my_tasks.total ?? 0 }}</div>
        <div class="text-xs opacity-90">今日任务</div>
      </div>
      <div class="rounded-xl bg-green-500 p-3 text-center text-white">
        <div class="text-xl font-bold">{{ summary?.today.total_qty ?? 0 }}</div>
        <div class="text-xs opacity-90">今日报工</div>
      </div>
      <div class="rounded-xl bg-purple-500 p-3 text-center text-white">
        <div class="text-xl font-bold">¥{{ formatMoney(summary?.today.salary_amount) }}</div>
        <div class="text-xs opacity-90">今日工资</div>
      </div>
    </div>

    <!-- 功能宫格 -->
    <div class="mx-4 mt-4">
      <div class="mb-2 text-sm font-medium text-zinc-700">功能入口</div>
      <div class="grid grid-cols-3 gap-3">
        <div class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer" @click="go('/tasks')">
          <div class="text-blue-500 text-2xl">📋</div>
          <div class="mt-1 text-sm font-medium">我的任务</div>
        </div>
        <div class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer" @click="go('/report')">
          <div class="text-green-500 text-2xl">📷</div>
          <div class="mt-1 text-sm font-medium">扫码报工</div>
        </div>
        <div class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer" @click="go('/report-manual')">
          <div class="text-orange-500 text-2xl">✏️</div>
          <div class="mt-1 text-sm font-medium">主动报工</div>
        </div>
        <div class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer" @click="go('/report-history')">
          <div class="text-indigo-500 text-2xl">📑</div>
          <div class="mt-1 text-sm font-medium">报工记录</div>
        </div>
        <div class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer" @click="go('/wages')">
          <div class="text-amber-500 text-2xl">💰</div>
          <div class="mt-1 text-sm font-medium">工资统计</div>
        </div>
        <div class="rounded-xl bg-white p-3 text-center shadow-sm cursor-pointer" @click="go('/attendance')">
          <div class="text-yellow-600 text-2xl">⏱</div>
          <div class="mt-1 text-sm font-medium">考勤打卡</div>
        </div>
      </div>
    </div>

    <!-- 快速操作 -->
    <div class="mx-4 flex gap-2">
      <van-button type="primary" block @click="go('/tasks')">查看任务</van-button>
      <van-button type="success" block @click="go('/report')">扫码报工</van-button>
      <van-button type="warning" block @click="go('/report-manual')">主动报工</van-button>
    </div>

    <div class="mx-4 mt-4">
      <van-button block type="primary" plain @click="go('/screen')">
        📊 生产看板大屏
      </van-button>
    </div>

    <!-- 待办任务卡片 -->
    <div class="mx-4 mt-4 hidden">
      <div class="mb-2 text-sm font-medium text-zinc-700">我的任务</div>
      <div class="grid grid-cols-2 gap-3">
        <div
          class="flex cursor-pointer items-center gap-3 rounded-xl bg-white p-3 shadow-sm"
          @click="go('/tasks')"
        >
          <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-500">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2M9 5h6m-3 4v6m-3-3h6" />
            </svg>
          </div>
          <div>
            <div class="text-lg font-bold text-zinc-900">{{ summary?.my_tasks.total ?? '—' }}</div>
            <div class="text-xs text-zinc-500">
              待开始 {{ summary?.my_tasks.pending ?? 0 }} / 进行中 {{ summary?.my_tasks.working ?? 0 }}
            </div>
          </div>
        </div>
        <div
          class="flex cursor-pointer items-center gap-3 rounded-xl bg-white p-3 shadow-sm"
          @click="go('/report')"
        >
          <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 text-green-500">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 4v16m8-8H4" />
            </svg>
          </div>
          <div>
            <div class="text-lg font-bold text-zinc-900">{{ summary?.month.report_count ?? '—' }}</div>
            <div class="text-xs text-zinc-500">本月报工次数</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 快捷入口 -->
    <div class="mx-4 mt-5">
      <div class="mb-2 text-sm font-medium text-zinc-700">快捷入口</div>
      <div class="grid grid-cols-5 gap-2">
        <div class="flex cursor-pointer flex-col items-center gap-1" @click="go('/tasks')">
          <div class="flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-blue-500">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2M9 5h6" />
            </svg>
          </div>
          <span class="text-xs text-zinc-600">我的任务</span>
        </div>
        <div class="flex cursor-pointer flex-col items-center gap-1" @click="go('/report')">
          <div class="flex h-12 w-12 items-center justify-center rounded-full bg-green-50 text-green-500">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z" />
            </svg>
          </div>
          <span class="text-xs text-zinc-600">扫码报工</span>
        </div>
        <div class="flex cursor-pointer flex-col items-center gap-1" @click="go('/attendance')">
          <div class="flex h-12 w-12 items-center justify-center rounded-full bg-yellow-50 text-yellow-500">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" />
            </svg>
          </div>
          <span class="text-xs text-zinc-600">考勤打卡</span>
        </div>
        <div class="flex cursor-pointer flex-col items-center gap-1" @click="go('/profile')">
          <div class="flex h-12 w-12 items-center justify-center rounded-full bg-purple-50 text-purple-500">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <span class="text-xs text-zinc-600">个人中心</span>
        </div>
        <div class="flex cursor-pointer flex-col items-center gap-1" @click="go('/wages')">
          <div class="flex h-12 w-12 items-center justify-center rounded-full bg-orange-50 text-orange-500">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 1a11 11 0 1 0 0 22 11 11 0 0 0 0-22z" /><path d="M12 6v12m-5-5h10" />
            </svg>
          </div>
          <span class="text-xs text-zinc-600">我的工资</span>
        </div>
      </div>
    </div>

    <!-- 未读消息提醒 -->
    <div
      v-if="auth.unreadNotificationCount > 0"
      class="mx-4 mt-4 cursor-pointer rounded-xl bg-red-50 p-3"
      @click="go('/notifications')"
    >
      <div class="flex items-center gap-2">
        <svg class="h-5 w-5 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        <span class="text-sm text-red-600">
          您有 {{ auth.unreadNotificationCount }} 条未读消息
        </span>
        <span class="ml-auto text-xs text-red-400">点击查看 →</span>
      </div>
    </div>

    <div class="h-8" />
  </div>
  <div v-else class="py-12 text-center text-sm text-zinc-500">加载中…</div>
</template>
