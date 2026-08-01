<template>
  <view class="emp-page">
    <view class="emp-page-head">
      <text class="emp-page-title">消息订阅</text>
    </view>

    <!-- 介绍卡 -->
    <view class="emp-card intro-card">
      <view class="intro-icon">💡</view>
      <view class="intro-body">
        <text class="intro-title">为什么需要订阅？</text>
        <text class="intro-text">微信小程序推送需要您主动授权。每次订阅后可收到一条相关消息（如工资发放、报工审核完成）。</text>
      </view>
    </view>

    <!-- 占位符警告 -->
    <view v-if="!loading && templates.length && hasPlaceholder" class="emp-card warn-card">
      <view class="warn-icon">⚠</view>
      <view class="warn-body">
        <text class="warn-title">模板 ID 未配置</text>
        <text class="warn-text">请联系管理员在「系统设置 → 微信消息推送」中填入真实的微信模板 ID。</text>
      </view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="emp-empty">
      <text class="emp-empty-icon">◌</text>
      加载中...
    </view>

    <!-- 空状态 -->
    <view v-else-if="!templates.length" class="emp-empty">
      <text class="emp-empty-icon">📭</text>
      暂无可订阅的推送消息
      <text class="empty-hint">请联系管理员在后台开启微信消息推送</text>
    </view>

    <!-- 模板列表 -->
    <view v-else>
      <view
        v-for="tpl in templates"
        :key="tpl.event_code"
        class="emp-card emp-card--striped tpl-card tappable"
        :class="isSubscribed(tpl.event_code) ? 'strip-done' : 'strip-info'"
      >
        <view class="tpl-head">
          <view class="tpl-icon-wrap" :class="getEventTone(tpl.event_code)">
            <text class="tpl-icon">{{ getEventIcon(tpl.event_code) }}</text>
          </view>
          <view class="tpl-title-area">
            <text class="tpl-name">{{ getEventLabel(tpl.event_code) }}</text>
            <text class="tpl-desc">{{ getEventDesc(tpl.event_code) }}</text>
          </view>
          <text v-if="isSubscribed(tpl.event_code)" class="emp-tag ok">已订阅</text>
          <text v-else class="emp-tag muted">未订阅</text>
        </view>

        <!-- 订阅统计 -->
        <view v-if="getMyStatus(tpl.event_code)" class="tpl-stats">
          <text class="stat-item ok">已授权 {{ getMyStatus(tpl.event_code)!.accept_count }} 次</text>
          <text v-if="getMyStatus(tpl.event_code)!.reject_count" class="stat-item dim">· 拒绝 {{ getMyStatus(tpl.event_code)!.reject_count }} 次</text>
          <text v-if="getMyStatus(tpl.event_code)!.last_accepted_at" class="stat-item dim">· 最近 {{ formatTime(getMyStatus(tpl.event_code)!.last_accepted_at) }}</text>
        </view>

        <!-- 推送字段 -->
        <view v-if="getKeywordHint(tpl.event_code).length" class="keyword-hint">
          <text class="hint-title">推送内容包含：</text>
          <view class="hint-tags">
            <text v-for="(kw, i) in getKeywordHint(tpl.event_code)" :key="i" class="hint-tag">{{ kw }}</text>
          </view>
        </view>

        <button
          class="emp-btn-primary subscribe-btn"
          :loading="subscribing === tpl.event_code"
          :disabled="hasPlaceholder"
          @tap="onSubscribeOne(tpl)"
        >
          {{ isSubscribed(tpl.event_code) ? '再次订阅' : '立即订阅' }}
        </button>
      </view>

      <button
        class="emp-btn-primary bulk-btn"
        :loading="bulkLoading"
        :disabled="hasPlaceholder"
        @tap="onSubscribeAll"
      >
        一键订阅全部
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { apiGet } from '@/api/request'
import { listAvailableTemplates, requestSubscribe, type WechatTemplate } from '@/utils/subscribe'

type MySub = {
  event_code: string; template_id: string; accept_count: number; reject_count: number;
  last_accepted_at: string | null; last_rejected_at: string | null;
}

const EVENT_LABELS: Record<string, string> = {
  'report.submitted': '报工提交通知', 'report.leader_approved': '报工审核结果',
  'report.qc_approved': '质检结果通知', 'report.rejected': '报工驳回通知',
  'salary.slip_remind': '工资条发放提醒', 'salary.slip_reset': '工资条重置通知',
  'salary.slip_rejected': '工资条拒签通知', 'dispatch.assigned': '派工任务通知',
  'order.customer_submitted': '客户订单通知', 'alert': '系统告警通知',
  'plan.automation_failed': '自动化异常通知', 'brief.daily': '每日经营简报',
}
const EVENT_DESCS: Record<string, string> = {
  'report.submitted': '提交报工单后，通知审核人',
  'report.leader_approved': '主管审核通过或驳回时通知您',
  'report.qc_approved': '质检完成后通知相关人员',
  'report.rejected': '报工被驳回时通知您修改',
  'salary.slip_remind': '每月工资条发放后提醒您查看',
  'salary.slip_reset': '工资条被重置时通知您',
  'salary.slip_rejected': '员工拒签工资条时通知管理员',
  'dispatch.assigned': '有新派工任务时通知您',
  'order.customer_submitted': '客户提交新订单时通知',
  'alert': '系统异常或设备告警时通知',
  'plan.automation_failed': '自动化任务执行失败时通知',
  'brief.daily': '每日自动推送经营数据摘要',
}
const EVENT_ICONS: Record<string, string> = {
  'report.submitted': '📋', 'report.leader_approved': '✅', 'report.qc_approved': '🔍',
  'report.rejected': '❌', 'salary.slip_remind': '💰', 'salary.slip_reset': '🔄',
  'salary.slip_rejected': '📝', 'dispatch.assigned': '🔧', 'order.customer_submitted': '📦',
  'alert': '🚨', 'plan.automation_failed': '⚙️', 'brief.daily': '📊',
}

function getEventLabel(code: string) { return EVENT_LABELS[code] || code }
function getEventDesc(code: string) { return EVENT_DESCS[code] || '' }
function getEventIcon(code: string) { return EVENT_ICONS[code] || '📩' }
function getEventTone(code: string) {
  if (code.startsWith('salary')) return 'tone-amber'
  if (code.startsWith('report')) return 'tone-blue'
  if (code === 'alert' || code === 'plan.automation_failed') return 'tone-rose'
  if (code === 'brief.daily') return 'tone-violet'
  return 'tone-slate'
}

const loading = ref(false)
const templates = ref<WechatTemplate[]>([])
const mySubs = ref<MySub[]>([])
const keywordHints = ref<Record<string, string[]>>({})
const subscribing = ref('')
const bulkLoading = ref(false)

const hasPlaceholder = computed(() =>
  templates.value.some((t) => !t.template_id || t.template_id.startsWith('tpl_'))
)

onShow(async () => { await load() })

async function load() {
  loading.value = true
  try {
    const [tpls, mine] = await Promise.all([listAvailableTemplates(), loadMySubs()])
    templates.value = tpls
    mySubs.value = mine
    keywordHints.value = tpls.length ? await loadKeywordHints() : {}
  } finally {
    loading.value = false
  }
}

async function loadMySubs(): Promise<MySub[]> {
  try {
    const r = await apiGet<{ items: MySub[] }>('/miniapp/wechat-mp/my-subscriptions')
    return r?.items || []
  } catch { return [] }
}

async function loadKeywordHints(): Promise<Record<string, string[]>> {
  try {
    const r = await apiGet<{ keyword_hints: Record<string, string[]> }>('/miniapp/wechat-mp/templates')
    return r?.keyword_hints || {}
  } catch { return {} }
}

function isSubscribed(eventCode: string): boolean {
  const sub = mySubs.value.find((s) => s.event_code === eventCode)
  if (!sub) return false
  if ((sub.accept_count || 0) <= 0) return false
  if (sub.last_rejected_at && sub.last_rejected_at > (sub.last_accepted_at || '')) {
    return (sub.accept_count || 0) > (sub.reject_count || 0)
  }
  return true
}

function getMyStatus(eventCode: string): MySub | undefined {
  return mySubs.value.find((s) => s.event_code === eventCode)
}

function getKeywordHint(eventCode: string): string[] {
  return keywordHints.value[eventCode] || []
}

function formatTime(s: string | null): string {
  if (!s) return ''
  try {
    const d = new Date(s)
    return `${d.getMonth() + 1}/${d.getDate()}`
  } catch { return s }
}

async function onSubscribeOne(tpl: WechatTemplate) {
  if (hasPlaceholder.value) { uni.showToast({ title: '模板 ID 未配置，请联系管理员', icon: 'none' }); return }
  subscribing.value = tpl.event_code
  try {
    const r = await requestSubscribe([tpl.template_id], { showToast: true, recordOnServer: true })
    if (r.accepted.length) mySubs.value = await loadMySubs()
  } finally { subscribing.value = '' }
}

async function onSubscribeAll() {
  if (hasPlaceholder.value) { uni.showToast({ title: '模板 ID 未配置，请联系管理员', icon: 'none' }); return }
  const wanted = templates.value
  if (!wanted.length) { uni.showToast({ title: '暂无可订阅模板', icon: 'none' }); return }
  bulkLoading.value = true
  try {
    let totalAccepted = 0
    for (let i = 0; i < wanted.length; i += 3) {
      const slice = wanted.slice(i, i + 3)
      const r = await requestSubscribe(slice.map((t) => t.template_id), { showToast: false, recordOnServer: true })
      totalAccepted += r.accepted.length
    }
    if (totalAccepted > 0) {
      uni.showToast({ title: `已订阅 ${totalAccepted} 个`, icon: 'success' })
      mySubs.value = await loadMySubs()
    } else {
      uni.showToast({ title: '未订阅', icon: 'none' })
    }
  } finally { bulkLoading.value = false }
}
</script>

<style scoped lang="scss">
// 介绍卡
.intro-card {
  display: flex;
  align-items: flex-start;
  gap: $space-4;
  background: linear-gradient(135deg, $brand-50, #f0fdf4);
  border: 1rpx solid rgba($brand-200, 0.4);
}
.intro-icon {
  font-size: 40rpx;
  flex-shrink: 0;
}
.intro-body { flex: 1; }
.intro-title {
  display: block;
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-800;
  margin-bottom: 6rpx;
}
.intro-text {
  font-size: $text-sm;
  color: $slate-600;
  line-height: 1.6;
  display: block;
}

// 警告卡
.warn-card {
  display: flex;
  align-items: flex-start;
  gap: $space-3;
  background: $warn-bg;
  border: 1rpx solid rgba($warn, 0.3);
}
.warn-icon {
  font-size: 32rpx;
  flex-shrink: 0;
}
.warn-body { flex: 1; }
.warn-title {
  display: block;
  font-size: $text-sm;
  font-weight: $fw-semibold;
  color: $warn-deep;
  margin-bottom: 4rpx;
}
.warn-text {
  font-size: $text-xs;
  color: $warn-deep;
  line-height: 1.5;
  display: block;
}

// 空状态
.empty-hint {
  display: block;
  margin-top: $space-1;
  font-size: $text-xs;
  color: $slate-400;
}

// 模板卡
.tpl-card {
  padding: $space-5;
  padding-left: 32rpx;
}
.tpl-head {
  display: flex;
  align-items: center;
  gap: $space-3;
  margin-bottom: $space-3;
}
.tpl-icon-wrap {
  width: 72rpx;
  height: 72rpx;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tpl-icon { font-size: 32rpx; }
.tone-blue    { background: $brand-50; }
.tone-amber   { background: $warn-bg; }
.tone-rose    { background: $danger-bg; }
.tone-violet  { background: #ede9fe; }
.tone-slate   { background: $slate-100; }

.tpl-title-area { flex: 1; min-width: 0; }
.tpl-name {
  display: block;
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-800;
}
.tpl-desc {
  display: block;
  font-size: $text-xs;
  color: $slate-500;
  margin-top: 4rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// 统计
.tpl-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 4rpx;
  margin-bottom: $space-3;
  font-size: $text-xs;
}
.stat-item { color: $success-deep; }
.stat-item.dim { color: $slate-400; }

// 推送字段
.keyword-hint {
  background: $slate-50;
  border-radius: $radius-md;
  padding: $space-3 $space-4;
  margin-bottom: $space-3;
}
.hint-title {
  display: block;
  font-size: $text-xs;
  color: $slate-500;
  margin-bottom: $space-1;
}
.hint-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6rpx;
}
.hint-tag {
  font-size: $text-xs;
  color: $slate-700;
  background: #fff;
  padding: 4rpx 14rpx;
  border-radius: $radius-sm;
  border: 1rpx solid $slate-200;
}

// 按钮
.subscribe-btn {
  width: 100%;
  margin-top: $space-2;
}
.bulk-btn {
  width: 100%;
  margin: $space-6 0 $space-7;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  box-shadow: 0 4rpx 12rpx rgba(79, 70, 229, 0.22);
  font-weight: $fw-semibold;
}
</style>
