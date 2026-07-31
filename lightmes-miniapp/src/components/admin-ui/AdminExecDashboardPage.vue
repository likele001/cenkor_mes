<template>
  <view class="adm-page exec-dash">
    <view class="hero">
      <text class="hero-title">老板看板</text>
      <text class="hero-sub">{{ periodLabel }} · {{ updatedAt }}</text>
    </view>

    <!-- 期间切换 -->
    <view class="period-bar">
      <view
        v-for="p in periods"
        :key="p.value"
        class="period-chip"
        :class="{ active: period === p.value }"
        @click="onPeriodChange(p.value)"
      >
        <text>{{ p.label }}</text>
      </view>
    </view>

    <view v-if="loading && !summary" class="tip">加载中...</view>

    <!-- 5 大指标卡片 -->
    <view v-else class="kpi-grid">
      <view class="kpi-card revenue">
        <text class="kpi-label">销售额</text>
        <text class="kpi-value">¥{{ fmtAmount(summary?.revenue.value) }}</text>
        <text class="kpi-change" :class="changeClass(summary?.revenue.change_pct)">
          {{ fmtChange(summary?.revenue.change_pct) }} 环比
        </text>
      </view>
      <view class="kpi-card margin">
        <text class="kpi-label">毛利率</text>
        <text class="kpi-value">{{ fmtPct(summary?.profit_margin.value) }}</text>
        <text class="kpi-change" :class="changeClass(summary?.profit_margin.change_pct)">
          {{ fmtChange(summary?.profit_margin.change_pct) }} 环比
        </text>
      </view>
      <view class="kpi-card delivery">
        <text class="kpi-label">准交率</text>
        <text class="kpi-value">{{ fmtPct(summary?.delivery_rate.value) }}</text>
        <text class="kpi-change" :class="changeClass(summary?.delivery_rate.change_pct)">
          {{ fmtChange(summary?.delivery_rate.change_pct) }} 环比
        </text>
      </view>
      <view class="kpi-card collection">
        <text class="kpi-label">回款率</text>
        <text class="kpi-value">{{ fmtPct(summary?.collection_rate.value) }}</text>
        <text class="kpi-change" :class="changeClass(summary?.collection_rate.change_pct)">
          {{ fmtChange(summary?.collection_rate.change_pct) }} 环比
        </text>
      </view>
      <view class="kpi-card capacity">
        <text class="kpi-label">产能利用率</text>
        <text class="kpi-value">{{ fmtPct(summary?.capacity_utilization.value) }}</text>
        <text class="kpi-change" :class="changeClass(summary?.capacity_utilization.change_pct)">
          {{ fmtChange(summary?.capacity_utilization.change_pct) }} 环比
        </text>
      </view>
    </view>

    <!-- 销售趋势（最近 14 天） -->
    <view class="section">
      <text class="section-title">销售趋势（近 14 天）</text>
      <view v-if="trend.length" class="trend-chart">
        <view
          v-for="(t, i) in trend"
          :key="i"
          class="bar"
          :style="{ height: barHeight(t.amount) + 'rpx' }"
        >
          <text class="bar-date">{{ t.date.slice(5) }}</text>
        </view>
      </view>
      <view v-else class="empty">暂无数据</view>
    </view>

    <!-- 客户排名 -->
    <view class="section">
      <text class="section-title">客户 Top5</text>
      <view v-if="topCustomers.length" class="rank-list">
        <view v-for="(c, i) in topCustomers" :key="i" class="rank-row">
          <text class="rank-no">{{ i + 1 }}</text>
          <text class="rank-name ellipsis">{{ c.customer_name }}</text>
          <text class="rank-meta">¥{{ fmtAmount(c.amount) }}</text>
        </view>
      </view>
      <view v-else class="empty">暂无数据</view>
    </view>

    <!-- 产品排名 -->
    <view class="section">
      <text class="section-title">产品 Top5</text>
      <view v-if="topSkus.length" class="rank-list">
        <view v-for="(s, i) in topSkus" :key="i" class="rank-row">
          <text class="rank-no">{{ i + 1 }}</text>
          <text class="rank-name ellipsis">{{ s.sku_name }}</text>
          <text class="rank-meta">¥{{ fmtAmount(s.amount) }}</text>
        </view>
      </view>
      <view v-else class="empty">暂无数据</view>
    </view>

    <!-- 逾期订单 -->
    <view v-if="overdueOrders.length" class="section overdue">
      <text class="section-title">⚠ 逾期订单（{{ overdueOrders.length }}）</text>
      <view class="rank-list">
        <view v-for="o in overdueOrders" :key="o.id" class="rank-row overdue-row">
          <text class="rank-name ellipsis">{{ o.code }} · {{ o.customer_name }}</text>
          <text class="rank-meta red">逾期 {{ o.days_overdue }} 天</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
import {
  execDashboardApi,
  type ExecSummary,
  type TrendItem,
  type TopCustomerItem,
  type TopSkuItem,
  type OverdueOrderItem,
} from '@/api/admin/exec-dashboard'

const { requirePermission } = usePermission()

const period = ref<'today' | 'week' | 'month' | 'quarter'>('month')
const periods = [
  { value: 'today' as const, label: '今日' },
  { value: 'week' as const, label: '本周' },
  { value: 'month' as const, label: '本月' },
  { value: 'quarter' as const, label: '本季' },
]

const loading = ref(false)
const summary = ref<ExecSummary | null>(null)
const trend = ref<TrendItem[]>([])
const topCustomers = ref<TopCustomerItem[]>([])
const topSkus = ref<TopSkuItem[]>([])
const overdueOrders = ref<OverdueOrderItem[]>([])

const updatedAt = ref('')
const periodLabel = computed(() => periods.find((p) => p.value === period.value)?.label || '')

const trendMax = computed(() => {
  const m = Math.max(...trend.value.map((t) => t.amount), 0)
  return m || 1
})

function fmtAmount(n: number | undefined): string {
  if (n === undefined || n === null) return '0'
  if (n >= 10000) return (n / 10000).toFixed(2) + ' 万'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPct(n: number | undefined): string {
  if (n === undefined || n === null) return '0%'
  return n.toFixed(1) + '%'
}

function fmtChange(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return (n >= 0 ? '↑ ' : '↓ ') + Math.abs(n).toFixed(1) + '%'
}

function changeClass(n: number | null | undefined): string {
  if (n === null || n === undefined) return ''
  return n >= 0 ? 'up' : 'down'
}

function barHeight(amount: number): number {
  return Math.max(8, Math.round((amount / trendMax.value) * 120))
}

function onPeriodChange(p: 'today' | 'week' | 'month' | 'quarter') {
  if (p === period.value) return
  period.value = p
  reload()
}

async function reload() {
  if (!requirePermission('exec_dashboard.view')) return
  loading.value = true
  try {
    const [s, tr, tc, ts, ov] = await Promise.all([
      execDashboardApi.summary(period.value),
      execDashboardApi.revenueTrend(14),
      execDashboardApi.topCustomers(period.value, 5),
      execDashboardApi.topSkus(period.value, 5),
      execDashboardApi.overdueOrders(10),
    ])
    summary.value = s
    trend.value = tr || []
    topCustomers.value = tc || []
    topSkus.value = ts || []
    overdueOrders.value = ov || []
    updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch (e) {
    console.error('exec dashboard load error', e)
  } finally {
    loading.value = false
  }
}

onShow(reload)
</script>

<style scoped lang="scss">
.exec-dash { background: #f6f8fb; min-height: 100vh; padding: 24rpx; box-sizing: border-box; }

.hero { padding: 16rpx 8rpx 24rpx; }
.hero-title { display: block; font-size: 40rpx; font-weight: 700; color: #0f172a; }
.hero-sub { display: block; font-size: 24rpx; color: #64748b; margin-top: 6rpx; }

.period-bar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.period-chip {
  flex: 1; text-align: center; padding: 14rpx 0;
  background: #fff; border-radius: 12rpx; font-size: 26rpx; color: #475569;
  border: 2rpx solid transparent;
}
.period-chip.active { background: #4f46e5; color: #fff; }

.tip { text-align: center; padding: 40rpx 0; color: #64748b; font-size: 26rpx; }
.empty { text-align: center; padding: 24rpx 0; color: #94a3b8; font-size: 24rpx; }

/* KPI grid */
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; }
.kpi-card { background: #fff; border-radius: 16rpx; padding: 24rpx; box-shadow: 0 2rpx 8rpx rgba(15, 23, 42, 0.04); }
.kpi-label { display: block; font-size: 24rpx; color: #64748b; }
.kpi-value { display: block; font-size: 40rpx; font-weight: 700; color: #0f172a; margin: 8rpx 0; }
.kpi-change { display: block; font-size: 22rpx; color: #94a3b8; }
.kpi-change.up { color: #10b981; }
.kpi-change.down { color: #ef4444; }

/* Section */
.section { background: #fff; border-radius: 16rpx; padding: 24rpx; margin-top: 20rpx; box-shadow: 0 2rpx 8rpx rgba(15, 23, 42, 0.04); }
.section.overdue { border-left: 6rpx solid #ef4444; }
.section-title { display: block; font-size: 28rpx; font-weight: 600; color: #0f172a; margin-bottom: 16rpx; }

/* Trend bars */
.trend-chart { display: flex; align-items: flex-end; gap: 6rpx; height: 160rpx; padding: 8rpx 0; }
.bar {
  flex: 1; min-width: 12rpx; background: linear-gradient(180deg, #818cf8 0%, #4f46e5 100%);
  border-radius: 4rpx 4rpx 0 0; position: relative; display: flex; align-items: flex-end; justify-content: center;
}
.bar-date { position: absolute; bottom: -28rpx; font-size: 16rpx; color: #94a3b8; transform: scale(0.85); white-space: nowrap; }

/* Rank list */
.rank-list { display: flex; flex-direction: column; gap: 12rpx; }
.rank-row { display: flex; align-items: center; gap: 12rpx; padding: 12rpx 0; border-bottom: 2rpx solid #f1f5f9; }
.rank-row:last-child { border-bottom: 0; }
.rank-no { width: 36rpx; height: 36rpx; line-height: 36rpx; text-align: center; background: #e0e7ff; color: #4f46e5; border-radius: 50%; font-size: 22rpx; font-weight: 600; flex-shrink: 0; }
.rank-name { flex: 1; font-size: 26rpx; color: #0f172a; }
.rank-meta { font-size: 24rpx; color: #475569; flex-shrink: 0; }
.rank-meta.red { color: #ef4444; }
.ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.overdue-row { padding: 14rpx 0; }
</style>
