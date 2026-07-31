<template>
  <AdminPage :title="t('execDashboard.title')">
    <template #actions>
      <el-radio-group v-model="period" size="default" @change="loadAll">
        <el-radio-button value="today">{{ t('execDashboard.today') }}</el-radio-button>
        <el-radio-button value="week">{{ t('execDashboard.week') }}</el-radio-button>
        <el-radio-button value="month">{{ t('execDashboard.month') }}</el-radio-button>
        <el-radio-button value="quarter">{{ t('execDashboard.quarter') }}</el-radio-button>
      </el-radio-group>
    </template>

    <div v-loading="loading" class="space-y-6 mt-4">
      <!-- KPI Cards -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <div v-for="card in kpiCards" :key="card.key"
             class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-sm">
          <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{ card.label }}</div>
          <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {{ card.display }}
          </div>
          <div class="flex items-center gap-1 mt-1 text-xs"
               :class="card.change >= 0 ? 'text-emerald-600' : 'text-red-500'">
            <el-icon v-if="card.change !== 0"><component :is="card.change >= 0 ? 'Top' : 'Bottom'" /></el-icon>
            <span v-if="card.change !== null">{{ Math.abs(card.change).toFixed(1) }}%</span>
            <span class="text-gray-400 ml-1">{{ t('execDashboard.vsPrev') }}</span>
          </div>
        </div>
      </div>

      <!-- Charts Row -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- Revenue Trend -->
        <div class="lg:col-span-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-sm">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{{ t('execDashboard.revenueTrend') }}</h3>
          <VChart :option="trendOption" autoresize style="height: 280px" />
        </div>
        <!-- Order Status Pie -->
        <div class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-sm">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{{ t('execDashboard.orderStatus') }}</h3>
          <VChart :option="pieOption" autoresize style="height: 280px" />
        </div>
      </div>

      <!-- Tables Row -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Top Customers -->
        <div class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-sm">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{{ t('execDashboard.topCustomers') }}</h3>
          <el-table :data="topCustomers" size="small" stripe>
            <el-table-column type="index" width="50" />
            <el-table-column prop="customer_name" :label="t('execDashboard.customerName')" min-width="120" show-overflow-tooltip />
            <el-table-column prop="order_count" :label="t('execDashboard.orderCount')" width="100" align="right" />
            <el-table-column :label="t('execDashboard.amount')" width="130" align="right">
              <template #default="{ row }">¥{{ fmtNum(row.amount) }}</template>
            </el-table-column>
          </el-table>
        </div>
        <!-- Top SKUs -->
        <div class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-sm">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{{ t('execDashboard.topSkus') }}</h3>
          <el-table :data="topSkus" size="small" stripe>
            <el-table-column type="index" width="50" />
            <el-table-column prop="sku_name" :label="t('execDashboard.skuName')" min-width="120" show-overflow-tooltip />
            <el-table-column prop="quantity" :label="t('execDashboard.quantity')" width="100" align="right" />
            <el-table-column :label="t('execDashboard.amount')" width="130" align="right">
              <template #default="{ row }">¥{{ fmtNum(row.amount) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- Overdue Orders -->
      <div v-if="overdueOrders.length" class="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 shadow-sm">
        <h3 class="text-sm font-semibold text-red-700 dark:text-red-400 mb-3">
          <el-icon class="mr-1"><Warning /></el-icon>{{ t('execDashboard.overdueOrders') }}（{{ overdueOrders.length }}）
        </h3>
        <el-table :data="overdueOrders" size="small" stripe>
          <el-table-column prop="code" :label="t('execDashboard.orderNo')" width="180" />
          <el-table-column prop="customer_name" :label="t('execDashboard.customerName')" min-width="140" show-overflow-tooltip />
          <el-table-column prop="due_date" :label="t('execDashboard.dueDate')" width="120" />
          <el-table-column :label="t('execDashboard.daysOverdue')" width="110" align="right">
            <template #default="{ row }">
              <el-tag type="danger" size="small">{{ row.days_overdue }} {{ t('execDashboard.days') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('execDashboard.amount')" width="130" align="right">
            <template #default="{ row }">¥{{ fmtNum(row.amount) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Top, Bottom, Warning } from '@element-plus/icons-vue'
import AdminPage from '@/components/admin/AdminPage.vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import {
  execDashboardApi,
  type ExecSummaryOut,
  type TrendItem,
  type OrderStatusItem,
  type TopCustomerItem,
  type TopSkuItem,
  type OverdueOrderItem,
  type MetricOut,
} from '@/api/execDashboard'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const { t } = useI18n()

const period = ref('month')
const loading = ref(false)

const summary = ref<ExecSummaryOut | null>(null)
const trend = ref<TrendItem[]>([])
const orderStatus = ref<OrderStatusItem[]>([])
const topCustomers = ref<TopCustomerItem[]>([])
const topSkus = ref<TopSkuItem[]>([])
const overdueOrders = ref<OverdueOrderItem[]>([])

/* ---------- KPI card helpers ---------- */

type KpiCard = { key: string; label: string; display: string; change: number | null }

function fmtNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(2) + t('execDashboard.wan')
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPct(n: number): string {
  return n.toFixed(1) + '%'
}

const kpiCards = computed<KpiCard[]>(() => {
  if (!summary.value) return []
  const s = summary.value
  return [
    {
      key: 'revenue',
      label: t('execDashboard.revenue'),
      display: '¥' + fmtNum(s.revenue.value),
      change: s.revenue.change_pct,
    },
    {
      key: 'profit_margin',
      label: t('execDashboard.profitMargin'),
      display: fmtPct(s.profit_margin.value),
      change: s.profit_margin.change_pct,
    },
    {
      key: 'delivery_rate',
      label: t('execDashboard.deliveryRate'),
      display: fmtPct(s.delivery_rate.value),
      change: s.delivery_rate.change_pct,
    },
    {
      key: 'collection_rate',
      label: t('execDashboard.collectionRate'),
      display: fmtPct(s.collection_rate.value),
      change: s.collection_rate.change_pct,
    },
    {
      key: 'capacity',
      label: t('execDashboard.capacityUtilization'),
      display: fmtPct(s.capacity_utilization.value),
      change: s.capacity_utilization.change_pct,
    },
  ]
})

/* ---------- Chart options ---------- */

const STATUS_LABELS = computed<Record<string, string>>(() => ({
  draft: t('execDashboard.statusDraft'),
  confirmed: t('execDashboard.statusConfirmed'),
  producing: t('execDashboard.statusProducing'),
  pending_confirm: t('execDashboard.statusPendingConfirm'),
  completed: t('execDashboard.statusCompleted'),
  cancelled: t('execDashboard.statusCancelled'),
}))

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 60, right: 20, top: 20, bottom: 30 },
  xAxis: {
    type: 'category',
    data: trend.value.map((d) => d.date.slice(5)),
    axisLabel: { fontSize: 10 },
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      formatter: (v: number) => (v >= 10000 ? (v / 10000).toFixed(0) + 'w' : String(v)),
    },
  },
  series: [
    {
      type: 'line',
      data: trend.value.map((d) => d.amount),
      smooth: true,
      areaStyle: { opacity: 0.15 },
      lineStyle: { width: 2 },
      itemStyle: { color: '#4f46e5' },
    },
  ],
}))

const pieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, textStyle: { fontSize: 11 } },
  series: [
    {
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      label: { show: false },
      data: orderStatus.value.map((d) => ({
        name: STATUS_LABELS.value[d.status] || d.status,
        value: d.count,
      })),
    },
  ],
}))

/* ---------- Data loading ---------- */

async function loadAll() {
  loading.value = true
  try {
    const [s, tr, os, tc, ts, ov] = await Promise.all([
      execDashboardApi.summary(period.value),
      execDashboardApi.revenueTrend(30),
      execDashboardApi.orderStatus(),
      execDashboardApi.topCustomers(period.value, 5),
      execDashboardApi.topSkus(period.value, 5),
      execDashboardApi.overdueOrders(10),
    ])
    summary.value = s
    trend.value = tr ?? []
    orderStatus.value = os ?? []
    topCustomers.value = tc ?? []
    topSkus.value = ts ?? []
    overdueOrders.value = ov ?? []
  } catch (e) {
    console.error('exec dashboard load error', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>
