<template>
  <view class="adm-page">
    <view class="hero">
      <text class="hero-title">生产自动化</text>
      <text class="hero-sub">订单确认、计划保存、报工审核与每日简报</text>
    </view>

    <view v-if="loading" class="tip">加载中...</view>

    <view v-else class="sections">
      <view class="section">
        <view class="row-between">
          <text class="label">启用自动化总开关</text>
          <switch :checked="form.enabled" color="#4338ca" @change="onMaster" />
        </view>
      </view>

      <view class="section">
        <text class="sec-title">订单确认后</text>
        <view class="row-between"><text class="label">自动创建生产计划</text><switch :checked="form.on_order_confirm.create_plan" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.on_order_confirm.create_plan = e.detail.value" /></view>
        <view class="row-between"><text class="label">创建后跑排产流水线</text><switch :checked="form.on_order_confirm.run_pipeline_after_create" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.on_order_confirm.run_pipeline_after_create = e.detail.value" /></view>
      </view>

      <view class="section">
        <text class="sec-title">计划保存后</text>
        <view class="row-between"><text class="label">自动排产</text><switch :checked="form.on_plan_saved.run_schedule" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.on_plan_saved.run_schedule = e.detail.value" /></view>
        <view class="row-between"><text class="label">自动确认下发</text><switch :checked="form.on_plan_saved.auto_release" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.on_plan_saved.auto_release = e.detail.value" /></view>
        <view class="row-between"><text class="label">自动派工</text><switch :checked="form.on_plan_saved.auto_dispatch" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.on_plan_saved.auto_dispatch = e.detail.value" /></view>
      </view>

      <view class="section">
        <text class="sec-title">报工审核</text>
        <view class="row-between"><text class="label">提交时预筛</text><switch :checked="form.audit.prescreen_on_submit" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.audit.prescreen_on_submit = e.detail.value" /></view>
        <view class="row-between"><text class="label">自动班组长初审</text><switch :checked="form.audit.auto_leader_approve" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.audit.auto_leader_approve = e.detail.value" /></view>
        <view class="row-between"><text class="label">要求员工现场照片</text><switch :checked="form.audit.require_employee_photo" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.audit.require_employee_photo = e.detail.value" /></view>
      </view>

      <view class="section">
        <text class="sec-title">每日简报</text>
        <view class="row-between"><text class="label">定时推送</text><switch :checked="form.briefing.daily_enabled" :disabled="!form.enabled" color="#4338ca" @change="(e) => form.briefing.daily_enabled = e.detail.value" /></view>
        <view class="field">
          <text class="label">推送小时</text>
          <input v-model.number="form.briefing.daily_hour" type="number" class="input" :disabled="!form.enabled || !form.briefing.daily_enabled" />
        </view>
        <view class="field">
          <text class="label">生成模式</text>
          <picker :range="['规则汇总', 'LLM 生成']" :disabled="!form.enabled" @change="onBriefMode">
            <view class="input picker">{{ form.briefing.mode === 'llm' ? 'LLM 生成' : '规则汇总' }}</view>
          </picker>
        </view>
      </view>

      <button class="btn primary" :loading="saving" @tap="save">保存配置</button>
      <button class="btn ghost" @tap="loadLogs">最近执行日志</button>
    </view>

    <view v-if="logsVisible" class="mask" @tap="logsVisible = false">
      <view class="sheet" @tap.stop>
        <view class="sheet-head"><text class="sheet-title">执行日志</text></view>
        <scroll-view scroll-y class="log-body">
          <view v-for="log in logs" :key="log.id" class="log-row">
            <text class="log-meta">{{ log.trigger }} · {{ log.status }}</text>
            <text class="log-msg">{{ log.message || log.action }}</text>
          </view>
          <text v-if="!logs.length" class="tip">暂无日志</text>
        </scroll-view>
        <button class="btn ghost" @tap="logsVisible = false">关闭</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { reactive, ref } from 'vue'
import { automationAdminApi, type AutomationLogOut, type AutomationSettings } from '@/api/admin/automation'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const loading = ref(false)
const saving = ref(false)
const logsVisible = ref(false)
const logs = ref<AutomationLogOut[]>([])

const defaults = (): AutomationSettings => ({
  enabled: false,
  on_order_confirm: { create_plan: false, start_offset_days: 0, run_pipeline_after_create: false },
  on_plan_saved: { run_schedule: false, engine: 'rule', auto_release: false, auto_dispatch: false, allow_shortage: false },
  audit: { prescreen_on_submit: true, auto_leader_approve: false, auto_qc_approve: false, require_employee_photo: true, vision_min_score: 0.75, block_if_prior_reject: true },
  briefing: { daily_enabled: false, daily_hour: 8, mode: 'rule' },
  alerts: { notify_on_scan: true, create_todo_on_critical: false },
})

const form = reactive<AutomationSettings>(defaults())

onShow(async () => {
  if (!requirePermission('setting.manage')) return
  loading.value = true
  try {
    Object.assign(form, defaults(), await automationAdminApi.getSettings())
    form.briefing.mode = form.briefing.mode === 'llm' ? 'llm' : 'rule'
  } catch {
    /* 默认 */
  } finally {
    loading.value = false
  }
})

function onMaster(e: { detail: { value: boolean } }) {
  if (e.detail.value) {
    uni.showModal({
      title: '确认开启',
      content: '开启后将在订单确认、计划保存等环节自动执行配置动作',
      success: (res) => {
        if (res.confirm) form.enabled = true
      },
    })
    return
  }
  form.enabled = false
}

function onBriefMode(e: { detail: { value: string } }) {
  form.briefing.mode = Number(e.detail.value) === 1 ? 'llm' : 'rule'
}

async function save() {
  saving.value = true
  try {
    Object.assign(form, await automationAdminApi.saveSettings(form))
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function loadLogs() {
  logsVisible.value = true
  try {
    const r = await automationAdminApi.listLogs({ limit: 30 })
    logs.value = r.items || []
  } catch {
    logs.value = []
  }
}
</script>

<style scoped lang="scss">
.hero { padding: 24rpx; }
.hero-title { display: block; font-size: 34rpx; font-weight: 700; color: #1e293b; }
.hero-sub { display: block; font-size: 24rpx; color: #64748b; margin-top: 8rpx; }
.tip { padding: 24rpx; font-size: 26rpx; color: #94a3b8; text-align: center; }
.sections { padding: 0 24rpx 48rpx; }
.section { background: #fff; border-radius: 16rpx; padding: 24rpx; margin-bottom: 20rpx; }
.sec-title { display: block; font-size: 28rpx; font-weight: 600; margin-bottom: 16rpx; color: #334155; }
.row-between { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16rpx; }
.label { font-size: 26rpx; color: #475569; }
.field { margin-bottom: 16rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 16rpx; font-size: 28rpx; }
.picker { color: #334155; }
.btn { margin-top: 16rpx; border-radius: 12rpx; font-size: 28rpx; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
.ghost { background: #f1f5f9; color: #475569; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 9999; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 70vh; background: #fff; border-radius: 24rpx 24rpx 0 0; padding: 24rpx; }
.sheet-head { margin-bottom: 16rpx; }
.sheet-title { font-size: 32rpx; font-weight: 700; }
.log-body { max-height: 50vh; }
.log-row { padding: 16rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.log-meta { display: block; font-size: 22rpx; color: #94a3b8; }
.log-msg { display: block; font-size: 26rpx; color: #334155; margin-top: 6rpx; }
</style>
