<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('menu.automationSettings')">
    <el-card v-loading="loading">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div class="text-[16px] font-semibold">生产自动化</div>
          <p class="text-xs text-zinc-500 mt-1">
            总开关关掉时下面所有自动化动作都不执行。改完记得保存；试运行不会写任何数据。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <el-button @click="load">{{ t('production.common.refresh') }}</el-button>
          <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
        </div>
      </div>

      <el-form label-width="200px" class="mt-4">
        <el-form-item label="启用生产自动化">
          <el-switch v-model="form.enabled" />
        </el-form-item>

        <el-divider content-position="left">订单确认后</el-divider>
        <el-form-item label="自动创建生产计划">
          <el-switch v-model="form.on_order_confirm.create_plan" />
        </el-form-item>
        <el-form-item label="计划开始日偏移（天）">
          <el-input-number v-model="form.on_order_confirm.start_offset_days" :min="0" :max="60" />
        </el-form-item>
        <el-form-item label="建完计划接着排产下发">
          <el-switch v-model="form.on_order_confirm.run_pipeline_after_create" />
        </el-form-item>

        <el-divider content-position="left">计划保存后</el-divider>
        <el-form-item label="自动排产">
          <el-switch v-model="form.on_plan_saved.run_schedule" />
        </el-form-item>
        <el-form-item label="排产引擎">
          <el-select v-model="form.on_plan_saved.engine" style="width: 200px">
            <el-option label="ortools" value="ortools" />
            <el-option label="规则（fallback）" value="rule" />
          </el-select>
        </el-form-item>
        <el-form-item label="自动下发工单">
          <el-switch v-model="form.on_plan_saved.auto_release" />
        </el-form-item>
        <el-form-item label="自动派工">
          <el-switch v-model="form.on_plan_saved.auto_dispatch" />
        </el-form-item>
        <el-form-item label="允许缺料照样下发">
          <el-switch v-model="form.on_plan_saved.allow_shortage" />
          <span class="ml-3 text-xs text-[var(--el-color-warning)]">开着等于放弃齐套闸门，一般只在赶单时临时打开</span>
        </el-form-item>

        <el-divider content-position="left">报工审核</el-divider>
        <el-form-item label="提交时预筛">
          <el-switch v-model="form.audit.prescreen_on_submit" />
        </el-form-item>
        <el-form-item label="自动初审">
          <el-switch v-model="form.audit.auto_leader_approve" />
        </el-form-item>
        <el-form-item label="自动终审">
          <el-switch v-model="form.audit.auto_qc_approve" />
        </el-form-item>
        <el-form-item label="必须员工照片">
          <el-switch v-model="form.audit.require_employee_photo" />
        </el-form-item>
        <el-form-item label="图像识别通过分">
          <el-input-number v-model="form.audit.vision_min_score" :min="0" :max="1" :step="0.05" :precision="2" />
        </el-form-item>
        <el-form-item label="前道工序被驳回则拦截">
          <el-switch v-model="form.audit.block_if_prior_reject" />
        </el-form-item>

        <el-divider content-position="left">简报与预警</el-divider>
        <el-form-item label="每日生产简报">
          <el-switch v-model="form.briefing.daily_enabled" />
        </el-form-item>
        <el-form-item label="简报发送时刻">
          <el-input-number v-model="form.briefing.daily_hour" :min="0" :max="23" />
        </el-form-item>
        <el-form-item label="简报取数方式">
          <el-select v-model="form.briefing.mode" style="width: 200px">
            <el-option label="规则汇总（rule）" value="rule" />
            <el-option label="AI 汇总（ai）" value="ai" />
          </el-select>
        </el-form-item>
        <el-form-item label="扫描到异常即推送">
          <el-switch v-model="form.alerts.notify_on_scan" />
        </el-form-item>
        <el-form-item label="严重异常生成待办">
          <el-switch v-model="form.alerts.create_todo_on_critical" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="canPlanManage" class="mt-4">
      <div class="text-[16px] font-semibold">试运行</div>
      <p class="text-xs text-zinc-500 mt-1">
        按当前配置预演一遍「这个订单/计划自动化会怎么走」，只报阻塞点，不建计划、不下发、不派工。
      </p>
      <div class="mt-3 flex items-center gap-3 flex-wrap">
        <el-input-number v-model="dryRun.order_id" :min="1" :controls="false" placeholder="订单 ID" style="width: 140px" />
        <el-input-number v-model="dryRun.plan_id" :min="1" :controls="false" placeholder="计划 ID" style="width: 140px" />
        <el-checkbox v-model="dryRun.allow_shortage">允许缺料</el-checkbox>
        <el-button type="primary" :loading="dryRunning" @click="onDryRun">开始试运行</el-button>
      </div>

      <div v-if="dryRunResult" class="mt-4">
        <el-tag :type="dryRunResult.ok ? 'success' : 'danger'" size="large">
          {{ dryRunResult.ok ? '可以通过自动化' : '会被自动化拦下' }}
        </el-tag>
        <el-table :data="dryRunChecks" border class="mt-3">
          <el-table-column label="级别" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.level === 'error' ? 'danger' : 'warning'" size="small">
                {{ row.level === 'error' ? '阻塞' : '提醒' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="320" />
        </el-table>
        <el-empty v-if="!dryRunChecks.length" description="没有阻塞点，也没有提醒" :image-size="60" />
      </div>
    </el-card>

    <el-card class="mt-4">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="text-[16px] font-semibold">自动化执行日志</div>
        <div class="flex items-center gap-2 flex-wrap">
          <el-input v-model="logs.trigger" clearable placeholder="触发点" style="width: 160px" @change="loadLogs" />
          <el-input v-model="logs.status" clearable placeholder="结果" style="width: 140px" @change="loadLogs" />
          <el-button :loading="logsLoading" @click="loadLogs">{{ t('production.common.refresh') }}</el-button>
        </div>
      </div>
      <p class="text-xs text-zinc-500 mt-1">
        自动化每次替你做的决定都记在这里：成功/失败、动了哪张单、为什么没动。这里空白说明自动化根本没被触发过。
      </p>
      <el-table :data="logs.items" border v-loading="logsLoading" class="mt-3" max-height="520">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="trigger" label="触发点" width="150" />
        <el-table-column prop="action" label="动作" width="160" />
        <el-table-column label="对象" width="150">
          <template #default="{ row }">
            <span v-if="row.biz_type">{{ row.biz_type }} #{{ row.biz_id ?? '—' }}</span>
            <span v-else class="text-zinc-400">—</span>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="logTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip />
      </el-table>
      <el-empty v-if="!logs.items.length && !logsLoading" description="还没有自动化执行记录" :image-size="60" />
    </el-card>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { useAuthStore } from '@/stores/auth'
import {
  automationApi,
  type AutomationCheck,
  type AutomationDryRunOut,
  type AutomationLog,
  type AutomationSettings,
} from '@/api/automation'

const { t } = useI18n()
const auth = useAuthStore()
const canPlanManage = computed(() => auth.hasAnyPermission(['plan.manage']))

const loading = ref(false)
const saving = ref(false)

const EMPTY: AutomationSettings = {
  enabled: false,
  on_order_confirm: { create_plan: false, start_offset_days: 0, run_pipeline_after_create: false },
  on_plan_saved: {
    run_schedule: false,
    engine: 'ortools',
    auto_release: false,
    auto_dispatch: false,
    allow_shortage: false,
  },
  audit: {
    prescreen_on_submit: true,
    auto_leader_approve: false,
    auto_qc_approve: false,
    require_employee_photo: true,
    vision_min_score: 0.75,
    block_if_prior_reject: true,
  },
  briefing: { daily_enabled: false, daily_hour: 8, mode: 'rule' },
  alerts: { notify_on_scan: true, create_todo_on_critical: true },
}

const form = reactive<AutomationSettings>(structuredClone(EMPTY))

function applySettings(data: AutomationSettings) {
  Object.assign(form, structuredClone(data))
}

async function load() {
  loading.value = true
  try {
    applySettings(await automationApi.getAutomationSettings())
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

async function onSave() {
  saving.value = true
  try {
    applySettings(await automationApi.saveAutomationSettings(structuredClone(form)))
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    saving.value = false
  }
}

// ── 试运行 ──

const dryRun = reactive<{ order_id?: number; plan_id?: number; allow_shortage: boolean }>({
  order_id: undefined,
  plan_id: undefined,
  allow_shortage: false,
})
const dryRunning = ref(false)
const dryRunResult = ref<AutomationDryRunOut | null>(null)
const dryRunChecks = computed<AutomationCheck[]>(() => dryRunResult.value?.checks ?? [])

async function onDryRun() {
  if (!dryRun.order_id && !dryRun.plan_id) {
    ElMessage.warning('请填写订单 ID 或计划 ID')
    return
  }
  dryRunning.value = true
  try {
    dryRunResult.value = await automationApi.dryRun({
      order_id: dryRun.order_id || undefined,
      plan_id: dryRun.plan_id || undefined,
      allow_shortage: dryRun.allow_shortage,
    })
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    dryRunning.value = false
  }
}

// ── 执行日志 ──

const logs = reactive<{ items: AutomationLog[]; trigger: string; status: string }>({
  items: [],
  trigger: '',
  status: '',
})
const logsLoading = ref(false)

function logTagType(status: string) {
  if (status === 'success' || status === 'ok') return 'success'
  if (status === 'skipped') return 'info'
  return 'danger'
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const res = await automationApi.listLogs({
      trigger: logs.trigger || undefined,
      status: logs.status || undefined,
      limit: 200,
    })
    logs.items = res.items ?? []
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    logsLoading.value = false
  }
}

onMounted(() => {
  load()
  loadLogs()
})
</script>
