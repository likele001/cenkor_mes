<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getMyDashboardSummary, type H5DashboardSummary } from '@/api/tasks'

const loading = ref(true)
const summary = ref<H5DashboardSummary | null>(null)
const now = ref(new Date())

function tick() { now.value = new Date() }

const timeStr = computed(() =>
  now.value.toLocaleTimeString('zh-CN', { hour12: false })
)

const dateStr = computed(() => {
  const d = now.value
  const w = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 星期${w}`
})

const yieldPct = computed(() => {
  const v = summary.value?.today?.yield_rate
  return v != null ? (v * 100).toFixed(1) : '—'
})

const yieldNum = computed(() => {
  const v = summary.value?.today?.yield_rate
  return v != null ? v * 100 : 0
})

const yieldColor = computed(() => {
  const p = yieldNum.value
  if (p >= 95) return '#22c55e'
  if (p >= 85) return '#f59e0b'
  return '#ef4444'
})

const todaySalary = computed(() => {
  const v = summary.value?.today?.salary_amount ?? 0
  return `¥${v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
})

const monthSalary = computed(() => {
  const v = summary.value?.month?.salary_amount ?? 0
  return `¥${v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
})

const taskProgress = computed(() => {
  const t = summary.value?.my_tasks
  if (!t || !t.total) return 0
  return Math.round(((t.total - t.pending) / t.total) * 100)
})

function fmtNum(n: number | null | undefined): string {
  return n != null ? String(n) : '—'
}

async function load() {
  try {
    summary.value = await getMyDashboardSummary()
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
}

let dataTimer: number | null = null
let clockTimer: number | null = null

onMounted(() => {
  load()
  clockTimer = window.setInterval(tick, 1000)
  dataTimer = window.setInterval(load, 15_000)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (dataTimer) clearInterval(dataTimer)
})
</script>

<template>
  <div class="screen-page">
    <!-- 顶部 -->
    <header class="screen-header">
      <div class="flex items-center gap-2">
        <div class="screen-logo">🏭</div>
        <div>
          <div class="screen-title">辰科MES 生产看板</div>
          <div class="screen-subtitle">员工个人实时看板</div>
        </div>
      </div>
      <div class="text-right">
        <div class="screen-time">{{ timeStr }}</div>
        <div class="screen-date">{{ dateStr }}</div>
      </div>
    </header>

    <!-- KPI 卡片 -->
    <section class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">今日合格</div>
        <div class="kpi-value kpi-green">{{ fmtNum(summary?.today?.good_qty) }}</div>
        <div class="kpi-unit">件</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">今日不良</div>
        <div class="kpi-value kpi-red">{{ fmtNum(summary?.today?.bad_qty) }}</div>
        <div class="kpi-unit">件</div>
      </div>
      <div class="kpi-card kpi-ring-card">
        <div class="kpi-label">良率</div>
        <svg width="90" height="90" viewBox="0 0 90 90">
          <circle r="34" cx="45" cy="45" fill="none" stroke="#1a1a2e" stroke-width="7" />
          <circle
            r="34" cx="45" cy="45" fill="none"
            :stroke="yieldColor" stroke-width="7" stroke-linecap="round"
            :stroke-dasharray="2 * Math.PI * 34"
            :stroke-dashoffset="2 * Math.PI * 34 * (1 - yieldNum / 100)"
            transform="rotate(-90, 45, 45)"
            class="ring-fill"
          />
          <text x="45" y="42" text-anchor="middle" fill="#e2e8f0" font-size="18" font-weight="700">{{ yieldPct }}%</text>
          <text x="45" y="58" text-anchor="middle" fill="#64748b" font-size="9">良率</text>
        </svg>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">今日工资</div>
        <div class="kpi-value kpi-sky">{{ todaySalary }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">本月工资</div>
        <div class="kpi-value kpi-amber">{{ monthSalary }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">今日总产量</div>
        <div class="kpi-value kpi-emerald">{{ fmtNum(summary?.today?.total_qty) }}</div>
        <div class="kpi-unit">件</div>
      </div>
    </section>

    <!-- 任务进度 -->
    <section class="panel task-panel">
      <div class="panel-title">我的任务进度</div>
      <div class="task-stats">
        <div class="task-stat-item">
          <div class="task-stat-num">{{ summary?.my_tasks?.total ?? 0 }}</div>
          <div class="task-stat-label">总任务</div>
        </div>
        <div class="task-stat-item">
          <div class="task-stat-num text-green-400">{{ summary?.my_tasks ? (summary.my_tasks.total - summary.my_tasks.pending - summary.my_tasks.working) : 0 }}</div>
          <div class="task-stat-label">已完成</div>
        </div>
        <div class="task-stat-item">
          <div class="task-stat-num text-blue-400">{{ summary?.my_tasks?.working ?? 0 }}</div>
          <div class="task-stat-label">进行中</div>
        </div>
        <div class="task-stat-item">
          <div class="task-stat-num text-zinc-400">{{ summary?.my_tasks?.pending ?? 0 }}</div>
          <div class="task-stat-label">待开始</div>
        </div>
      </div>
      <div class="progress-bar-wrap">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: taskProgress + '%' }"></div>
        </div>
        <span class="progress-text">{{ taskProgress }}%</span>
      </div>
    </section>

    <!-- 本月统计 -->
    <section class="panel month-panel">
      <div class="panel-title">本月统计</div>
      <div class="month-stats">
        <div class="month-stat-item">
          <div class="month-stat-icon">📊</div>
          <div>
            <div class="month-stat-num">{{ summary?.month?.report_count ?? 0 }}</div>
            <div class="month-stat-label">报工次数</div>
          </div>
        </div>
        <div class="month-stat-item">
          <div class="month-stat-icon">💰</div>
          <div>
            <div class="month-stat-num">{{ monthSalary }}</div>
            <div class="month-stat-label">累计工资</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 底部提示 -->
    <footer class="screen-footer">
      <div class="alert-track">
        <span class="alert-item">💡 数据每15秒自动刷新 · 如有疑问请联系班组长</span>
      </div>
    </footer>

    <!-- 加载遮罩 -->
    <div v-if="loading" class="loading-mask">
      <div class="loading-spinner"></div>
      <div class="loading-text">加载中…</div>
    </div>
  </div>
</template>

<style scoped>
.screen-page {
  --bg: #0f0f1a;
  --card: #1a1a2e;
  --border: #2a2a3e;
  --text: #e2e8f0;
  --muted: #64748b;
  position: fixed; inset: 0;
  background: var(--bg); color: var(--text);
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  display: flex; flex-direction: column; padding: 1rem 1.2rem;
  overflow-y: auto; overflow-x: hidden;
  user-select: none;
}

.screen-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 1rem;
}
.screen-logo { font-size: 1.8rem; }
.screen-title { font-size: 1.2rem; font-weight: 700; letter-spacing: 0.05em; }
.screen-subtitle { font-size: 0.7rem; color: var(--muted); }
.screen-time { font-size: 2.2rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1; color: #38bdf8; }
.screen-date { font-size: 0.75rem; color: var(--muted); margin-top: 2px; }

.kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-bottom: 0.6rem; }
.kpi-card {
  background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 0.6rem 0.4rem; text-align: center;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.kpi-card.kpi-ring-card { padding: 0.3rem; }
.kpi-label { font-size: 0.65rem; color: var(--muted); letter-spacing: 0.04em; margin-bottom: 0.15rem; }
.kpi-value { font-size: 1.6rem; font-weight: 800; font-variant-numeric: tabular-nums; line-height: 1.2; }
.kpi-unit { font-size: 0.6rem; color: var(--muted); }
.kpi-green { color: #22c55e; }
.kpi-red { color: #ef4444; }
.kpi-amber { color: #f59e0b; }
.kpi-sky { color: #38bdf8; }
.kpi-emerald { color: #34d399; }

.ring-fill { transition: stroke-dashoffset 1s ease; }

.panel {
  background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 0.7rem 0.8rem; margin-bottom: 0.6rem;
}
.panel-title { font-size: 0.8rem; font-weight: 600; color: #94a3b8; margin-bottom: 0.5rem; letter-spacing: 0.03em; }

.task-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.4rem; text-align: center; margin-bottom: 0.6rem; }
.task-stat-num { font-size: 1.3rem; font-weight: 700; }
.task-stat-label { font-size: 0.6rem; color: var(--muted); }

.progress-bar-wrap { display: flex; align-items: center; gap: 0.5rem; }
.progress-bar-bg { flex: 1; height: 10px; background: #222234; border-radius: 5px; overflow: hidden; }
.progress-bar-fill { height: 100%; border-radius: 5px; background: linear-gradient(90deg, #6366f1, #8b5cf6); transition: width 0.8s ease; min-width: 4px; }
.progress-text { font-size: 0.75rem; font-weight: 600; color: #a78bfa; width: 3rem; text-align: right; }

.month-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; }
.month-stat-item {
  display: flex; align-items: center; gap: 0.6rem;
  background: rgba(255,255,255,0.03); border-radius: 8px; padding: 0.5rem;
}
.month-stat-icon { font-size: 1.5rem; }
.month-stat-num { font-size: 1rem; font-weight: 700; }
.month-stat-label { font-size: 0.6rem; color: var(--muted); }

.screen-footer {
  margin-top: auto;
  padding: 0.4rem 0.8rem;
  background: rgba(56,189,248,0.08); border: 1px solid rgba(56,189,248,0.15);
  border-radius: 8px; height: 1.8rem; overflow: hidden;
  display: flex; align-items: center;
}
.alert-track { flex: 1; overflow: hidden; position: relative; }
.alert-item { font-size: 0.7rem; color: #7dd3fc; }

.loading-mask {
  position: fixed; inset: 0; z-index: 50;
  background: var(--bg); display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 0.8rem;
}
.loading-spinner {
  width: 2.5rem; height: 2.5rem; border: 3px solid var(--border);
  border-top-color: #6366f1; border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-text { font-size: 0.8rem; color: var(--muted); }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
