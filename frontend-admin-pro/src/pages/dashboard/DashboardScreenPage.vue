<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { dashboardApi, type DashboardSummaryOut, type DashboardChartsOut } from '@/api/dashboard'
import { kanbanApi, type KanbanOrderOut } from '@/api/kanban'
import { connectDashboardWS } from '@/utils/ws'

const { t } = useI18n()

// ===== 时钟 =====
const now = ref(new Date())
function tick() { now.value = new Date() }
const timeStr = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false }))
const dateStr = computed(() => {
  const d = now.value
  const w = [t('dashboard.screen.sunday'), t('dashboard.screen.monday'), t('dashboard.screen.tuesday'), t('dashboard.screen.wednesday'), t('dashboard.screen.thursday'), t('dashboard.screen.friday'), t('dashboard.screen.saturday')][d.getDay()]
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')} ${t('dashboard.screen.week')}${w}`
})

// ===== 数据 =====
const loading = ref(true)
const summary = ref<DashboardSummaryOut | null>(null)
const charts = ref<DashboardChartsOut | null>(null)
const orders = ref<KanbanOrderOut[]>([])
const alerts = ref<string[]>([])

// ===== 全屏 =====
const fullscreen = ref(false)
async function toggleFullscreen() {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen?.()
    fullscreen.value = true
  } else {
    await document.exitFullscreen?.()
    fullscreen.value = false
  }
}
function onFSChange() { fullscreen.value = !!document.fullscreenElement }

// ===== 自动轮播 =====
const scrollIdx = ref(0)
const scrollStep = 1
const rowH = 56
const visibleRows = 8

const scrollOrders = computed(() => {
  const base = orders.value
  if (base.length <= visibleRows) return base
  return [...base, ...base.slice(0, visibleRows)]
})

const barMax = computed(() => {
  const max = Math.max(...(charts.value?.process_rank || []).map((p) => p.good_qty + p.bad_qty), 1)
  return max
})

// ===== 数据加载 =====
async function load() {
  try {
    const [s, c, o] = await Promise.all([
      dashboardApi.summary().catch(() => null),
      dashboardApi.charts(7).catch(() => null),
      kanbanApi.listOrders({ offset: 0, limit: 50 }).catch(() => ({ items: [] as KanbanOrderOut[] })),
    ])
    if (s) summary.value = s as DashboardSummaryOut
    if (c) charts.value = c as DashboardChartsOut
    const orderData = (o as any)?.items ?? []
    orders.value = orderData as KanbanOrderOut[]
    buildAlerts(s)
  } finally { loading.value = false }
}

function buildAlerts(s: DashboardSummaryOut | null) {
  const list: string[] = []
  if (!s) return
  const reports = s.reports
  if (reports?.pending_audit > 0) list.push(`⚠️ ${t('dashboard.screen.pendingAudit')} ${reports.pending_audit} ${t('dashboard.screen.items')}`)
  const overdue = orders.value.filter((o) => o.warning_level === 'overdue')
  if (overdue.length) list.push(`🚨 ${t('dashboard.screen.overdueOrders')} ${overdue.length} ${t('dashboard.screen.orders')}`)
  const warn = orders.value.filter((o) => o.warning_level === 'warn')
  if (warn.length) list.push(`⚡ ${t('dashboard.screen.aboutToOverdue')} ${warn.length} ${t('dashboard.screen.orders')}`)
  if (!list.length) list.push(`✅ ${t('dashboard.screen.allNormal')}`)
  alerts.value = list
}

// ===== 定时器 =====
let dataTimer: number | null = null
let scrollTimer: number | null = null
let closeWs: (() => void) | null = null
const wsLive = ref(false)

onMounted(() => {
  load()
  closeWs = connectDashboardWS(
    () => load(),
    () => {
      wsLive.value = false
      if (!dataTimer) dataTimer = window.setInterval(load, 15_000)
    },
  )
  wsLive.value = true
  scrollTimer = window.setInterval(() => {
    if (orders.value.length > visibleRows) {
      scrollIdx.value += scrollStep
      if (scrollIdx.value >= orders.value.length) scrollIdx.value = 0
    }
  }, 3_000)
  const ci = window.setInterval(tick, 1000)
  document.addEventListener('fullscreenchange', onFSChange)
  onUnmounted(() => {
    closeWs?.()
    if (dataTimer) clearInterval(dataTimer)
    if (scrollTimer) clearInterval(scrollTimer)
    clearInterval(ci)
    document.removeEventListener('fullscreenchange', onFSChange)
  })
})

// ===== 工具 =====
const yieldPct = computed(() => {
  const v = summary.value?.today?.yield_rate
  return v != null ? (v * 100).toFixed(1) : '—'
})
const yieldAngles = computed(() => {
  const p = parseFloat(yieldPct.value)
  return isNaN(p) ? 0 : (p / 100) * 360
})
const todaySalary = computed(() => {
  const v = summary.value?.today?.salary_amount ?? 0
  return `¥${v.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
})
const orderProgress = (o: KanbanOrderOut) => Math.max(0, Math.min(100, Math.round((o.progress ?? 0) * 100)))
const barColor = (lvl: string) =>
  lvl === 'overdue' ? '#ef4444' : lvl === 'warn' ? '#f59e0b' : '#22c55e'
const dueLabel = (o: KanbanOrderOut) => {
  if (!o.due_date) return '—'
  const dd = o.due_days
  if (dd == null) return o.due_date
  return dd < 0 ? `${t('dashboard.screen.overdue')}${-dd}${t('dashboard.screen.days')}` : `${dd}${t('dashboard.screen.daysLater')}`
}

// ===== 环形进度 SVG =====
const ringSize = 120
const ringStroke = 8
const ringR = (ringSize - ringStroke) / 2
const ringCirc = 2 * Math.PI * ringR
</script>

<template>
  <div
    class="tv-dashboard tv-screen"
    :class="{ 'is-fullscreen': fullscreen }"
    @dblclick="toggleFullscreen"
  >
    <!-- 顶部：时钟 + 标题 -->
    <header class="tv-header">
      <div class="flex items-center gap-3">
        <div class="tv-logo">🏭</div>
        <div>
          <div class="tv-title">{{ t('dashboard.screen.title') }}</div>
          <div class="tv-subtitle">{{ t('dashboard.screen.subtitle') }}</div>
        </div>
      </div>
      <div class="tv-datetime">
        <div class="tv-time">{{ timeStr }}</div>
        <div class="tv-date">{{ dateStr }}</div>
      </div>
      <button class="tv-fs-btn" @click="toggleFullscreen">
        {{ fullscreen ? t('dashboard.screen.exitFullscreen') : t('dashboard.screen.fullscreen') }}
      </button>
    </header>

    <!-- KPI 卡片 -->
    <section class="tv-kpi-grid">
      <div class="tv-kpi-card">
        <div class="tv-kpi-label">{{ t('dashboard.screen.todayQualified') }}</div>
        <div class="tv-kpi-value tv-kpi-green">{{ summary?.today?.good_qty ?? 0 }}</div>
      </div>
      <div class="tv-kpi-card">
        <div class="tv-kpi-label">{{ t('dashboard.screen.todayDefective') }}</div>
        <div class="tv-kpi-value tv-kpi-red">{{ summary?.today?.bad_qty ?? 0 }}</div>
      </div>
      <div class="tv-kpi-card tv-kpi-ring-card">
        <div class="tv-kpi-label">{{ t('dashboard.screen.yieldRate') }}</div>
        <svg :width="ringSize" :height="ringSize" class="tv-ring">
          <circle :r="ringR" :cx="ringSize / 2" :cy="ringSize / 2" fill="none" stroke="#2a2a3a" :stroke-width="ringStroke" />
          <circle
            :r="ringR" :cx="ringSize / 2" :cy="ringSize / 2" fill="none"
            stroke="#22c55e" :stroke-width="ringStroke" stroke-linecap="round"
            :stroke-dasharray="ringCirc"
            :stroke-dashoffset="ringCirc - (yieldAngles / 360) * ringCirc"
            transform="rotate(-90, 60, 60)"
            class="tv-ring-fill"
          />
          <text x="60" y="56" text-anchor="middle" fill="#e2e8f0" font-size="24" font-weight="700">{{ yieldPct }}%</text>
          <text x="60" y="76" text-anchor="middle" fill="#64748b" font-size="10">{{ t('dashboard.screen.yieldRate') }}</text>
        </svg>
      </div>
      <div class="tv-kpi-card">
        <div class="tv-kpi-label">{{ t('dashboard.screen.pendingAudit') }}</div>
        <div class="tv-kpi-value tv-kpi-amber">{{ summary?.reports?.pending_audit ?? 0 }}</div>
      </div>
      <div class="tv-kpi-card">
        <div class="tv-kpi-label">{{ t('dashboard.screen.todayOutput') }}</div>
        <div class="tv-kpi-value tv-kpi-sky" style="font-size:1.6rem">{{ todaySalary }}</div>
      </div>
      <div class="tv-kpi-card">
        <div class="tv-kpi-label">{{ t('dashboard.screen.taskCompleted') }}</div>
        <div class="tv-kpi-value tv-kpi-emerald">
          <span>{{ summary?.tasks?.done ?? 0 }}</span>
          <span class="text-base text-zinc-400">/{{ summary?.tasks?.total ?? 0 }}</span>
        </div>
      </div>
    </section>

    <!-- 主体：订单进度 + 工序排行 -->
    <section class="tv-main-grid">
      <!-- 左侧：订单进度 -->
      <div class="tv-panel">
        <div class="tv-panel-title">{{ t('dashboard.screen.orderProgress') }} · {{ t('dashboard.screen.total') }} {{ orders.length }} {{ t('dashboard.screen.ordersUnit') }}</div>
        <div class="tv-list-header">
          <span class="w-36 shrink-0">{{ t('dashboard.screen.orderNo') }}</span>
          <span class="w-16 shrink-0 text-center">{{ t('dashboard.screen.customer') }}</span>
          <span class="w-20 shrink-0 text-center">{{ t('dashboard.screen.deliveryDate') }}</span>
          <span class="w-24 shrink-0 text-center">{{ t('dashboard.screen.progress') }}</span>
          <span class="flex-1 min-w-0">{{ t('dashboard.screen.progressBar') }}</span>
        </div>
        <div
          class="tv-list-viewport"
          :style="{ height: `${Math.min(visibleRows, Math.max(1, orders.length || 1)) * rowH}px` }"
        >
          <div class="tv-list-body" :style="{ transform: `translateY(-${scrollIdx * rowH}px)`, transition: 'transform 0.6s ease' }">
            <div
              v-for="(o, i) in scrollOrders" :key="`${o.id}-${i}`"
              class="tv-list-row"
              :class="{ 'tv-row-overdue': o.warning_level === 'overdue', 'tv-row-warn': o.warning_level === 'warn' }"
              :style="{ height: rowH + 'px' }"
            >
              <span class="w-36 shrink-0 truncate font-mono text-sm">{{ o.code }}</span>
              <span class="w-16 shrink-0 text-center text-xs truncate">{{ o.customer?.name?.slice(0, 4) || '—' }}</span>
              <span :class="['w-20 shrink-0 text-center text-xs', o.warning_level === 'overdue' ? 'text-red-400' : '']">
                {{ dueLabel(o) }}
              </span>
              <span class="w-24 shrink-0 text-center font-mono text-sm">{{ o.done_qty }}/{{ o.total_qty }}</span>
              <div class="flex-1 min-w-0 flex items-center gap-2">
                <div class="tv-progress-bg flex-1">
                  <div
                    class="tv-progress-fill"
                    :style="{ width: orderProgress(o) + '%', backgroundColor: barColor(o.warning_level) }"
                  />
                </div>
                <span class="text-xs w-10 text-right text-zinc-400">{{ orderProgress(o) }}%</span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!orders.length" class="tv-empty">{{ t('dashboard.screen.noOrders') }}</div>
      </div>

      <!-- 右侧：工序负荷排行 -->
      <div class="tv-panel">
        <div class="tv-panel-title">{{ t('dashboard.screen.processLoad') }} · {{ t('dashboard.screen.recent7Days') }}</div>
        <div class="tv-list-header">
          <span class="w-20 shrink-0">{{ t('dashboard.screen.process') }}</span>
          <span class="flex-1 text-right">{{ t('dashboard.screen.output') }}</span>
        </div>
        <div class="space-y-2 mt-2">
          <div v-for="p in (charts?.process_rank || []).slice(0, 8)" :key="p.process_id" class="flex items-center gap-2">
            <span class="w-20 shrink-0 text-sm truncate">{{ p.process_name }}</span>
            <div class="tv-progress-bg flex-1">
              <div
                class="tv-progress-fill"
                :style="{ width: Math.max(3, ((p.good_qty + p.bad_qty) / barMax) * 100) + '%', backgroundColor: p.bad_qty > 0 ? '#f59e0b' : '#6366f1' }"
              />
            </div>
            <span class="text-sm font-mono w-20 text-right">{{ p.good_qty }}</span>
            <span v-if="p.bad_qty > 0" class="text-xs text-red-400 w-12 text-right">{{ p.bad_qty }}{{ t('dashboard.screen.defective') }}</span>
          </div>
          <div v-if="!charts?.process_rank?.length" class="tv-empty">{{ t('dashboard.screen.noData') }}</div>
        </div>
      </div>
    </section>

    <!-- 底部：异常报警滚动条 -->
    <footer class="tv-alert-bar">
      <div class="tv-alert-label">📢</div>
      <div class="tv-alert-track">
        <div class="tv-alert-scroll" v-if="alerts.length">
          <span v-for="(a, i) in [...alerts, ...alerts]" :key="i" class="tv-alert-item">{{ a }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ── TV 大屏：独立暗色主题，不受 admin 暗色模式影响 ── */
.tv-screen .tv-dashboard,
.tv-dashboard {
  --bg: var(--tv-bg, #0f0f1a);
  --card: var(--tv-card, #1a1a2e);
  --border: var(--tv-border, #2a2a3e);
  --text: var(--tv-text, #e2e8f0);
  --muted: var(--tv-muted, #64748b);
  position: fixed; inset: 0;
  background: var(--bg); color: var(--text);
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  display: flex; flex-direction: column; padding: 1.2rem 1.5rem;
  overflow: hidden;
  user-select: none;
}
.tv-dashboard.is-fullscreen { cursor: none; }

/* 顶部 */
.tv-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
.tv-logo { font-size: 2rem; }
.tv-title { font-size: 1.4rem; font-weight: 700; letter-spacing: 0.05em; }
.tv-subtitle { font-size: 0.75rem; color: var(--muted); }
.tv-datetime { text-align: right; }
.tv-time { font-size: 2.8rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1; color: #38bdf8; }
.tv-date { font-size: 0.85rem; color: var(--muted); margin-top: 2px; }
.tv-fs-btn {
  position: fixed; bottom: 0.8rem; right: 0.8rem;
  background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
  color: var(--muted); padding: 0.3rem 0.6rem; border-radius: 6px;
  font-size: 0.7rem; cursor: pointer; z-index: 100; opacity: 0.3;
  transition: opacity 0.3s;
}
.tv-dashboard:hover .tv-fs-btn { opacity: 1; }

/* KPI 区域 */
.tv-kpi-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.6rem; margin-bottom: 0.8rem; }
.tv-kpi-card {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 0.8rem 0.6rem; text-align: center;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.tv-kpi-card.tv-kpi-ring-card { padding: 0.4rem; }
.tv-kpi-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.2rem; }
.tv-kpi-value { font-size: 2.2rem; font-weight: 800; font-variant-numeric: tabular-nums; line-height: 1.2; }
.tv-kpi-green { color: #22c55e; }
.tv-kpi-red { color: #ef4444; }
.tv-kpi-amber { color: #f59e0b; }
.tv-kpi-sky { color: #38bdf8; }
.tv-kpi-emerald { color: #34d399; }

/* 环形进度 */
.tv-ring { display: block; }
.tv-ring-fill { transition: stroke-dashoffset 1s ease; }

/* 主区域 */
.tv-main-grid { display: grid; grid-template-columns: 3fr 2fr; gap: 0.8rem; flex: 1; min-height: 0; }
.tv-panel {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 0.8rem 1rem; display: flex; flex-direction: column;
}
.tv-panel-title { font-size: 0.85rem; font-weight: 600; margin-bottom: 0.6rem; color: #94a3b8; letter-spacing: 0.03em; }

/* 列表 */
.tv-list-header { display: flex; gap: 0.4rem; font-size: 0.7rem; color: var(--muted); margin-bottom: 0.3rem; padding: 0 0.2rem; }
.tv-list-viewport { overflow: hidden; flex: 1; }
.tv-list-body { will-change: transform; }
.tv-list-row {
  display: flex; align-items: center; gap: 0.4rem;
  padding: 0 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.04);
  transition: background 0.2s;
}
.tv-list-row:hover { background: rgba(255,255,255,0.04); }
.tv-row-overdue { background: rgba(239,68,68,0.08); }
.tv-row-warn { background: rgba(245,158,11,0.06); }
.tv-empty { text-align: center; color: var(--muted); font-size: 0.85rem; padding: 2rem 0; }

/* 进度条 */
.tv-progress-bg { height: 12px; background: #222234; border-radius: 6px; overflow: hidden; }
.tv-progress-fill { height: 100%; border-radius: 6px; transition: width 0.8s ease; min-width: 4px; }

/* 底部报警 */
.tv-alert-bar {
  display: flex; align-items: center; gap: 0.5rem;
  margin-top: 0.6rem; padding: 0.4rem 0.8rem;
  background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2); border-radius: 8px;
  height: 2rem; overflow: hidden;
}
.tv-alert-label { font-size: 0.85rem; white-space: nowrap; }
.tv-alert-track { flex: 1; overflow: hidden; position: relative; }
.tv-alert-scroll {
  display: flex; gap: 3rem; white-space: nowrap;
  animation: scroll-left 20s linear infinite;
}
.tv-alert-item { font-size: 0.8rem; color: #fca5a5; }
@keyframes scroll-left {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}
</style>
