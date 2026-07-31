<template>
  <AdminPage :title="t('home.productionOverview')" :description="t('home.overviewDesc')">
    <template #actions>
      <el-tag v-if="summary?.today?.date" type="info" effect="plain" round>{{ summary.today.date }}</el-tag>
      <el-button v-if="canAi" type="primary" @click="aiOpen = true">{{ t('home.factoryAssistant') }}</el-button>
      <el-button type="primary" plain @click="reloadAll">{{ t('home.refreshData') }}</el-button>
    </template>

  <div class="space-y-5 pb-2">
    <PushStatsCard />

    <el-row v-if="canCrm && crmSummary" :gutter="16" class="mb-4">
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="cursor-pointer" @click="router.push('/crm/opportunities')">
          <div class="text-sm text-el-placeholder">{{ t('home.crmOpenOpps') }}</div>
          <div class="text-2xl font-semibold mt-1">{{ crmSummary.open_opportunities }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="cursor-pointer" @click="router.push('/crm/public-pool')">
          <div class="text-sm text-el-placeholder">{{ t('home.crmPublicPool') }}</div>
          <div class="text-2xl font-semibold mt-1">{{ crmSummary.public_pool }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="cursor-pointer" @click="router.push('/crm/opportunities')">
          <div class="text-sm text-el-placeholder">{{ t('home.crmDueFollowups') }}</div>
          <div class="text-2xl font-semibold mt-1 text-[#e6a23c]">{{ crmSummary.due_followups }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-loading="summaryLoading" class="admin-dashboard-hero" shadow="never">

      <el-alert
        v-if="!canDashboard"
        class="mt-4"
        type="warning"
        :closable="false"
        :title="t('home.noDashboardPermission')"
      />

      <template v-if="canDashboard">
        <el-row :gutter="16" class="mt-5">
          <el-col :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
            <div class="stat-card tone-green admin-interactive">
              <div class="stat-icon-wrap bg-[#e8f8f0] text-[#67c23a]">
                <el-icon :size="20"><CircleCheck /></el-icon>
              </div>
              <div class="stat-label">{{ t('home.todayGoodQty') }}</div>
              <div class="stat-value text-[#67c23a]">{{ summary?.today.good_qty ?? '-' }}</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
            <div class="stat-card tone-rose admin-interactive">
              <div class="stat-icon-wrap bg-[#fef0f0] text-[#f56c6c]">
                <el-icon :size="20"><WarningFilled /></el-icon>
              </div>
              <div class="stat-label">{{ t('home.todayBadQty') }}</div>
              <div class="stat-value text-[#f56c6c]">{{ summary?.today.bad_qty ?? '-' }}</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
            <div class="stat-card tone-blue admin-interactive">
              <div class="stat-icon-wrap bg-[#ecf5ff] text-[#409eff]">
                <el-icon :size="20"><PieChart /></el-icon>
              </div>
              <div class="stat-label">{{ t('home.todayYieldRate') }}</div>
              <div class="stat-value">{{ formatRate(summary?.today.yield_rate) }}</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
            <div class="stat-card tone-orange admin-interactive">
              <div class="stat-icon-wrap bg-[#fff4e6] text-[#e6a23c]">
                <el-icon :size="20"><Coin /></el-icon>
              </div>
              <div class="stat-label">{{ t('home.todaySalary') }}</div>
              <div class="stat-value text-[#e6a23c]">¥{{ formatMoney(summary?.today.salary_amount) }}</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
            <div class="stat-card tone-violet admin-interactive">
              <div class="stat-icon-wrap bg-[#f3e8ff] text-[#9b7ede]">
                <el-icon :size="20"><Timer /></el-icon>
              </div>
              <div class="stat-label">{{ t('home.pendingAuditReports') }}</div>
              <div class="stat-value text-[#9b7ede]">{{ summary?.reports.pending_audit ?? '-' }}</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
            <div class="stat-card tone-blue admin-interactive">
              <div class="stat-icon-wrap bg-[#ecf5ff] text-[#409eff]">
                <el-icon :size="20"><Document /></el-icon>
              </div>
              <div class="stat-label">{{ t('home.ordersTotalConfirmed') }}</div>
              <div class="stat-value text-el-primary">{{ summary?.orders.total ?? '-' }} / {{ summary?.orders.confirmed ?? '-' }}</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
            <div class="stat-card tone-mint admin-interactive">
              <div class="stat-icon-wrap bg-[#e6fffa] text-[#13ce66]">
                <el-icon :size="20"><List /></el-icon>
              </div>
              <div class="stat-label">{{ t('home.tasksPendingDone') }}</div>
              <div class="stat-value text-el-primary">{{ summary?.tasks.pending ?? '-' }} / {{ summary?.tasks.done ?? '-' }}</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6" class="mb-4">
            <div class="stat-card tone-violet admin-interactive">
              <div class="stat-icon-wrap bg-[#f3e8ff] text-[#9b7ede]">
                <el-icon :size="20"><DataBoard /></el-icon>
              </div>
              <div class="stat-label">{{ t('home.todayReportCount') }}</div>
              <div class="stat-value text-[#9b7ede]">{{ summary?.today.report_count ?? '-' }}</div>
            </div>
          </el-col>
        </el-row>
      </template>
    </el-card>

    <template v-if="canDashboard && charts">
      <el-row :gutter="16">
        <el-col :xs="24" :lg="14" class="mb-4">
          <el-card class="admin-chart-card" shadow="never">
            <template #header>
              <div class="flex items-center justify-between gap-3 flex-wrap">
                <span class="text-[14px] font-semibold text-el-primary">{{ t('home.recentDaysTrend', { days: chartDays }) }}</span>
                <el-radio-group v-model="chartDays" size="small" @change="loadCharts">
                  <el-radio-button :value="7">7{{ t('home.days') }}</el-radio-button>
                  <el-radio-button :value="14">14{{ t('home.days') }}</el-radio-button>
                  <el-radio-button :value="30">30{{ t('home.days') }}</el-radio-button>
                </el-radio-group>
              </div>
            </template>
            <div class="h-[300px] min-h-[260px]">
              <v-chart v-if="trendOption" :option="trendOption" autoresize />
            </div>
          </el-card>
        </el-col>

        <el-col :xs="24" :lg="10" class="mb-4">
          <el-card class="admin-chart-card" shadow="never">
            <template #header>
              <span class="text-[14px] font-semibold text-el-primary">{{ t('home.processRankTop10') }}</span>
            </template>
            <div class="h-[300px] min-h-[260px]">
              <v-chart v-if="rankOption" :option="rankOption" autoresize />
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-card v-if="canAi" shadow="never" class="mb-4" v-loading="briefLoading">
      <div class="flex items-center justify-between mb-3">
        <span class="text-[14px] font-semibold text-el-primary">{{ t('home.todayBrief') }}</span>
        <el-tag v-if="aiBrief?.mode" size="small" effect="plain">{{ aiBrief.mode === 'llm' ? t('home.llm') : t('home.rule') }}</el-tag>
      </div>
      <pre v-if="aiBrief?.content" class="text-sm text-zinc-700 whitespace-pre-wrap m-0 font-sans leading-relaxed">{{ aiBrief.content }}</pre>
      <el-empty v-else :description="t('home.noBrief')" :image-size="48" />
    </el-card>

    <el-card v-if="canAiAlert" shadow="never" class="mb-4">
      <div class="flex items-center justify-between mb-3">
        <span class="text-[14px] font-semibold text-el-primary">{{ t('home.aiDataAlert') }}</span>
        <div class="flex gap-2">
          <el-button v-if="canAi" size="small" link :loading="alertScanning" @click="runAlertScan">{{ t('home.scanNow') }}</el-button>
          <el-button v-if="canAiSettings" size="small" link @click="openAlertSettings">{{ t('home.thresholdConfig') }}</el-button>
          <el-button size="small" link @click="loadAlerts">{{ t('home.refreshData') }}</el-button>
        </div>
      </div>
      <el-empty v-if="!aiAlerts.length" :description="t('home.noAlerts')" :image-size="64" />
      <ul v-else class="space-y-2 text-sm">
        <li v-for="a in aiAlerts" :key="a.id" class="border rounded-lg px-3 py-2">
          <el-tag :type="a.level === 'danger' ? 'danger' : 'warning'" size="small" class="mr-2">{{ a.level }}</el-tag>
          <span class="font-medium">{{ a.title }}</span>
          <p v-if="a.summary" class="text-zinc-500 mt-1 text-xs">{{ a.summary }}</p>
        </li>
      </ul>
    </el-card>

    <el-drawer v-model="aiOpen" :title="t('home.factoryAssistantQA')" size="480px" destroy-on-close @open="onAiOpen">
      <div class="flex flex-col h-full">
        <div class="flex items-center gap-2 mb-2">
          <el-select v-if="aiModels.length" v-model="aiModelCode" size="small" class="flex-1" :placeholder="t('home.selectModel')">
            <el-option v-for="m in aiModels" :key="m.code" :label="m.display_name" :value="m.code" />
          </el-select>
          <el-button size="small" @click="aiShowHistory = !aiShowHistory">{{ t('home.history') }}</el-button>
          <el-button size="small" @click="newAiChat">{{ t('home.newChat') }}</el-button>
        </div>
        <div v-if="aiShowHistory && aiConversations.length" class="mb-2 max-h-32 overflow-y-auto border rounded p-2 text-xs">
          <div v-for="c in aiConversations" :key="c.id" class="flex justify-between items-center py-1 border-b last:border-0">
            <span class="truncate cursor-pointer flex-1" @click="aiConvId = c.id">{{ c.title || t('home.chatTitle', { id: c.id }) }}</span>
            <el-button link type="danger" size="small" @click="removeAiConv(c.id)">{{ t('home.delete') }}</el-button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto space-y-3 mb-3 min-h-[200px]">
          <div v-for="(m, i) in aiMessages" :key="i" :class="m.role === 'user' ? 'text-right' : ''">
            <div
              class="inline-block max-w-[90%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap"
              :class="m.role === 'user' ? 'bg-[#409eff] text-white' : 'bg-zinc-100 text-zinc-800'"
            >
              {{ m.content }}
            </div>
          </div>
        </div>
        <el-input v-model="aiInput" type="textarea" :rows="3" :placeholder="t('home.aiInputPlaceholder')" />
        <el-button class="mt-2" type="primary" :loading="aiSending" @click="sendAi">{{ t('home.send') }}</el-button>
      </div>
    </el-drawer>

    <el-dialog v-model="alertSettingsOpen" :title="t('home.aiAlertThreshold')" width="480px">
      <el-form label-width="160px">
        <el-form-item :label="t('home.pendingAuditThreshold')">
          <el-input-number v-model="alertSettings.pending_audit" :min="1" :max="10000" />
        </el-form-item>
        <el-form-item :label="t('home.yieldDropDelta')">
          <el-input-number v-model="alertSettings.yield_drop_delta" :min="0.01" :max="0.5" :step="0.01" />
        </el-form-item>
        <el-form-item :label="t('home.pendingTasksThreshold')">
          <el-input-number v-model="alertSettings.pending_tasks" :min="1" :max="10000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="alertSettingsOpen = false">{{ t('home.cancel') }}</el-button>
        <el-button type="primary" :loading="alertSettingsSaving" @click="saveAlertSettings">{{ t('home.save') }}</el-button>
      </template>
    </el-dialog>

    <el-card shadow="never">
      <div class="text-[14px] font-semibold mb-4" style="color: var(--admin-text-primary)">{{ t('home.quickEntry') }}</div>
      <div class="flex flex-wrap gap-2">
        <el-button v-if="can(['user.manage'])" class="admin-shortcut-btn" @click="go('/system/users')">{{ t('home.userManage') }}</el-button>
        <el-button v-if="can(['role.manage'])" class="admin-shortcut-btn" @click="go('/system/roles')">{{ t('home.roleManage') }}</el-button>
        <el-button v-if="can(['product.manage'])" class="admin-shortcut-btn" @click="go('/master/products')">{{ t('home.productManage') }}</el-button>
        <el-button v-if="can(['sku.manage'])" class="admin-shortcut-btn" @click="go('/master/skus')">{{ t('home.skuManage') }}</el-button>
        <el-button v-if="can(['process.manage'])" class="admin-shortcut-btn" @click="go('/master/processes')">{{ t('home.processManage') }}</el-button>
        <el-button v-if="can(['price.manage'])" class="admin-shortcut-btn" @click="go('/master/process-prices')">{{ t('home.priceManage') }}</el-button>
        <el-button v-if="can(['order.manage'])" class="admin-shortcut-btn" @click="go('/production/orders')">{{ t('home.orderManage') }}</el-button>
        <el-button v-if="can(['report.audit'])" class="admin-shortcut-btn" @click="go('/production/reports')">{{ t('home.reportAudit') }}</el-button>
        <el-button v-if="can(['salary.manage'])" class="admin-shortcut-btn" @click="go('/production/salary')">{{ t('home.salaryManage') }}</el-button>
      </div>
    </el-card>
  </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  CircleCheck,
  WarningFilled,
  PieChart,
  Coin,
  Timer,
  Document,
  List,
  DataBoard,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import AdminPage from '@/components/admin/AdminPage.vue'
import PushStatsCard from '@/components/admin/PushStatsCard.vue'
import { dashboardApi, type DashboardChartsOut, type DashboardSummaryOut } from '@/api/dashboard'
import { productionApi } from '@/api/production'
import { aiApi } from '@/api/ai'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()

const summaryLoading = ref(false)
const summary = ref<DashboardSummaryOut | null>(null)
const charts = ref<DashboardChartsOut | null>(null)
const chartDays = ref(14)

const canDashboard = computed(() => auth.hasAnyPermission(['dashboard.view']))
const canCrm = computed(() => auth.hasAnyPermission(['customer.manage', 'crm.sales']))
const crmSummary = ref<{ open_opportunities: number; public_pool: number; due_followups: number } | null>(null)
const canAi = computed(() => auth.hasAnyPermission(['ai.use']))
const canAiAlert = computed(() => auth.hasAnyPermission(['ai.alert.view']))
const canAiSettings = computed(() => auth.hasAnyPermission(['ai.use', 'setting.manage']))

const aiOpen = ref(false)
const aiInput = ref('')
const aiSending = ref(false)
const aiConvId = ref<number | undefined>()
const aiMessages = ref<{ role: string; content: string }[]>([])
const aiModels = ref<Array<{ code: string; display_name: string; is_default: boolean }>>([])
const aiModelCode = ref('')
const aiShowHistory = ref(false)
const aiConversations = ref<Array<{ id: number; title: string | null }>>([])
const aiAlerts = ref<Array<{ id: number; level: string; title: string; summary?: string }>>([])
const alertSettingsOpen = ref(false)
const alertSettingsSaving = ref(false)
const alertSettings = ref({ pending_audit: 50, yield_drop_delta: 0.05, pending_tasks: 30, unassigned_sample_min: 3 })
const alertScanning = ref(false)
const briefLoading = ref(false)
const aiBrief = ref<{ mode: string; content: string } | null>(null)

async function loadAiModels() {
  if (!canAi.value) return
  try {
    const res = await aiApi.listModels()
    aiModels.value = res.items || []
    const def = aiModels.value.find((m) => m.is_default)
    aiModelCode.value = def?.code || aiModels.value[0]?.code || ''
  } catch {
    aiModels.value = []
  }
}

async function loadAiConversations() {
  if (!canAi.value) return
  try {
    const res = await aiApi.listConversations('boss_qa')
    aiConversations.value = res.items || []
  } catch {
    aiConversations.value = []
  }
}

function onAiOpen() {
  loadAiModels()
  loadAiConversations()
}

function newAiChat() {
  aiConvId.value = undefined
  aiMessages.value = []
}

async function removeAiConv(id: number) {
  try {
    await aiApi.deleteConversation(id)
    if (aiConvId.value === id) newAiChat()
    await loadAiConversations()
    ElMessage.success(t('home.deleted'))
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : t('home.deleteFailed'))
  }
}

async function runAlertScan() {
  alertScanning.value = true
  try {
    const res = await aiApi.runAlerts()
    ElMessage.success(t('home.scanComplete', { events: res.events ?? 0, notified: res.notified ?? 0 }))
    await loadAlerts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : t('home.scanFailed'))
  } finally {
    alertScanning.value = false
  }
}

async function loadAlerts() {
  if (!canAiAlert.value) return
  try {
    const res = await aiApi.listAlerts()
    aiAlerts.value = res.items || []
  } catch {
    aiAlerts.value = []
  }
}

async function loadBrief() {
  if (!canAi.value) return
  briefLoading.value = true
  try {
    aiBrief.value = await aiApi.getAiBrief()
  } catch {
    aiBrief.value = null
  } finally {
    briefLoading.value = false
  }
}

function openAiFromQuery() {
  if (route.query.ai === '1' && canAi.value) {
    aiOpen.value = true
    onAiOpen()
    const q = { ...route.query }
    delete q.ai
    router.replace({ path: route.path, query: q })
  }
}

async function openAlertSettings() {
  alertSettingsOpen.value = true
  try {
    alertSettings.value = await aiApi.getAlertSettings()
  } catch {
    /* 默认 */
  }
}

async function saveAlertSettings() {
  alertSettingsSaving.value = true
  try {
    alertSettings.value = await aiApi.saveAlertSettings(alertSettings.value)
    ElMessage.success(t('home.saved'))
    alertSettingsOpen.value = false
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : t('home.saveFailed'))
  } finally {
    alertSettingsSaving.value = false
  }
}

async function sendAi() {
  const msg = aiInput.value.trim()
  if (!msg) return
  aiMessages.value.push({ role: 'user', content: msg })
  aiInput.value = ''
  aiSending.value = true
  const assistantIdx = aiMessages.value.length
  aiMessages.value.push({ role: 'assistant', content: '' })
  try {
    const res = await aiApi.chatStream(
      { message: msg, conversation_id: aiConvId.value, model_code: aiModelCode.value || undefined },
      (delta) => {
      aiMessages.value[assistantIdx].content += delta
    })
    aiConvId.value = res.conversation_id
    if (res.reply && !aiMessages.value[assistantIdx].content) {
      aiMessages.value[assistantIdx].content = res.reply
    }
    await loadAiConversations()
  } catch (e: unknown) {
    aiMessages.value.pop()
    ElMessage.error(e instanceof Error ? e.message : t('home.aiUnavailable'))
  } finally {
    aiSending.value = false
  }
}

function go(path: string) {
  router.push(path)
}
function can(perms: string[]) {
  return auth.hasAnyPermission(perms)
}

function formatRate(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return `${(v * 100).toFixed(2)}%`
}
function formatMoney(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return '0.00'
  return v.toFixed(2)
}

const trendOption = computed(() => {
  const data = charts.value?.daily_trend
  if (!data || data.length === 0) return null
  const dates = data.map((d) => d.date.slice(5))
  const goodQty = data.map((d) => d.good_qty)
  const badQty = data.map((d) => d.bad_qty)
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: [t('home.goodQty'), t('home.badQty')], bottom: 0 },
    grid: { left: 40, right: 16, top: 10, bottom: 40 },
    xAxis: { type: 'category' as const, data: dates, axisLabel: { fontSize: 11, color: '#909399' } },
    yAxis: {
      type: 'value' as const,
      minInterval: 1,
      splitLine: { lineStyle: { color: '#eef0f4' } },
    },
    series: [
      {
        name: t('home.goodQty'),
        type: 'line' as const,
        data: goodQty,
        smooth: true,
        lineStyle: { color: '#93c5fd', width: 2 },
        itemStyle: { color: '#409eff' },
        areaStyle: { color: 'rgba(147, 197, 253, 0.25)' },
      },
      {
        name: t('home.badQty'),
        type: 'line' as const,
        data: badQty,
        smooth: true,
        lineStyle: { color: '#fdba74', width: 2 },
        itemStyle: { color: '#fdba74' },
        areaStyle: { color: 'rgba(253, 186, 116, 0.2)' },
      },
    ],
  }
})

const rankOption = computed(() => {
  const data = charts.value?.process_rank
  if (!data || data.length === 0) return null
  const names = data.map((r) => r.process_name || `${t('home.processPrefix')}${r.process_id}`).reverse()
  const goodQty = data.map((r) => r.good_qty).reverse()
  const badQty = data.map((r) => r.bad_qty).reverse()
  return {
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
    legend: { data: [t('home.goodQty'), t('home.badQty')], bottom: 0 },
    grid: { left: 80, right: 20, top: 10, bottom: 40 },
    xAxis: { type: 'value' as const, minInterval: 1, splitLine: { lineStyle: { color: '#eef0f4' } } },
    yAxis: { type: 'category' as const, data: names, axisLabel: { fontSize: 11, color: '#606266' } },
    series: [
      {
        name: t('home.goodQty'),
        type: 'bar' as const,
        data: goodQty,
        barWidth: 10,
        itemStyle: { color: '#93c5fd', borderRadius: [0, 4, 4, 0] },
      },
      {
        name: t('home.badQty'),
        type: 'bar' as const,
        data: badQty,
        barWidth: 10,
        itemStyle: { color: '#86efac', borderRadius: [0, 4, 4, 0] },
      },
    ],
  }
})

async function loadSummary() {
  if (!canDashboard.value) return
  summaryLoading.value = true
  try {
    summary.value = await dashboardApi.summary()
  } finally {
    summaryLoading.value = false
  }
}

async function loadCharts() {
  if (!canDashboard.value) return
  try {
    charts.value = await dashboardApi.charts(chartDays.value)
  } catch {
    /* ignore */
  }
}

async function loadCrmSummary() {
  if (!canCrm.value) return
  try {
    crmSummary.value = await productionApi.getCrmDashboardSummary()
  } catch {
    crmSummary.value = null
  }
}

async function reloadAll() {
  await Promise.all([loadSummary(), loadCharts(), loadCrmSummary()])
}

watch(
  () => route.query.ai,
  () => openAiFromQuery(),
)

onMounted(() => {
  loadSummary()
  loadCharts()
  loadCrmSummary()
  loadAlerts()
  loadBrief()
  openAiFromQuery()
})
</script>
