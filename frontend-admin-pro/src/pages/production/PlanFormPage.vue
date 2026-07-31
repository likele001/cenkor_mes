<template>
  <AdminPage :title="isEdit ? t('production.planForm.titleEdit') : t('production.planForm.titleCreate')">
    <el-card v-loading="loading">
          <template #actions>
      <div class="flex items-center gap-2">
          <el-button @click="router.push('/plans')">{{ t('production.common.back') }}</el-button>
          <el-button v-if="form.order_id" :loading="previewing" @click="previewReadiness">{{ t('production.planForm.readinessPreview') }}</el-button>
          <el-button v-if="isEdit" :loading="autoscheduling" @click="autoSchedule">{{ t('production.planForm.autoSchedule') }}</el-button>
          <el-button v-if="isEdit && canAi" :loading="aiScheduling" @click="aiScheduleSuggest">{{ t('production.planForm.aiSchedule') }}</el-button>
          <el-button v-if="isEdit && canAi" :loading="aiAnalyzing" @click="aiPlanAnalyze">{{ t('production.planForm.aiAnalyze') }}</el-button>
          <el-button type="primary" :loading="saving" @click="save">{{ t('production.common.save') }}</el-button>
        </div>
    </template>


      <el-alert
        class="mt-4"
        type="info"
        :closable="false"
        show-icon
        title="保存后将自动进行齐套、工艺路线与工价检查，缺料可生成采购单，工艺/工价不全请先去主数据补全。"
      />

      <el-alert
        v-if="automationSettings?.enabled"
        class="mt-4"
        type="success"
        :closable="false"
        show-icon
        title="生产自动化已启用：保存本计划可能触发自动排产、下发或派工"
      >
        <el-button v-if="canAutomationSettings" link type="primary" @click="router.push('/system/automation-settings')">自动化设置</el-button>
      </el-alert>

      <el-tabs v-model="activeTab" class="mt-4">
        <el-tab-pane label="基本信息" name="basic">
      <el-form class="mt-2" :model="form" label-width="110px">
        <el-form-item label="关联订单" required>
          <template v-if="isEdit">
            <el-input :model-value="selectedOrderLabel" disabled style="width: 480px" />
            <div class="text-xs text-zinc-500 mt-1">{{ t('production.planForm.editOrderHint') }}</div>
          </template>
          <template v-else>
            <el-select
              v-model="form.order_id"
              filterable
              clearable
              placeholder="选择已审核、未投产的订单"
              style="width: 480px"
              :loading="ordersLoading"
              @visible-change="(v: boolean) => v && loadOrderOptions()"
            >
              <el-option
                v-for="o in orderOptions"
                :key="o.id"
                :label="orderOptionLabel(o)"
                :value="o.id"
              >
                <div class="leading-tight py-0.5">
                  <div class="font-medium">{{ orderOptionMain(o) }}</div>
                  <div class="text-xs text-zinc-500">
                    订单号 {{ o.code }} · 数量 {{ o.qty }} · 交期 {{ o.due_date || '—' }}
                  </div>
                </div>
              </el-option>
            </el-select>
            <div v-if="!ordersLoading && !orderOptions.length" class="text-xs text-amber-600 mt-1">
              暂无可选订单：请先在「订单」中审核通过，且该订单尚未下发投产（无工单）。
            </div>
          </template>
        </el-form-item>
        <el-form-item label="计划编号">
          <el-input v-model="form.code" placeholder="留空保存时自动生成，如 PLN202605200001" style="width: 360px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 240px" :disabled="form.status === 'in_progress'">
            <el-option label="计划" value="planned" />
            <el-option v-if="form.status === 'in_progress'" label="进行中（已下发）" value="in_progress" />
            <el-option label="已完成" value="done" />
            <el-option label="已取消" value="canceled" />
          </el-select>
          <div class="text-xs text-zinc-500 mt-1">「进行中」须在生产计划列表通过「确认下发」进入，不可手动切换。</div>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 240px" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 240px" />
        </el-form-item>
        <el-form-item label="工期(天)">
          <el-input-number v-model="form.work_days" :min="0" :controls="false" style="width: 240px" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="4" style="width: 520px" />
        </el-form-item>
      </el-form>
        </el-tab-pane>

        <el-tab-pane v-if="isEdit" label="APS 策略" name="aps" lazy>
          <div v-loading="apsLoading" class="max-w-2xl py-2">
            <div v-if="planForecast" class="mb-6">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium text-zinc-700">{{ t('production.planForm.dueRiskForecast') }}</span>
                <el-tag :type="riskTagType(planForecast.due_risk)" size="small">{{ riskLabel(planForecast.due_risk) }}</el-tag>
              </div>
              <el-progress
                :percentage="riskBarPercent(planForecast.due_risk)"
                :color="riskBarColor(planForecast.due_risk)"
                :stroke-width="14"
              />
              <dl class="mt-3 text-xs text-zinc-600 grid grid-cols-2 gap-2">
                <div><span class="text-zinc-400">交期</span> {{ planForecast.due_date || '—' }}</div>
                <div><span class="text-zinc-400">{{ t('production.planForm.daysLeft') }}</span> {{ planForecast.days_left ?? '—' }}</div>
                <div><span class="text-zinc-400">{{ t('production.planForm.remainingTasks') }}</span> {{ planForecast.remaining_tasks }}</div>
                <div><span class="text-zinc-400">{{ t('production.planForm.avgDailyOutput') }}</span> {{ planForecast.avg_daily_output_7d }}</div>
                <div><span class="text-zinc-400">{{ t('production.planForm.kitting') }}</span> {{ planForecast.kitting_ok ? '通过' : '缺料' }}</div>
                <div><span class="text-zinc-400">{{ t('production.planForm.shortageCount') }}</span> {{ planForecast.shortage_count }}</div>
              </dl>
            </div>
            <el-empty v-if="!apsLoading && !apsStrategies.length" description="暂无策略分析" />
            <div v-for="s in apsStrategies" :key="s.key" class="border rounded-lg p-3 mb-3">
              <div class="flex items-center justify-between gap-2">
                <span class="font-medium text-sm">{{ s.title }}</span>
                <el-tag v-if="apsRecommended === s.key" type="success" size="small">{{ t('production.planForm.recommended') }}</el-tag>
                <span class="text-xs text-zinc-500">评分 {{ s.score }}</span>
              </div>
              <p v-if="s.pros?.length" class="text-xs text-green-700 mt-2">优点：{{ s.pros.join('；') }}</p>
              <p v-if="s.cons?.length" class="text-xs text-amber-700 mt-1">注意：{{ s.cons.join('；') }}</p>
            </div>
            <p v-if="apsLlmSummary" class="text-sm text-zinc-600 whitespace-pre-wrap mt-2">{{ apsLlmSummary }}</p>
            <el-button class="mt-2" size="small" :loading="apsLoading" @click="loadApsTab">{{ t('production.planForm.refreshAnalysis') }}</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <PlanReadinessDrawer
      v-model="readinessOpen"
      :plan-id="readinessPlanId"
      :order-id="readinessOrderId"
      title="投产就绪检查"
      @closed="onReadinessClosed"
    />

    <el-dialog v-model="aiDlg" :title="aiDlgTitle" width="640px" destroy-on-close>
      <div v-loading="aiDlgLoading" class="text-sm whitespace-pre-wrap text-zinc-700">{{ aiDlgText }}</div>
      <ul v-if="aiDlgList.length" class="mt-3 list-disc pl-5 text-sm text-zinc-600">
        <li v-for="(t, i) in aiDlgList" :key="i">{{ t }}</li>
      </ul>
      <template v-if="aiDlgMode === 'schedule'" #footer>
        <el-button @click="aiDlg = false">{{ t('production.common.close') }}</el-button>
        <el-button type="primary" :loading="aiApplying" @click="aiScheduleApply">{{ t('production.planForm.applySchedule') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { plansApi, type PlanOrderOption } from '@/api/plans'
import { aiApi, type PlanForecastOut, type PlanScheduleOut, type PlanApsStrategyItem } from '@/api/ai'
import { automationApi, type AutomationSettings } from '@/api/automation'
import { formatAutomationFeedback } from '@/utils/automationFeedback'
import { useAuthStore } from '@/stores/auth'
import { systemApi } from '@/api/system'
import { codeForSubmit } from '@/utils/code'
import PlanReadinessDrawer from '@/components/PlanReadinessDrawer.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const canAi = computed(() => auth.hasAnyPermission(['ai.use', 'plan.manage']))
const canAutomationSettings = computed(() => auth.hasAnyPermission(['setting.manage']))
const automationSettings = ref<AutomationSettings | null>(null)
const activeTab = ref('basic')
const apsLoading = ref(false)
const planForecast = ref<PlanForecastOut | null>(null)
const apsStrategies = ref<PlanApsStrategyItem[]>([])
const apsRecommended = ref('')
const apsLlmSummary = ref<string | null>(null)

function riskLabel(risk: string) {
  if (risk === 'green') return '低风险'
  if (risk === 'yellow') return '中风险'
  if (risk === 'red') return '高风险'
  return risk
}

function riskTagType(risk: string): 'success' | 'warning' | 'danger' | 'info' {
  if (risk === 'green') return 'success'
  if (risk === 'yellow') return 'warning'
  if (risk === 'red') return 'danger'
  return 'info'
}

function riskBarPercent(risk: string) {
  if (risk === 'green') return 25
  if (risk === 'yellow') return 55
  if (risk === 'red') return 90
  return 40
}

function riskBarColor(risk: string) {
  if (risk === 'green') return '#67c23a'
  if (risk === 'yellow') return '#e6a23c'
  if (risk === 'red') return '#f56c6c'
  return '#909399'
}

async function loadAutomationHint() {
  if (!canAutomationSettings.value) return
  try {
    automationSettings.value = await automationApi.getAutomationSettings()
  } catch {
    automationSettings.value = null
  }
}

async function loadApsTab() {
  if (!isEdit.value) return
  apsLoading.value = true
  try {
    planForecast.value = await aiApi.getPlanForecast(id.value)
    if (canAi.value) {
      const aps = await aiApi.getPlanApsStrategy(id.value)
      apsStrategies.value = aps.strategies || []
      apsRecommended.value = aps.recommended || ''
      apsLlmSummary.value = aps.llm_summary || null
      if (aps.forecast) planForecast.value = aps.forecast
    } else {
      apsStrategies.value = []
      apsLlmSummary.value = null
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : t('production.planForm.apsLoadFailed'))
  } finally {
    apsLoading.value = false
  }
}

const id = computed(() => Number(route.params.id))
const isEdit = computed(() => Number.isFinite(id.value) && id.value > 0)

const loading = ref(false)
const ordersLoading = ref(false)
const orderOptions = ref<PlanOrderOption[]>([])
const saving = ref(false)
const previewing = ref(false)
const autoscheduling = ref(false)
const aiScheduling = ref(false)
const aiAnalyzing = ref(false)
const aiApplying = ref(false)
const aiDlg = ref(false)
const aiDlgLoading = ref(false)
const aiDlgTitle = ref('')
const aiDlgText = ref('')
const aiDlgList = ref<string[]>([])
const aiDlgMode = ref<'schedule' | 'risk'>('risk')
const lastScheduleSuggest = ref<PlanScheduleOut | null>(null)

const readinessOpen = ref(false)
const readinessPlanId = ref<number | null>(null)
const readinessOrderId = ref<number | null>(null)
const savedNavigateToList = ref(false)

const selectedOrderLabel = computed(() => {
  const o = orderOptions.value.find((x) => x.id === form.order_id)
  if (o) return orderOptionLabel(o)
  if (form.order_id && isEdit.value) return `订单 #${form.order_id}`
  return ''
})

function orderOptionMain(o: PlanOrderOption) {
  return o.customer_name ? `${o.customer_name} · ${o.qty} 件` : `订单 ${o.code} · ${o.qty} 件`
}

function orderOptionLabel(o: PlanOrderOption) {
  const due = o.due_date ? ` · 交期 ${o.due_date}` : ''
  return `${orderOptionMain(o)}（${o.code}）${due}`
}

async function loadOrderOptions() {
  if (orderOptions.value.length) return
  ordersLoading.value = true
  try {
    const res = await plansApi.getPlanFormOptions()
    orderOptions.value = res.orders || []
  } finally {
    ordersLoading.value = false
  }
}

const form = reactive({
  order_id: null as number | null,
  code: '',
  status: 'planned',
  start_date: '' as string | null,
  end_date: '' as string | null,
  work_days: null as number | null,
  remark: '',
})

function openReadiness(opts: { planId?: number | null; orderId?: number | null; goListOnClose?: boolean }) {
  readinessPlanId.value = opts.planId ?? null
  readinessOrderId.value = opts.orderId ?? null
  savedNavigateToList.value = !!opts.goListOnClose
  readinessOpen.value = true
}

function onReadinessClosed() {
  if (savedNavigateToList.value) {
    router.push('/plans')
  }
}

async function load() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const p = await plansApi.getPlan(id.value)
    form.order_id = p.order_id
    orderOptions.value = [
      {
        id: p.order_id,
        code: p.order_code || `订单#${p.order_id}`,
        customer_id: 0,
        customer_name: p.customer_name,
        due_date: null,
        qty: p.qty ?? 0,
        remark: null,
      },
    ]
    form.code = p.code
    form.status = p.status || 'planned'
    form.start_date = p.start_date
    form.end_date = p.end_date
    form.work_days = p.work_days
    form.remark = p.remark || ''
  } finally {
    loading.value = false
  }
}

async function previewReadiness() {
  if (!form.order_id) return ElMessage.warning(t('production.planForm.selectOrder'))
  if (previewing.value) return
  previewing.value = true
  try {
    openReadiness({ orderId: Number(form.order_id), goListOnClose: false })
  } finally {
    previewing.value = false
  }
}

async function save() {
  if (saving.value) return
  if (!form.order_id) return ElMessage.warning(t('production.planForm.selectOrder'))
  saving.value = true
  try {
    const payload = {
      order_id: Number(form.order_id),
      code: codeForSubmit(form.code) || undefined,
      status: form.status || undefined,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      work_days: form.work_days ?? null,
      remark: form.remark || null,
    }
    let planId = id.value
    if (isEdit.value) {
      const updated = await plansApi.updatePlan(id.value, payload)
      const autoMsg = formatAutomationFeedback(updated)
      ElMessage.success(autoMsg ? `已更新。${autoMsg}` : '已更新，正在检查齐套与工艺…')
    } else {
      const created = await plansApi.createPlan(payload)
      planId = created.id
      const autoMsg = formatAutomationFeedback(created)
      ElMessage.success(autoMsg ? `已创建。${autoMsg}` : '已创建，正在检查齐套与工艺…')
    }
    openReadiness({ planId, goListOnClose: false })
  } finally {
    saving.value = false
  }
}

async function autoSchedule() {
  if (!isEdit.value) return
  if (autoscheduling.value) return
  autoscheduling.value = true
  try {
    const p = await plansApi.autoSchedule(id.value, { mode: 'backward' })
    form.start_date = p.start_date
    form.end_date = p.end_date
    form.work_days = p.work_days
    ElMessage.success(t('production.planForm.autoScheduleApplied'))
  } finally {
    autoscheduling.value = false
  }
}

async function aiScheduleSuggest() {
  if (!isEdit.value) return
  aiScheduling.value = true
  aiDlgLoading.value = true
  aiDlgMode.value = 'schedule'
  aiDlgTitle.value = t('production.planForm.aiScheduleTitle')
  aiDlg.value = true
  aiDlgText.value = ''
  aiDlgList.value = []
  try {
    const res = await aiApi.planScheduleSuggest(id.value)
    lastScheduleSuggest.value = res
    aiDlgText.value = res.reply || ''
    const hints = [...(res.dispatch_hints || []), ...(res.overload_warnings || [])]
    if (res.suggest_start_date || res.suggest_end_date) {
      hints.unshift(`建议：${res.suggest_mode === 'forward' ? '正排' : '倒排'} ${res.suggest_start_date || '—'} ~ ${res.suggest_end_date || '—'}`)
    }
    aiDlgList.value = hints
  } catch (e: unknown) {
    aiDlgText.value = e instanceof Error ? e.message : t('production.planForm.aiUnavailable')
  } finally {
    aiScheduling.value = false
    aiDlgLoading.value = false
  }
}

async function aiPlanAnalyze() {
  if (!isEdit.value) return
  aiAnalyzing.value = true
  aiDlgLoading.value = true
  aiDlgMode.value = 'risk'
  aiDlgTitle.value = t('production.planForm.aiAnalyzeTitle')
  aiDlg.value = true
  aiDlgText.value = ''
  aiDlgList.value = []
  try {
    const res = await aiApi.planAnalyze(id.value)
    aiDlgText.value = res.reply || res.summary || ''
    aiDlgList.value = [...(res.risks || []), ...(res.suggestions || [])]
  } catch (e: unknown) {
    aiDlgText.value = e instanceof Error ? e.message : t('production.planForm.aiUnavailable')
  } finally {
    aiAnalyzing.value = false
    aiDlgLoading.value = false
  }
}

async function aiScheduleApply() {
  const mode = lastScheduleSuggest.value?.suggest_mode === 'forward' ? 'forward' : 'backward'
  await ElMessageBox.confirm(
    '将依次：调整计划日期 → 未下发则自动确认下发 → 自动派工。物料未齐套请先在计划列表用「允许缺料」下达。',
    '采纳排产',
  )
  aiApplying.value = true
  try {
    await aiApi.planScheduleApply(id.value, { mode, unassigned_only: true, auto_release: true })
    ElMessage.success('已执行排产与派工，请刷新计划日期')
    const p = await plansApi.getPlan(id.value)
    form.start_date = p.start_date
    form.end_date = p.end_date
    form.work_days = p.work_days
    aiDlg.value = false
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : t('production.planForm.executeFailed'))
  } finally {
    aiApplying.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'aps' && isEdit.value) loadApsTab()
})

onMounted(async () => {
  await loadAutomationHint()
  if (!isEdit.value) {
    const q = route.query.order_id
    if (q) form.order_id = Number(q) || null
    await loadOrderOptions()
    try {
      const res = await systemApi.nextCode('production_plan')
      form.code = res.code
    } catch {
      /* 后端未部署时留空，保存时自动生成 */
    }
  }
  await load()
})
</script>
