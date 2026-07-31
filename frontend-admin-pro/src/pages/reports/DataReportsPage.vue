<template>
  <AdminPage :title="t('reports.title')">
    <el-card v-loading="loading">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="text-lg font-semibold">{{ t('reports.title') }}</div>
        <div class="flex items-center gap-2 flex-wrap">
          <el-date-picker
            v-model="range"
            type="daterange"
            value-format="YYYY-MM-DD"
            :range-separator="t('reports.rangeTo')"
            :start-placeholder="t('reports.startDate')"
            :end-placeholder="t('reports.endDate')"
            @change="reload"
          />
          <el-button size="small" @click="reload">{{ t('common.refresh') }}</el-button>
          <el-button size="small" type="primary" :loading="exporting" @click="exportExcel">{{ t('reports.exportExcel') }}</el-button>
        </div>
      </div>

      <el-tabs class="mt-4" v-model="activeTab">
        <el-tab-pane :label="t('reports.tabProduction')" name="production">
          <el-row :gutter="16">
            <el-col :xs="24" :lg="12">
              <div class="flex items-center justify-center" style="height:320px;">
                <v-chart v-if="productionPieOption" :option="productionPieOption" autoresize style="width:100%;height:100%;" />
                <el-empty v-else :description="t('reports.noData')" />
              </div>
            </el-col>
            <el-col :xs="24" :lg="12">
              <el-descriptions v-if="production" :column="2" border class="mt-4">
                <el-descriptions-item :label="t('reports.goodQty')">
                  <span class="text-green-600 font-semibold">{{ production.good_qty }}</span>
                </el-descriptions-item>
                <el-descriptions-item :label="t('reports.badQty')">
                  <span class="text-red-500 font-semibold">{{ production.bad_qty }}</span>
                </el-descriptions-item>
                <el-descriptions-item :label="t('reports.totalQty')">{{ production.total_qty }}</el-descriptions-item>
                <el-descriptions-item :label="t('reports.yieldRate')">
                  <span class="text-blue-600 font-semibold">{{ formatRate(production.yield_rate) }}</span>
                </el-descriptions-item>
                <el-descriptions-item :label="t('reports.approvedReports')">{{ production.report_count }}</el-descriptions-item>
                <el-descriptions-item :label="t('reports.statRange')">{{ rangeLabel }}</el-descriptions-item>
              </el-descriptions>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane :label="t('reports.tabYield')" name="yield">
          <el-row :gutter="16">
            <el-col :xs="24" :lg="12">
              <div class="flex items-center justify-center" style="height:320px;">
                <v-chart v-if="yieldGaugeOption" :option="yieldGaugeOption" autoresize style="width:100%;height:100%;" />
                <el-empty v-else :description="t('reports.noData')" />
              </div>
            </el-col>
            <el-col :xs="24" :lg="12">
              <el-descriptions v-if="yieldSummary" :column="2" border class="mt-4">
                <el-descriptions-item :label="t('reports.yieldRate')">
                  <span class="text-blue-600 font-semibold">{{ formatRate(yieldSummary.yield_rate) }}</span>
                </el-descriptions-item>
                <el-descriptions-item :label="t('reports.goodQty')">{{ yieldSummary.good_qty }}</el-descriptions-item>
                <el-descriptions-item :label="t('reports.badQty')">{{ yieldSummary.bad_qty }}</el-descriptions-item>
                <el-descriptions-item :label="t('reports.totalQty')">{{ yieldSummary.total_qty }}</el-descriptions-item>
                <el-descriptions-item :label="t('reports.statRange')">{{ rangeLabel }}</el-descriptions-item>
              </el-descriptions>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane :label="t('reports.tabProcessRank')" name="process-rank">
          <div class="flex items-center justify-center" style="height:400px;">
            <v-chart v-if="rankChartOption" :option="rankChartOption" autoresize style="width:100%;height:100%;" />
            <el-empty v-else :description="t('reports.noData')" />
          </div>
          <template v-if="processRank.length">
            <el-table class="hidden lg:block mt-4 w-full" :data="processRank" border style="width:100%">
              <el-table-column type="index" label="#" width="60" />
              <el-table-column prop="process_name" :label="t('reports.process')" min-width="180" />
              <el-table-column prop="good_qty" :label="t('reports.goodQty')" width="110" />
              <el-table-column prop="bad_qty" :label="t('reports.badQty')" width="110" />
              <el-table-column prop="total_qty" :label="t('reports.totalQty')" width="110" />
              <el-table-column :label="t('reports.yieldRate')" width="110">
                <template #default="{ row }">{{ formatRate(row.yield_rate) }}</template>
              </el-table-column>
            </el-table>
            <div class="lg:hidden space-y-3 mt-4">
              <div v-for="(row, idx) in processRank" :key="row.process_id ?? idx" class="admin-mobile-row">
                <div class="font-semibold text-sm text-el-primary">{{ row.process_name || `${t('reports.processPrefix')}${row.process_id}` }}</div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>{{ t('reports.goodShort') }}</dt>
                  <dd>{{ row.good_qty }}</dd>
                  <dt>{{ t('reports.badShort') }}</dt>
                  <dd>{{ row.bad_qty }}</dd>
                  <dt>{{ t('reports.totalQty') }}</dt>
                  <dd>{{ row.total_qty }}</dd>
                  <dt>{{ t('reports.yieldRate') }}</dt>
                  <dd>{{ formatRate(row.yield_rate) }}</dd>
                </dl>
              </div>
            </div>
          </template>
        </el-tab-pane>

        <el-tab-pane :label="t('reports.tabDefectPareto')" name="defect-pareto">
          <div class="flex items-center justify-center" style="height:360px;">
            <v-chart v-if="defectParetoOption" :option="defectParetoOption" autoresize style="width:100%;height:100%;"
              ref="paretoChartRef" />
            <el-empty v-else :description="t('reports.noDefectData')" />
          </div>
          <template v-if="defectPareto.length">
            <div class="flex justify-end mb-2">
              <el-button size="small" @click="exportParetoChart">{{ t('reports.exportChart') }}</el-button>
            </div>
            <el-table class="hidden lg:block mt-2 w-full" :data="defectPareto" border>
              <el-table-column type="index" label="#" width="60" />
              <el-table-column prop="defect_code" :label="t('reports.defectCode')" width="140" />
              <el-table-column prop="defect_name" :label="t('reports.defectName')" min-width="180" />
              <el-table-column :label="t('reports.severity')" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.severity === 'critical' ? 'danger' : row.severity === 'major' ? 'warning' : 'info'" size="small">
                    {{ severityLabel(row.severity) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="count" :label="t('reports.count')" width="80" />
              <el-table-column prop="pct" :label="t('reports.pct')" width="80">
                <template #default="{ row }">{{ row.pct }}%</template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane>

        <el-tab-pane :label="t('reports.tabDailyTrend')" name="daily-trend">
          <div class="flex items-center justify-center" style="height:360px;">
            <v-chart v-if="trendChartOption" :option="trendChartOption" autoresize style="width:100%;height:100%;" />
            <el-empty v-else :description="t('reports.noData')" />
          </div>
          <template v-if="dailyTrend.length">
            <el-table class="hidden lg:block mt-4 w-full" :data="dailyTrend" border style="width:100%">
              <el-table-column prop="date" :label="t('reports.date')" width="130" />
              <el-table-column prop="good_qty" :label="t('reports.goodQty')" width="110" />
              <el-table-column prop="bad_qty" :label="t('reports.badQty')" width="110" />
              <el-table-column prop="total_qty" :label="t('reports.totalQty')" width="110" />
              <el-table-column :label="t('reports.yieldRate')" width="110">
                <template #default="{ row }">{{ formatRate(row.yield_rate) }}</template>
              </el-table-column>
            </el-table>
            <div class="lg:hidden space-y-3 mt-4">
              <div v-for="row in dailyTrend" :key="row.date" class="admin-mobile-row">
                <div class="font-semibold text-sm">{{ row.date }}</div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>{{ t('reports.goodShort') }}</dt>
                  <dd>{{ row.good_qty }}</dd>
                  <dt>{{ t('reports.badShort') }}</dt>
                  <dd>{{ row.bad_qty }}</dd>
                  <dt>{{ t('reports.totalQty') }}</dt>
                  <dd>{{ row.total_qty }}</dd>
                  <dt>{{ t('reports.yieldRate') }}</dt>
                  <dd>{{ formatRate(row.yield_rate) }}</dd>
                </dl>
              </div>
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useExport } from '@/composables/useExport'
import {
  reportsApi,
  type DailyTrendItemOut,
  type DefectParetoItemOut,
  type ProcessRankItemOut,
  type ProductionSummaryOut,
  type YieldSummaryOut,
} from '@/api/reports'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, GaugeChart, BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'

use([
  CanvasRenderer,
  PieChart,
  GaugeChart,
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
])

const { t } = useI18n()

const activeTab = ref<'production' | 'yield' | 'process-rank' | 'defect-pareto' | 'daily-trend'>('production')
const loading = ref(false)
const range = ref<[string, string] | null>(null)

const { exporting, doExport } = useExport()

const production = ref<ProductionSummaryOut | null>(null)
const yieldSummary = ref<YieldSummaryOut | null>(null)
const processRank = ref<ProcessRankItemOut[]>([])
const dailyTrend = ref<DailyTrendItemOut[]>([])
const defectPareto = ref<DefectParetoItemOut[]>([])
const paretoChartRef = ref<any>(null)

const rangeLabel = computed(() => {
  if (!range.value) return t('reports.rangeAll')
  return `${range.value[0]} ${t('reports.rangeTo')} ${range.value[1]}`
})

function formatRate(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return `${(v * 100).toFixed(2)}%`
}

function severityLabel(severity: string) {
  const map: Record<string, string> = {
    critical: t('reports.severityCritical'),
    major: t('reports.severityMajor'),
    minor: t('reports.severityMinor'),
  }
  return map[severity] || severity
}

const productionPieOption = computed(() => {
  const p = production.value
  if (!p || (p.good_qty === 0 && p.bad_qty === 0)) return null
  const goodLabel = t('reports.goodQty')
  const badLabel = t('reports.badQty')
  return {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie' as const,
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        label: { show: true, formatter: '{b}\n{d}%' },
        emphasis: { label: { show: true, fontSize: 14 } },
        data: [
          { value: p.good_qty, name: goodLabel, itemStyle: { color: '#409eff' } },
          { value: p.bad_qty, name: badLabel, itemStyle: { color: '#f56c6c' } },
        ],
      },
    ],
  }
})

const yieldGaugeOption = computed(() => {
  const y = yieldSummary.value
  if (!y || y.yield_rate === null || y.total_qty === 0) return null
  const rate = Math.round(y.yield_rate * 10000) / 100
  const yieldLabel = t('reports.yieldRate')
  return {
    series: [
      {
        type: 'gauge' as const,
        center: ['50%', '55%'],
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        splitNumber: 5,
        progress: { show: true, width: 12 },
        axisLine: { lineStyle: { width: 12, color: [[0.8, '#f56c6c'], [0.95, '#e6a23c'], [1, '#67c23a']] } },
        axisTick: { show: false },
        splitLine: { length: 8 },
        axisLabel: { distance: 20, fontSize: 10 },
        pointer: { width: 4 },
        detail: {
          fontSize: 20,
          formatter: `{value}%\n${yieldLabel}`,
          offsetCenter: [0, '40%'],
        },
        data: [{ value: rate }],
      },
    ],
  }
})

const rankChartOption = computed(() => {
  const data = processRank.value
  if (!data || data.length === 0) return null
  const prefix = t('reports.processPrefix')
  const goodLabel = t('reports.goodQty')
  const badLabel = t('reports.badQty')
  const names = data.map((r) => r.process_name || `${prefix}${r.process_id}`).reverse()
  const good = data.map((r) => r.good_qty).reverse()
  const bad = data.map((r) => r.bad_qty).reverse()
  return {
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
    legend: { data: [goodLabel, badLabel], bottom: 0 },
    grid: { left: 80, right: 20, top: 10, bottom: 40 },
    xAxis: { type: 'value' as const, minInterval: 1 },
    yAxis: { type: 'category' as const, data: names, axisLabel: { fontSize: 11 } },
    series: [
      {
        name: goodLabel,
        type: 'bar' as const,
        data: good,
        barWidth: 10,
        itemStyle: { color: '#409eff', borderRadius: [0, 4, 4, 0] },
      },
      {
        name: badLabel,
        type: 'bar' as const,
        data: bad,
        barWidth: 10,
        itemStyle: { color: '#f56c6c', borderRadius: [0, 4, 4, 0] },
      },
    ],
  }
})

const trendChartOption = computed(() => {
  const data = dailyTrend.value
  if (!data || data.length === 0) return null
  const goodLabel = t('reports.goodQty')
  const badLabel = t('reports.badQty')
  const dates = data.map((d) => d.date.slice(5))
  const good = data.map((d) => d.good_qty)
  const bad = data.map((d) => d.bad_qty)
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: [goodLabel, badLabel], bottom: 0 },
    grid: { left: 40, right: 16, top: 10, bottom: 40 },
    xAxis: { type: 'category' as const, data: dates, axisLabel: { fontSize: 11, rotate: 30 } },
    yAxis: { type: 'value' as const, minInterval: 1 },
    series: [
      {
        name: goodLabel,
        type: 'line' as const,
        data: good,
        smooth: true,
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
        areaStyle: { color: 'rgba(64,158,255,0.08)' },
      },
      {
        name: badLabel,
        type: 'line' as const,
        data: bad,
        smooth: true,
        lineStyle: { color: '#f56c6c', width: 2 },
        itemStyle: { color: '#f56c6c' },
        areaStyle: { color: 'rgba(245,108,108,0.08)' },
      },
    ],
  }
})

const defectParetoOption = computed(() => {
  const data = defectPareto.value
  if (!data || data.length === 0) return null
  const countLabel = t('reports.count')
  const cumLabel = t('reports.cumulativePct')
  const names = data.map((d) => `${d.defect_code} ${d.defect_name}`)
  const counts = data.map((d) => d.count)
  const cumPct = data.map((d) => d.cumulative_pct)
  return {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: any) => {
        const bar = params.find((p: any) => p.seriesName === countLabel)
        const line = params.find((p: any) => p.seriesName === cumLabel)
        return `${bar?.name}<br/>${countLabel}: ${bar?.value}<br/>${cumLabel}: ${line?.value}%`
      },
    },
    legend: { data: [countLabel, cumLabel], bottom: 0 },
    grid: { left: 50, right: 50, top: 10, bottom: 40 },
    xAxis: { type: 'category' as const, data: names, axisLabel: { fontSize: 10, rotate: 30 } },
    yAxis: [
      { type: 'value' as const, name: countLabel, minInterval: 1 },
      { type: 'value' as const, name: cumLabel, max: 100, axisLabel: { formatter: '{value}%' } },
    ],
    series: [
      {
        name: countLabel,
        type: 'bar' as const,
        data: counts,
        barWidth: 16,
        itemStyle: {
          color: (p: any) => {
            const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899']
            return colors[p.dataIndex % colors.length]
          },
          borderRadius: [4, 4, 0, 0],
        },
      },
      {
        name: cumLabel,
        type: 'line' as const,
        yAxisIndex: 1,
        data: cumPct,
        smooth: true,
        lineStyle: { color: '#ef4444', width: 2 },
        itemStyle: { color: '#ef4444' },
        symbol: 'circle',
        symbolSize: 6,
      },
    ],
  }
})

async function exportExcel() {
  const params = range.value ? { date_from: range.value[0], date_to: range.value[1] } : {}
  await doExport(
    () => reportsApi.exportProductionExcel(params),
    `production_${range.value?.[0] || 'all'}_${range.value?.[1] || 'all'}.xlsx`,
  )
}

function exportParetoChart() {
  const chart = paretoChartRef.value
  if (!chart) return
  try {
    const url = chart.getDataURL?.() || (chart as any)?.root?.renderToDataURL?.()
    if (url) {
      const a = document.createElement('a')
      a.href = url
      a.download = `defect-pareto_${range.value?.[0] || ''}_${range.value?.[1] || ''}.png`
      a.click()
    }
  } catch {
    // ignore
  }
}

function toISODate(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function initRange(days: number) {
  const to = new Date()
  const from = new Date()
  from.setDate(to.getDate() - (days - 1))
  range.value = [toISODate(from), toISODate(to)]
}

async function reload() {
  loading.value = true
  try {
    const params = range.value ? { date_from: range.value[0], date_to: range.value[1] } : {}
    const [p, y, pr, dt, dp] = await Promise.all([
      reportsApi.production(params),
      reportsApi.yield(params),
      reportsApi.processRank({ ...params, limit: 20 }),
      reportsApi.dailyTrend(params),
      reportsApi.defectPareto(params).catch(() => ({ items: [], total: 0 })),
    ])
    production.value = p
    yieldSummary.value = y
    processRank.value = pr.items
    dailyTrend.value = dt.items
    defectPareto.value = dp.items
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  initRange(30)
  reload()
})
</script>
