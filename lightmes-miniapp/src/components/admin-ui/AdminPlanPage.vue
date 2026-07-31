<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索计划号" @confirm="reload" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新建</button>
    </view>

    <MListLayout :items="items" :loading="loading" empty-text="暂无生产计划" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ planTitle(item) }}</text>
          <view class="adm-list-tags">
            <text v-if="forecastCache[item.id]" :class="['adm-list-badge', riskTone(forecastCache[item.id]?.due_risk)]">
              {{ dueRiskLabel(forecastCache[item.id]?.due_risk) }}
            </text>
            <text class="adm-list-badge tone-violet">{{ statusLabel(String(item.status)) }}</text>
          </view>
        </view>
        <AdminKvGrid :rows="planKvRows(item)" />
        <view class="adm-progress-wrap">
          <view class="adm-progress-meta">
            <text>完成率</text>
            <text>{{ planProgress(item).pct }}%</text>
          </view>
          <view class="adm-progress-bar">
            <view class="adm-progress-fill" :style="{ width: planProgress(item).width }" />
          </view>
        </view>
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="openEdit(item)">详情</button>
          <button v-if="item.can_release" class="adm-card-btn ghost" @tap="checkReadiness(item)">齐套</button>
          <button v-if="item.can_release" class="adm-card-btn teal" @tap="releasePlan(item)">下发</button>
        </view>
      </template>
    </MListLayout>

    <!-- 新建/编辑 -->
    <view v-if="formVisible" class="mask" @tap="formVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">{{ formMode === 'create' ? '新建生产计划' : '编辑生产计划' }}</text>
          <text v-if="planForecast?.due_risk" :class="['risk-tag', planForecast.due_risk]">
            {{ dueRiskLabel(planForecast.due_risk) }}
          </text>
        </view>
        <scroll-view scroll-y class="body">
          <view v-if="formMode === 'create'" class="field">
            <text class="label">关联订单*</text>
            <picker :range="orderLabels" @change="onOrderPick">
              <view class="input picker">{{ orderLabels[orderIndex] || '请选择已审核订单' }}</view>
            </picker>
          </view>
          <view v-else class="field">
            <text class="label">关联订单</text>
            <view class="input disabled">{{ selectedOrderText }}</view>
          </view>
          <view class="field"><text class="label">计划编号</text><input v-model="form.code" class="input" placeholder="留空自动生成" /></view>
          <view class="field">
            <text class="label">状态</text>
            <picker :range="statusOptions" range-key="label" :disabled="form.status === 'in_progress'" @change="onStatusPick">
              <view class="input picker">{{ currentStatusLabel }}</view>
            </picker>
          </view>
          <view class="field"><text class="label">开始日期</text><input v-model="form.start_date" class="input" placeholder="YYYY-MM-DD" /></view>
          <view class="field"><text class="label">结束日期</text><input v-model="form.end_date" class="input" placeholder="YYYY-MM-DD" /></view>
          <view class="field"><text class="label">工期(天)</text><input v-model="form.work_days" class="input" type="number" placeholder="可选" /></view>
          <view class="field"><text class="label">备注</text><textarea v-model="form.remark" class="input area" /></view>
        </scroll-view>
        <view class="foot">
          <button v-if="formMode === 'edit'" class="btn ghost" :loading="aiRiskLoading" @tap="aiPlanAnalyze">AI交期分析</button>
          <button v-if="formMode === 'edit'" class="btn ghost" :loading="aiSuggestLoading" @tap="aiScheduleSuggest">AI排产建议</button>
          <button v-if="formMode === 'edit' && editingId" class="btn ghost" @tap="openFactoryAssistant">问工厂助手</button>
          <button v-if="formMode === 'edit'" class="btn ghost" :loading="autoscheduling" @tap="autoSchedule">按交期回推</button>
          <button v-if="form.order_id" class="btn ghost" @tap="previewReadiness">投产预览</button>
          <button class="btn primary" :loading="saving" @tap="submit">保存</button>
        </view>
      </view>
    </view>

    <!-- 齐套/就绪检查 -->
    <view v-if="readinessVisible" class="mask" @tap="readinessVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">投产就绪检查</text>
          <text :class="['tag', readinessData?.ready ? 'ok' : 'bad']">{{ readinessData?.ready ? '可投产' : '未就绪' }}</text>
        </view>
        <scroll-view scroll-y class="body">
          <view v-if="readinessData?.blockers?.length" class="blockers">
            <text class="section-title">阻塞项</text>
            <text v-for="(b, i) in readinessData.blockers" :key="i" class="blocker">· {{ b }}</text>
          </view>
          <view v-if="readinessData?.kitting?.items?.length" class="section-title">缺料明细</view>
          <view
            v-for="(k, idx) in readinessData?.kitting?.items?.filter((x) => x.shortage_qty > 0) || []"
            :key="idx"
            class="line-info"
          >
            <text class="mat">{{ k.material_name }} ({{ k.material_code }})</text>
            <text class="nums">需求 {{ k.demand_qty }} · 库存 {{ k.stock_qty }} · 缺 {{ k.shortage_qty }}</text>
          </view>
          <view v-if="readinessData?.process?.missing_routes?.length" class="section-title">缺工艺路线</view>
          <text v-for="(r, i) in readinessData?.process?.missing_routes || []" :key="'r' + i" class="blocker">
            · {{ r.product_name }} ({{ r.product_code }})
          </text>
          <view v-if="readinessData?.process?.missing_prices?.length" class="section-title">缺工价</view>
          <text v-for="(p, i) in readinessData?.process?.missing_prices || []" :key="'p' + i" class="blocker">
            · {{ p.sku_name }} / {{ p.process_name }}
          </text>
        </scroll-view>
        <view class="foot">
          <button v-if="canReleaseCurrent" class="btn primary" :loading="releasing" @tap="releaseCurrent">确认下发</button>
          <button class="btn ghost" @tap="readinessVisible = false">关闭</button>
        </view>
      </view>
    </view>

    <view v-if="aiRiskVisible" class="mask" @tap="aiRiskVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">AI 交期风险分析</text></view>
        <scroll-view scroll-y class="body">
          <text v-if="aiRiskLevel" class="risk-tag">风险等级：{{ aiRiskLevel }}</text>
          <text v-if="aiRiskSummary" class="ai-text">{{ aiRiskSummary }}</text>
          <text v-if="aiRiskList.length" class="section-title">要点</text>
          <text v-for="(line, i) in aiRiskList" :key="'rk' + i" class="blocker">· {{ line }}</text>
        </scroll-view>
        <view class="foot">
          <button class="btn ghost" @tap="aiRiskVisible = false">关闭</button>
        </view>
      </view>
    </view>

    <view v-if="aiSuggestVisible" class="mask" @tap="aiSuggestVisible = false">
      <view class="sheet sheet-tall" @tap.stop>
        <view class="head"><text class="title">智能排产建议（只读）</text></view>
        <view class="tabs">
          <text :class="['tab', aiTab === 'llm' ? 'active' : '']" @tap="aiTab = 'llm'">LLM 建议</text>
          <text :class="['tab', aiTab === 'optimizer' ? 'active' : '']" @tap="aiTab = 'optimizer'">OR-Tools</text>
          <text :class="['tab', aiTab === 'forecast' ? 'active' : '']" @tap="aiTab = 'forecast'">交期预测</text>
          <text :class="['tab', aiTab === 'aps' ? 'active' : '']" @tap="aiTab = 'aps'">APS 策略</text>
        </view>
        <scroll-view scroll-y class="body">
          <view v-if="aiTab === 'llm'">
            <text class="ai-text">{{ aiSuggestText || (aiSuggestLoading ? '加载中…' : '暂无') }}</text>
          </view>
          <view v-else-if="aiTab === 'optimizer'">
            <text v-if="aiOptimizeText" class="ai-text">{{ aiOptimizeText }}</text>
            <text v-else class="ai-text muted">{{ aiOptimizeLoading ? '计算中…' : '暂无优化结果' }}</text>
          </view>
          <view v-else-if="aiTab === 'forecast'">
            <view v-if="planForecast">
              <text class="risk-tag block" :class="planForecast.due_risk">风险：{{ dueRiskLabel(planForecast.due_risk) }}</text>
              <text class="ai-text">交期 {{ planForecast.due_date || '—' }} · 剩余 {{ planForecast.days_left ?? '—' }} 天</text>
              <text class="ai-text">待完成任务 {{ planForecast.remaining_tasks ?? 0 }} · 近7日均产 {{ planForecast.avg_daily_output_7d ?? 0 }}</text>
              <text class="ai-text">齐套 {{ planForecast.kitting_ok ? '正常' : '缺料' }} · 缺料项 {{ planForecast.shortage_count ?? 0 }}</text>
              <text v-for="(n, i) in planForecast.notes || []" :key="'fn' + i" class="blocker">· {{ n }}</text>
            </view>
            <text v-else class="ai-text muted">{{ aiForecastLoading ? '加载中…' : '暂无预测' }}</text>
          </view>
          <view v-else>
            <text v-if="apsData?.llm_summary" class="ai-text">{{ apsData.llm_summary }}</text>
            <text v-if="apsData?.recommended" class="section-title">推荐：{{ apsData.recommended }}</text>
            <view v-for="s in apsData?.strategies || []" :key="s.key" class="line-info">
              <text class="mat">{{ s.title }} · 得分 {{ s.score }}</text>
              <text v-if="s.suggest_start" class="nums">{{ s.suggest_start }} ~ {{ s.suggest_end || '—' }}</text>
              <text v-for="(p, i) in s.pros || []" :key="'p' + i" class="blocker ok">+ {{ p }}</text>
              <text v-for="(c, i) in s.cons || []" :key="'c' + i" class="blocker">− {{ c }}</text>
            </view>
            <text v-if="!apsData && !aiApsLoading" class="ai-text muted">暂无 APS 策略</text>
            <text v-if="aiApsLoading" class="ai-text muted">加载中…</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button class="btn ghost" @tap="aiSuggestVisible = false">关闭</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { plansAdminApi, type PlanOut } from '@/api/admin/plans'
import { aiAdminApi, type PlanOptimizeOut, type PlanForecastOut, type PlanApsStrategyOut } from '@/api/admin/ai'
import { apiGet } from '@/api/request'
import { usePermission } from '@/composables/usePermission'
import { formatAutomationFeedback } from '@/utils/automationFeedback'

type OrderOpt = { id: number; code: string; customer_name?: string; qty?: number; due_date?: string }
type Readiness = {
  ready?: boolean
  blockers?: string[]
  kitting?: { items?: { material_code?: string; material_name?: string; demand_qty: number; stock_qty: number; shortage_qty: number }[] }
  process?: {
    missing_routes?: { product_code?: string; product_name?: string }[]
    missing_prices?: { sku_name?: string; process_name?: string }[]
  }
}

const { requirePermission } = usePermission()
const items = ref<PlanOut[]>([])
const loading = ref(false)
const keyword = ref('')
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const autoscheduling = ref(false)
const aiSuggestLoading = ref(false)
const aiOptimizeLoading = ref(false)
const aiRiskLoading = ref(false)
const aiSuggestVisible = ref(false)
const aiRiskVisible = ref(false)
const aiSuggestText = ref('')
const aiOptimizeText = ref('')
const aiRiskSummary = ref('')
const aiRiskLevel = ref('')
const aiRiskList = ref<string[]>([])
const aiTab = ref<'llm' | 'optimizer' | 'forecast' | 'aps'>('llm')
const aiForecastLoading = ref(false)
const aiApsLoading = ref(false)
const planForecast = ref<PlanForecastOut | null>(null)
const forecastCache = ref<Record<number, PlanForecastOut>>({})
const apsData = ref<PlanApsStrategyOut | null>(null)
const releasing = ref(false)
const editingId = ref<number | null>(null)
const canReleaseCurrent = ref(false)
const readinessVisible = ref(false)
const readinessPlanId = ref<number | null>(null)
const readinessData = ref<Readiness | null>(null)
const orders = ref<OrderOpt[]>([])
const orderIndex = ref(0)
const form = reactive({
  order_id: null as number | null,
  code: '',
  status: 'planned',
  start_date: '',
  end_date: '',
  work_days: '',
  remark: '',
})

const statusOptions = computed(() => {
  const opts = [
    { value: 'planned', label: '计划' },
    { value: 'done', label: '已完成' },
    { value: 'canceled', label: '已取消' },
  ]
  if (form.status === 'in_progress') {
    opts.splice(1, 0, { value: 'in_progress', label: '进行中（已下发）' })
  }
  return opts
})

const orderLabels = computed(() =>
  orders.value.map((o) => {
    const due = o.due_date ? ` · 交期${o.due_date}` : ''
    return `${o.customer_name || o.code} · ${o.qty ?? 0}件 (${o.code})${due}`
  }),
)
const selectedOrderText = computed(() => {
  const o = orders.value.find((x) => x.id === form.order_id)
  return o ? orderLabels.value[orders.value.indexOf(o)] : form.order_id ? `订单#${form.order_id}` : '—'
})
const currentStatusLabel = computed(() => {
  if (form.status === 'in_progress') return '进行中（已下发）'
  return statusOptions.value.find((s) => s.value === form.status)?.label || form.status
})

onShow(async () => {
  if (!requirePermission('plan.manage')) return
  await loadOrderOptions()
  await reload()
})

function statusLabel(s: string) {
  const map: Record<string, string> = {
    planned: '计划',
    in_progress: '进行中',
    done: '已完成',
    canceled: '已取消',
  }
  return map[s] || s || '-'
}

function planTitle(item: PlanOut) {
  const code = item.order_code || item.code || item.id
  return `${code} · 生产计划`
}

function planKvRows(item: PlanOut) {
  return [
    { label: '所属订单', value: item.order_code || '—' },
    { label: '计划编码', value: item.code || '—' },
    { label: '客户', value: item.customer_name || '—' },
    { label: '计划数量', value: `${item.qty ?? 0} 件` },
    { label: '完成数量', value: `${item.done_qty ?? 0} 件` },
    { label: '计划周期', value: planPeriod(item) },
  ]
}

function planPeriod(item: PlanOut) {
  const s = item.start_date ? String(item.start_date).slice(0, 10) : ''
  const e = item.end_date ? String(item.end_date).slice(0, 10) : ''
  if (s && e) return `${s} ~ ${e}`
  return s || e || '—'
}

function planProgress(item: PlanOut) {
  const pct = Math.min(100, Number(item.progress ?? 0))
  return { pct, width: `${pct}%` }
}

function dueRiskLabel(risk?: string) {
  const map: Record<string, string> = { green: '交期正常', yellow: '交期关注', red: '交期风险' }
  return risk ? map[risk] || risk : '—'
}

function riskTone(risk?: string) {
  const map: Record<string, string> = { green: 'tone-success', yellow: 'tone-pending', red: 'tone-danger' }
  return risk ? map[risk] || 'tone-draft' : 'tone-draft'
}

async function loadPlanForecast(planId: number) {
  aiForecastLoading.value = true
  try {
    const fc = await aiAdminApi.getPlanForecast(planId)
    planForecast.value = fc
    forecastCache.value = { ...forecastCache.value, [planId]: fc }
  } catch {
    planForecast.value = null
  } finally {
    aiForecastLoading.value = false
  }
}

async function loadOrderOptions() {
  try {
    const r = await plansAdminApi.formOptions()
    orders.value = r.orders || []
  } catch {
    orders.value = []
  }
}

async function reload() {
  loading.value = true
  try {
    const r = await plansAdminApi.list({ limit: 50, keyword: keyword.value.trim() || undefined })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onOrderPick(e: { detail: { value: number } }) {
  orderIndex.value = Number(e.detail.value)
  form.order_id = orders.value[orderIndex.value]?.id ?? null
}
function onStatusPick(e: { detail: { value: number } }) {
  const opt = statusOptions.value[Number(e.detail.value)]
  if (opt && form.status !== 'in_progress') form.status = opt.value
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  form.order_id = orders.value[0]?.id ?? null
  orderIndex.value = 0
  form.code = ''
  form.status = 'planned'
  form.start_date = ''
  form.end_date = ''
  form.work_days = ''
  form.remark = ''
  formVisible.value = true
}

async function openEdit(row: PlanOut) {
  formMode.value = 'edit'
  editingId.value = row.id
  try {
    const p = await plansAdminApi.get(row.id)
    form.order_id = p.order_id
    orders.value = [
      {
        id: p.order_id,
        code: p.order_code || `订单#${p.order_id}`,
        customer_name: p.customer_name || undefined,
        qty: p.qty,
      },
    ]
    form.code = p.code || ''
    form.status = p.status || 'planned'
    form.start_date = String(p.start_date || '').slice(0, 10)
    form.end_date = String(p.end_date || '').slice(0, 10)
    form.work_days = p.work_days != null ? String(p.work_days) : ''
    form.remark = p.remark || ''
    formVisible.value = true
    if (row.id) await loadPlanForecast(row.id)
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function buildPayload() {
  if (!form.order_id && formMode.value === 'create') throw new Error('请选择订单')
  return {
    order_id: Number(form.order_id),
    code: form.code.trim() || undefined,
    status: form.status || undefined,
    start_date: form.start_date.trim() || null,
    end_date: form.end_date.trim() || null,
    work_days: form.work_days.trim() ? Number(form.work_days) : null,
    remark: form.remark.trim() || null,
  }
}

async function submit() {
  saving.value = true
  try {
    const payload = buildPayload()
    let planId = editingId.value
    if (formMode.value === 'create') {
      const created = await plansAdminApi.create(payload)
      planId = created.id
      const extra = formatAutomationFeedback(created)
      uni.showToast({
        title: extra ? `创建成功，${extra}` : '创建成功',
        icon: 'success',
        duration: extra ? 3500 : 1500,
      })
    } else if (editingId.value) {
      const updated = await plansAdminApi.update(editingId.value, payload)
      const extra = formatAutomationFeedback(updated)
      uni.showToast({
        title: extra ? `保存成功，${extra}` : '保存成功',
        icon: 'success',
        duration: extra ? 3500 : 1500,
      })
    }
    formVisible.value = false
    await reload()
    if (planId) await showReadiness(planId, rowCanRelease(planId))
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function autoSchedule() {
  if (!editingId.value) return
  autoscheduling.value = true
  try {
    const p = await plansAdminApi.autoSchedule(editingId.value, 'backward')
    form.start_date = String(p.start_date || '').slice(0, 10)
    form.end_date = String(p.end_date || '').slice(0, 10)
    form.work_days = p.work_days != null ? String(p.work_days) : ''
    uni.showToast({ title: '已按交期回推', icon: 'success' })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '排期失败', icon: 'none' })
  } finally {
    autoscheduling.value = false
  }
}

function openFactoryAssistant() {
  if (!editingId.value) return
  uni.navigateTo({ url: `/pages-admin/ai/assistant/index?planId=${editingId.value}` })
}

async function aiPlanAnalyze() {
  if (!editingId.value) return
  aiRiskLoading.value = true
  aiRiskVisible.value = true
  aiRiskSummary.value = ''
  aiRiskLevel.value = ''
  aiRiskList.value = []
  try {
    const res = await aiAdminApi.planAnalyze(editingId.value)
    aiRiskLevel.value = String(res.risk_level || '')
    aiRiskSummary.value = String(res.summary || res.reply || '')
    aiRiskList.value = [...(res.risks || []), ...(res.suggestions || [])]
  } catch (e: unknown) {
    aiRiskSummary.value = (e as Error).message || 'AI 暂不可用'
  } finally {
    aiRiskLoading.value = false
  }
}

async function aiScheduleSuggest() {
  if (!editingId.value) return
  aiSuggestLoading.value = true
  aiOptimizeLoading.value = true
  aiSuggestVisible.value = true
  aiSuggestText.value = ''
  aiOptimizeText.value = ''
  apsData.value = null
  aiTab.value = 'llm'
  const planId = editingId.value
  if (planId) loadPlanForecast(planId)
  aiApsLoading.value = true
  const apsPromise = planId
    ? aiAdminApi.getPlanApsStrategy(planId).then((d) => {
        apsData.value = d
        if (d.forecast) {
          planForecast.value = d.forecast
          forecastCache.value = { ...forecastCache.value, [planId]: d.forecast }
        }
      }).catch(() => {
        apsData.value = null
      }).finally(() => {
        aiApsLoading.value = false
      })
    : Promise.resolve()
  const [llmRes, optRes] = await Promise.allSettled([
    aiAdminApi.planScheduleSuggest(planId!),
    aiAdminApi.planScheduleOptimize(planId!),
    apsPromise,
  ])
  aiOptimizeLoading.value = false
  if (llmRes.status === 'fulfilled') {
    const llm = llmRes.value
    const parts = [llm.reply]
    if (llm.suggest_start_date) {
      parts.push(`建议：${llm.suggest_start_date} ~ ${llm.suggest_end_date || '—'}`)
    }
    if (llm.dispatch_hints?.length) parts.push(...llm.dispatch_hints)
    aiSuggestText.value = parts.filter(Boolean).join('\n\n') || '无文字建议'
  } else {
    aiSuggestText.value = llmRes.reason instanceof Error ? llmRes.reason.message : 'LLM 暂不可用'
  }
  if (optRes.status === 'fulfilled') {
    aiOptimizeText.value = formatOptimizeText(optRes.value)
  } else {
    aiOptimizeText.value = optRes.reason instanceof Error ? optRes.reason.message : '优化器暂不可用'
  }
  aiSuggestLoading.value = false
}

function formatOptimizeText(opt: PlanOptimizeOut) {
  if (opt.error) return opt.error
  if (!opt.ok && !opt.suggest_start_date) return '暂无优化结果'
  const lines: string[] = []
  if (opt.suggest_start_date) {
    lines.push(`方案（${opt.solver || 'rule'}）：${opt.suggest_start_date} ~ ${opt.suggest_end_date || '—'}`)
    lines.push(`工期 ${opt.suggest_work_days ?? '—'} 天，总工时 ${opt.total_minutes ?? '—'} 分`)
  }
  if (opt.notes?.length) lines.push(...opt.notes)
  return lines.join('\n') || '暂无'
}

function rowCanRelease(planId: number) {
  return items.value.find((x) => x.id === planId)?.can_release ?? false
}

async function previewReadiness() {
  if (!form.order_id) {
    uni.showToast({ title: '请选择订单', icon: 'none' })
    return
  }
  try {
    const data = await apiGet<Readiness>('/admin/plans/readiness/preview', { order_id: form.order_id }, true)
    readinessPlanId.value = null
    readinessData.value = data
    canReleaseCurrent.value = false
    readinessVisible.value = true
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '检查失败', icon: 'none' })
  }
}

async function checkReadiness(row: PlanOut) {
  await showReadiness(row.id, !!row.can_release)
}

async function showReadiness(planId: number, canRelease: boolean) {
  try {
    readinessPlanId.value = planId
    canReleaseCurrent.value = canRelease
    readinessData.value = await plansAdminApi.readiness(planId)
    readinessVisible.value = true
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '检查失败', icon: 'none' })
  }
}

async function releasePlan(row: PlanOut) {
  let shortage = 0
  try {
    const data = await plansAdminApi.readiness(row.id)
    shortage = data.kitting?.items?.filter((x) => x.shortage_qty > 0).length ?? 0
  } catch {
    /* 仍允许尝试下发 */
  }
  const title = shortage > 0 ? `仍有 ${shortage} 项缺料，仍要下发？` : `确认下发计划「${row.code}」？将生成工单与工序任务。`
  uni.showModal({
    title: '确认下发',
    content: title,
    success: async (res) => {
      if (!res.confirm) return
      await doRelease(row.id, shortage > 0)
    },
  })
}

async function releaseCurrent() {
  if (!readinessPlanId.value) return
  const shortage = readinessData.value?.kitting?.items?.filter((x) => x.shortage_qty > 0).length ?? 0
  await doRelease(readinessPlanId.value, shortage > 0)
}

async function doRelease(planId: number, allowShortage: boolean) {
  releasing.value = true
  try {
    const res = await plansAdminApi.release(planId, allowShortage)
    uni.showToast({
      title: `已下发：工单${res.work_order_count ?? 0} · 任务${res.task_count ?? 0}`,
      icon: 'success',
    })
    readinessVisible.value = false
    formVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '下发失败', icon: 'none' })
  } finally {
    releasing.value = false
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.add-btn { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; border-radius: 999rpx; }
.row-head { display: flex; justify-content: space-between; align-items: center; }
.row-tags { display: flex; gap: 8rpx; align-items: center; flex-shrink: 0; }
.status-tag { font-size: 22rpx; color: #4338ca; background: #eef2ff; padding: 4rpx 12rpx; border-radius: 999rpx; }
.risk-tag { font-size: 20rpx; padding: 4rpx 12rpx; border-radius: 999rpx; }
.risk-tag.green { color: #15803d; background: #dcfce7; }
.risk-tag.yellow { color: #b45309; background: #fef3c7; }
.risk-tag.red { color: #b91c1c; background: #fee2e2; }
.risk-tag.block { display: block; margin-bottom: 12rpx; }
.blocker.ok { color: #15803d; }
.row-actions { display: flex; gap: 20rpx; margin-top: 12rpx; }
.act { font-size: 24rpx; color: #64748b; padding: 8rpx 0; }
.act.primary { color: #4338ca; font-weight: 600; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; display: flex; align-items: center; justify-content: space-between; }
.title { font-size: 32rpx; font-weight: 700; }
.tag { font-size: 24rpx; padding: 6rpx 16rpx; border-radius: 999rpx; }
.tag.ok { color: #15803d; background: #dcfce7; }
.tag.bad { color: #b45309; background: #fef3c7; }
.body { max-height: 58vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.input.disabled { color: #64748b; }
.area { min-height: 120rpx; width: 100%; }
.picker { color: #334155; }
.section-title { font-size: 28rpx; font-weight: 600; margin: 16rpx 0 8rpx; }
.line-info { background: #f8fafc; border-radius: 12rpx; padding: 16rpx; margin-bottom: 12rpx; }
.mat { display: block; font-size: 28rpx; font-weight: 600; }
.nums { display: block; font-size: 24rpx; color: #64748b; margin-top: 6rpx; }
.blockers { margin-bottom: 16rpx; }
.blocker { display: block; font-size: 26rpx; color: #b45309; margin-bottom: 6rpx; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
.sheet-tall { max-height: 88vh; }
.tabs { display: flex; gap: 24rpx; padding: 16rpx 32rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.tab { font-size: 28rpx; color: #64748b; padding-bottom: 12rpx; }
.tab.active { color: #4338ca; font-weight: 600; border-bottom: 4rpx solid #4338ca; }
.ai-text { font-size: 26rpx; color: #334155; white-space: pre-wrap; line-height: 1.6; display: block; }
.risk-tag { display: block; font-size: 26rpx; font-weight: 600; color: #b45309; margin-bottom: 12rpx; }
.ai-text.muted { color: #94a3b8; }
</style>
