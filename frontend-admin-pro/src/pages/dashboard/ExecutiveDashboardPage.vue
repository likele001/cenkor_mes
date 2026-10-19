<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
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
      <el-alert v-if="loadError" type="error" :closable="false" show-icon :title="loadError" />
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
            <el-icon v-if="card.change !== 0"><component :is="card.change >= 0 ? TopIcon : BottomIcon" /></el-icon>
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

      <!-- AI Extension Cards -->
      <div v-if="hasAiExtensions" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          v-if="aiAnomalyLoaded"
          class="rounded-xl border border-blue-200 dark:border-blue-800 bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 p-4 shadow-sm cursor-pointer hover:shadow-md transition-shadow"
          @click="goToExtension(aiAnomalyRoute)"
        >
          <div class="flex items-center gap-2 mb-2">
            <el-icon :size="20" class="text-blue-600 dark:text-blue-400"><Warning /></el-icon>
            <h3 class="text-sm font-semibold text-blue-900 dark:text-blue-200">AI 异常预警</h3>
          </div>
          <p class="text-xs text-blue-700 dark:text-blue-300">六维规则体检 · 根因深挖 · 处置建议</p>
        </div>
        <div
          v-if="productionDiagnosisLoaded"
          class="rounded-xl border border-orange-200 dark:border-orange-800 bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-800/20 p-4 shadow-sm cursor-pointer hover:shadow-md transition-shadow"
          @click="goToExtension(productionDiagnosisRoute)"
        >
          <div class="flex items-center gap-2 mb-2">
            <el-icon :size="20" class="text-orange-600 dark:text-orange-400"><Warning /></el-icon>
            <h3 class="text-sm font-semibold text-orange-900 dark:text-orange-200">生产异常排查</h3>
          </div>
          <p class="text-xs text-orange-700 dark:text-orange-300">报工/进度/交期/齐套/设备/质量诊断</p>
        </div>
        <div
          v-if="aiInsightLoaded"
          class="rounded-xl border border-purple-200 dark:border-purple-800 bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 p-4 shadow-sm cursor-pointer hover:shadow-md transition-shadow"
          @click="goToExtension(aiInsightRoute)"
        >
          <div class="flex items-center gap-2 mb-2">
            <el-icon :size="20" class="text-purple-600 dark:text-purple-400"><TrendCharts /></el-icon>
            <h3 class="text-sm font-semibold text-purple-900 dark:text-purple-200">AI 深度洞察</h3>
          </div>
          <p class="text-xs text-purple-700 dark:text-purple-300">质量/设备/交期/成本趋势与结构问题</p>
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
import { useRouter } from 'vue-router'
import { Top as TopIcon, Bottom as BottomIcon, Warning, TrendCharts } from '@element-plus/icons-vue'
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
import { isExtensionLoaded, getExtensionRoute } from '@/utils/extensionLoader'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const { t } = useI18n()
const router = useRouter()

const period = ref('month')
const loading = ref(false)

const loadError = ref('')
const summary = ref<ExecSummaryOut | null>(null)
const trend = ref<TrendItem[]>([])
const orderStatus = ref<OrderStatusItem[]>([])
const topCustomers = ref<TopCustomerItem[]>([])
const topSkus = ref<TopSkuItem[]>([])
const overdueOrders = ref<OverdueOrderItem[]>([])

// AI 扩展卡片（扩展已加载时显示）
const aiAnomalyLoaded = computed(() => isExtensionLoaded('ai_anomaly'))
const aiAnomalyRoute = computed(() => getExtensionRoute('ai_anomaly'))
const productionDiagnosisLoaded = computed(() => isExtensionLoaded('production_diagnosis'))
const productionDiagnosisRoute = computed(() => getExtensionRoute('production_diagnosis'))
const aiInsightLoaded = computed(() => isExtensionLoaded('ai_insight'))
const aiInsightRoute = computed(() => getExtensionRoute('ai_insight'))
const hasAiExtensions = computed(() => aiAnomalyLoaded.value || productionDiagnosisLoaded.value || aiInsightLoaded.value)

function goToExtension(route: string | null) {
  if (route) router.push(route)
}

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
  loadError.value = ''
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
    loadError.value = t('execDashboard.loadFailed')
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>
