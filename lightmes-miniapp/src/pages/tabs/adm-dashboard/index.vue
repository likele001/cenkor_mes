<template>
  <view class="adm-page">
    <view class="adm-hero">
      <text class="adm-hero-title">生产总览</text>
      <text class="adm-hero-sub">关键指标与快捷入口 · 与 PC 管理端一致</text>
      <view class="adm-hero-meta">
        <text>{{ userName }}</text>
        <text>{{ today }}</text>
      </view>
    </view>

    <view v-if="!canDashboard" class="adm-card">
      <text class="adm-empty-tip">当前账号无 dashboard.view 权限，无法查看指标</text>
    </view>

    <view v-else-if="loading" class="adm-empty-tip">加载中...</view>

    <view v-else class="adm-stat-grid">
      <view class="adm-stat-card tone-green">
        <text class="adm-stat-label">今日合格数</text>
        <text class="adm-stat-value">{{ summary.today?.good_qty ?? '-' }}</text>
      </view>
      <view class="adm-stat-card tone-rose">
        <text class="adm-stat-label">今日不良数</text>
        <text class="adm-stat-value">{{ summary.today?.bad_qty ?? '-' }}</text>
      </view>
      <view class="adm-stat-card tone-blue">
        <text class="adm-stat-label">今日良率</text>
        <text class="adm-stat-value">{{ formatPercent(summary.today?.yield_rate) }}</text>
      </view>
      <view class="adm-stat-card tone-orange">
        <text class="adm-stat-label">今日工资</text>
        <text class="adm-stat-value">¥{{ formatMoney(summary.today?.salary_amount) }}</text>
      </view>
      <view class="adm-stat-card tone-violet">
        <text class="adm-stat-label">待审核报工</text>
        <text class="adm-stat-value">{{ summary.reports?.pending_audit ?? '-' }}</text>
      </view>
      <view class="adm-stat-card tone-blue">
        <text class="adm-stat-label">订单 总/已确认</text>
        <text class="adm-stat-value">{{ summary.orders?.total ?? '-' }}/{{ summary.orders?.confirmed ?? '-' }}</text>
      </view>
      <view class="adm-stat-card tone-green">
        <text class="adm-stat-label">任务 待开始/完成</text>
        <text class="adm-stat-value">{{ summary.tasks?.pending ?? '-' }}/{{ summary.tasks?.done ?? '-' }}</text>
      </view>
      <view class="adm-stat-card tone-violet">
        <text class="adm-stat-label">今日报工次数</text>
        <text class="adm-stat-value">{{ summary.today?.report_count ?? '-' }}</text>
      </view>
    </view>

    <!-- 自动化运行状态卡片 -->
    <view v-if="autoStatus.visible" class="adm-card auto-card" @tap="goAutoSettings">
      <view class="auto-head">
        <text class="auto-title">🤖 自动化运行状态</text>
        <text class="auto-arrow">设置 ›</text>
      </view>
      <view class="auto-row">
        <text class="auto-label">总开关</text>
        <text class="auto-val" :class="autoStatus.enabled ? 'green' : 'muted'">
          {{ autoStatus.enabled ? '✅ 已开启' : '❌ 已关闭' }}
        </text>
      </view>
      <view v-if="autoStatus.lastLog" class="auto-row">
        <text class="auto-label">上次流水线执行</text>
        <text class="auto-val" :class="statusTone(autoStatus.lastLog.status)">
          {{ statusLabel(autoStatus.lastLog) }}
        </text>
      </view>
    </view>

    <view v-if="canAi && briefContent" class="adm-card brief-card">
      <view class="brief-head">
        <text class="brief-title">今日简报</text>
        <text class="brief-mode">{{ briefMode === 'llm' ? 'AI 生成' : '规则汇总' }}</text>
      </view>
      <text class="brief-text">{{ briefContent }}</text>
    </view>
    <view v-else-if="canAi && briefLoading" class="adm-card">
      <text class="adm-empty-tip">简报加载中...</text>
    </view>

    <view v-if="canAiAlert && aiAlerts.length" class="adm-card ai-alerts">
      <view class="ai-head">
        <text class="ai-title">AI 数据预警</text>
        <view class="ai-actions">
          <text v-if="canAi" class="ai-link" @tap="runAlertScan">扫描</text>
          <text v-if="canAiSettings" class="ai-link" @tap="openSettings">阈值</text>
        </view>
      </view>
      <view v-for="a in aiAlerts" :key="a.id" class="ai-item" @tap="toggleAlert(a.id)">
        <text class="ai-tag" :class="a.level">{{ a.level === 'danger' ? '严重' : '预警' }}</text>
        <text class="ai-item-title">{{ a.title }}</text>
        <text v-if="expandedAlert === a.id && a.summary" class="ai-summary">{{ a.summary }}</text>
      </view>
    </view>

    <AdminMenuSection
      v-if="shortcuts.length"
      title="快捷入口"
      subtitle="工厂助手 · 智能帮助 · 产能等与 PC 首页一致"
      :items="shortcuts"
      compact
      @navigate="navigate"
    />

    <view v-if="auth.canSwitchMode" class="adm-link" @tap="switchEmp">切换到员工端</view>

    <view v-if="settingsVisible" class="mask" @tap="settingsVisible = false">
      <view class="sheet" @tap.stop>
        <view class="sheet-head"><text class="sheet-title">AI 预警阈值</text></view>
        <view class="field">
          <text class="label">待审报工阈值</text>
          <input v-model.number="alertSettings.pending_audit" type="number" class="input" />
        </view>
        <view class="field">
          <text class="label">良率下降幅度</text>
          <input v-model.number="alertSettings.yield_drop_delta" type="digit" class="input" />
        </view>
        <view class="field">
          <text class="label">在制任务阈值</text>
          <input v-model.number="alertSettings.pending_tasks" type="number" class="input" />
        </view>
        <view class="sheet-foot">
          <button class="btn ghost" @tap="settingsVisible = false">取消</button>
          <button class="btn primary" :loading="settingsSaving" @tap="saveSettings">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, reactive, ref } from 'vue'
import { adminApi } from '@/api/admin/index'
import { aiAdminApi, type AlertItem, type AlertSettingsOut } from '@/api/admin/ai'
import { automationAdminApi, type AutomationLogOut, type AutomationSettings } from '@/api/admin/automation'
import AdminMenuSection from '@/components/admin-ui/AdminMenuSection.vue'
import { useAdminMenu } from '@/constants/adminMenu'
import { useAuthStore } from '@/stores/auth'
import { PermissionCode } from '@/constants/permissions'
import { switchToEmployeeMode } from '@/utils/navigate'
import { formatMoney, formatPercent } from '@/utils/format'

type Summary = {
  today?: { good_qty?: number; bad_qty?: number; yield_rate?: number; salary_amount?: number; report_count?: number }
  orders?: { total?: number; confirmed?: number }
  tasks?: { pending?: number; done?: number }
  reports?: { pending_audit?: number }
}

const auth = useAuthStore()
const { shortcuts, canDashboard, navigate } = useAdminMenu()
const loading = ref(false)
const summary = reactive<Summary>({})
const aiAlerts = ref<AlertItem[]>([])
const expandedAlert = ref<number | null>(null)
const briefLoading = ref(false)
const briefContent = ref('')
const briefMode = ref('rule')
const settingsVisible = ref(false)
const settingsSaving = ref(false)
const alertSettings = reactive<AlertSettingsOut>({
  pending_audit: 50,
  yield_drop_delta: 0.05,
  pending_tasks: 30,
  unassigned_sample_min: 3,
})

const canSettings = computed(() => auth.hasPermission(PermissionCode.SETTING_MANAGE))

const autoStatus = reactive({
  visible: false,
  enabled: false,
  lastLog: null as AutomationLogOut | null,
})

const canAiAlert = computed(() => auth.hasPermission(PermissionCode.AI_ALERT_VIEW))
const canAi = computed(() => auth.hasPermission(PermissionCode.AI_USE))
const canAiSettings = computed(
  () => auth.hasPermission(PermissionCode.AI_USE) && auth.hasPermission(PermissionCode.SETTING_MANAGE),
)

const userName = computed(() => auth.userInfo?.full_name || auth.userInfo?.username || '管理员')
const today = computed(() => new Date().toLocaleDateString('zh-CN'))

function statusLabel(log: AutomationLogOut): string {
  const s = log.status === 'success' ? '✅ 成功' : log.status === 'failed' ? '❌ 失败' : '⏭️ 跳过'
  const t = log.created_at ? log.created_at.slice(0, 16).replace('T', ' ') : ''
  return `${s} · ${t}`
}

function statusTone(s: string): string {
  if (s === 'success') return 'green'
  if (s === 'failed') return 'rose'
  return 'muted'
}

function goAutoSettings() {
  uni.navigateTo({ url: '/pages-admin/system/automation/index' })
}

onShow(() => load())

async function load() {
  if (!canDashboard.value) return
  loading.value = true
  try {
    const d = (await adminApi.dashboardSummary()) as Summary
    Object.assign(summary, d)
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
  if (canAiAlert.value) {
    try {
      const res = await aiAdminApi.listAlerts()
      aiAlerts.value = (res.items || []).slice(0, 5)
    } catch {
      aiAlerts.value = []
    }
  }
  if (canAi.value) {
    briefLoading.value = true
    try {
      const b = await aiAdminApi.getAiBrief()
      briefContent.value = b.content || ''
      briefMode.value = b.mode || 'rule'
    } catch {
      briefContent.value = ''
    } finally {
      briefLoading.value = false
    }
  }
  // 自动化运行状态
  if (canSettings.value) {
    try {
      const [settings, logs] = await Promise.all([
        automationAdminApi.getSettings(),
        automationAdminApi.listLogs({ limit: 1 }),
      ])
      autoStatus.enabled = settings?.enabled ?? false
      autoStatus.lastLog = (logs?.items || [])[0] ?? null
      autoStatus.visible = true
    } catch {
      autoStatus.visible = false
    }
  }
}

function toggleAlert(id: number) {
  expandedAlert.value = expandedAlert.value === id ? null : id
}

async function openSettings() {
  settingsVisible.value = true
  try {
    const s = await aiAdminApi.getAlertSettings()
    Object.assign(alertSettings, s)
  } catch {
    /* 默认 */
  }
}

async function saveSettings() {
  settingsSaving.value = true
  try {
    const s = await aiAdminApi.saveAlertSettings({ ...alertSettings })
    Object.assign(alertSettings, s)
    uni.showToast({ title: '已保存', icon: 'success' })
    settingsVisible.value = false
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    settingsSaving.value = false
  }
}

async function runAlertScan() {
  try {
    const res = await aiAdminApi.runAlerts()
    uni.showToast({
      title: `扫描 ${res.events ?? 0} 条`,
      icon: 'none',
    })
    const list = await aiAdminApi.listAlerts()
    aiAlerts.value = (list.items || []).slice(0, 5)
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '扫描失败', icon: 'none' })
  }
}

function switchEmp() {
  switchToEmployeeMode()
}
</script>

<style scoped lang="scss">
.auto-card { margin-top: 24rpx; padding: 24rpx; }
.auto-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16rpx; }
.auto-title { font-size: 28rpx; font-weight: 600; color: #1e293b; }
.auto-arrow { font-size: 24rpx; color: #6366f1; }
.auto-row { display: flex; justify-content: space-between; align-items: center; padding: 10rpx 0; }
.auto-label { font-size: 26rpx; color: #64748b; }
.auto-val { font-size: 26rpx; font-weight: 500; }
.auto-val.green { color: #15803d; }
.auto-val.rose { color: #b91c1c; }
.auto-val.muted { color: #94a3b8; }
.brief-card { margin-top: 24rpx; padding: 24rpx; }
.brief-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12rpx; }
.brief-title { font-size: 28rpx; font-weight: 600; color: #1e293b; }
.brief-mode { font-size: 22rpx; color: #94a3b8; }
.brief-text { font-size: 26rpx; color: #475569; line-height: 1.6; white-space: pre-wrap; }
.ai-alerts { margin-top: 24rpx; padding: 24rpx; }
.ai-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16rpx; }
.ai-title { font-size: 28rpx; font-weight: 600; color: #1e293b; }
.ai-actions { display: flex; gap: 24rpx; }
.ai-link { font-size: 24rpx; color: #4338ca; }
.ai-item { padding: 16rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.ai-tag { font-size: 20rpx; padding: 4rpx 10rpx; border-radius: 8rpx; margin-right: 12rpx; }
.ai-tag.warning { background: #fef3c7; color: #b45309; }
.ai-tag.danger { background: #fee2e2; color: #b91c1c; }
.ai-item-title { font-size: 26rpx; color: #334155; }
.ai-summary { display: block; font-size: 24rpx; color: #64748b; margin-top: 8rpx; line-height: 1.5; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 9999; display: flex; align-items: flex-end; }
.sheet { width: 100%; background: #fff; border-radius: 24rpx 24rpx 0 0; padding: 24rpx 32rpx calc(24rpx + env(safe-area-inset-bottom)); }
.sheet-head { margin-bottom: 24rpx; }
.sheet-title { font-size: 32rpx; font-weight: 700; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #64748b; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 16rpx; font-size: 28rpx; }
.sheet-foot { display: flex; gap: 16rpx; margin-top: 24rpx; }
.btn { flex: 1; border-radius: 12rpx; font-size: 28rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
</style>
