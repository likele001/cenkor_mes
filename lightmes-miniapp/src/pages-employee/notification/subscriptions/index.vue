<template>
  <view class="emp-page">
    <view class="section-head">消息推送订阅</view>
    <view class="emp-card intro-card">
      <text class="intro-title">为什么需要订阅？</text>
      <text class="intro-body">微信小程序推送需要您主动授权。每次订阅后，您可以收到一条相关消息（如工资发放、报工审核完成）。点击下方按钮可随时管理订阅状态。</text>
    </view>

    <!-- 模板未配置提示 -->
    <view v-if="!loading && templates.length && hasPlaceholder" class="emp-card warn-card">
      <text class="warn-icon">⚠</text>
      <text class="warn-text">模板 ID 尚未在后台配置，请联系管理员在「系统设置 → 微信消息推送」中填入真实的微信模板 ID。</text>
    </view>

    <view v-if="loading" class="emp-empty">加载中...</view>
    <view v-else-if="!templates.length" class="emp-empty">
      <text class="empty-icon">📭</text>
      <text class="empty-text">暂无可订阅的推送消息</text>
      <text class="empty-hint">请联系管理员在后台开启微信消息推送</text>
    </view>

    <view v-else>
      <view
        v-for="tpl in templates"
        :key="tpl.event_code"
        class="emp-card tpl-card"
        :class="{ subscribed: isSubscribed(tpl.event_code) }"
      >
        <view class="tpl-head">
          <view class="tpl-icon-wrap">
            <text class="tpl-icon">{{ getEventIcon(tpl.event_code) }}</text>
          </view>
          <view class="tpl-title-area">
            <text class="tpl-name">{{ getEventLabel(tpl.event_code) }}</text>
            <text class="tpl-desc">{{ getEventDesc(tpl.event_code) }}</text>
          </view>
          <text v-if="isSubscribed(tpl.event_code)" class="emp-tag success">已订阅</text>
          <text v-else class="emp-tag info">未订阅</text>
        </view>

        <!-- 订阅统计（有历史记录时显示） -->
        <view v-if="getMyStatus(tpl.event_code)" class="tpl-stats">
          <text class="stat-item">
            已授权 {{ getMyStatus(tpl.event_code)!.accept_count }} 次
          </text>
          <text v-if="getMyStatus(tpl.event_code)!.reject_count" class="stat-item dim">
            · 拒绝 {{ getMyStatus(tpl.event_code)!.reject_count }} 次
          </text>
          <text v-if="getMyStatus(tpl.event_code)!.last_accepted_at" class="stat-item dim">
            · 最近 {{ formatTime(getMyStatus(tpl.event_code)!.last_accepted_at) }}
          </text>
        </view>

        <!-- 推送内容预览 -->
        <view class="keyword-hint" v-if="getKeywordHint(tpl.event_code).length">
          <text class="hint-title">推送内容包含：</text>
          <text v-for="(kw, i) in getKeywordHint(tpl.event_code)" :key="i" class="hint-tag">{{ kw }}</text>
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

      <view class="bulk-action">
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
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { apiGet } from '@/api/request'
import {
  listAvailableTemplates,
  requestSubscribe,
  type WechatTemplate,
} from '@/utils/subscribe'

type MySub = {
  event_code: string
  template_id: string
  accept_count: number
  reject_count: number
  last_accepted_at: string | null
  last_rejected_at: string | null
}

// ---- 事件友好名称 ----
const EVENT_LABELS: Record<string, string> = {
  'report.submitted': '报工提交通知',
  'report.leader_approved': '报工审核结果',
  'report.qc_approved': '质检结果通知',
  'report.rejected': '报工驳回通知',
  'salary.slip_remind': '工资条发放提醒',
  'salary.slip_reset': '工资条重置通知',
  'salary.slip_rejected': '工资条拒签通知',
  'dispatch.assigned': '派工任务通知',
  'order.customer_submitted': '客户订单通知',
  'alert': '系统告警通知',
  'plan.automation_failed': '自动化异常通知',
  'brief.daily': '每日经营简报',
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
  'report.submitted': '📋',
  'report.leader_approved': '✅',
  'report.qc_approved': '🔍',
  'report.rejected': '❌',
  'salary.slip_remind': '💰',
  'salary.slip_reset': '🔄',
  'salary.slip_rejected': '📝',
  'dispatch.assigned': '🔧',
  'order.customer_submitted': '📦',
  'alert': '🚨',
  'plan.automation_failed': '⚙️',
  'brief.daily': '📊',
}

function getEventLabel(code: string): string {
  return EVENT_LABELS[code] || code
}
function getEventDesc(code: string): string {
  return EVENT_DESCS[code] || ''
}
function getEventIcon(code: string): string {
  return EVENT_ICONS[code] || '📩'
}

// ---- 状态 ----
const loading = ref(false)
const templates = ref<WechatTemplate[]>([])
const mySubs = ref<MySub[]>([])
const keywordHints = ref<Record<string, string[]>>({})
const subscribing = ref<string>('')
const bulkLoading = ref(false)

// 检测模板 ID 是否为占位符
const hasPlaceholder = computed(() =>
  templates.value.some((t) => !t.template_id || t.template_id.startsWith('tpl_'))
)

onShow(async () => {
  await load()
})

async function load() {
  loading.value = true
  try {
    const [tpls, mine] = await Promise.all([
      listAvailableTemplates(),
      loadMySubs(),
    ])
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
  } catch (e) {
    console.warn('[subs] loadMySubs failed:', e)
    return []
  }
}

async function loadKeywordHints(): Promise<Record<string, string[]>> {
  try {
    const r = await apiGet<{ keyword_hints: Record<string, string[]> }>('/miniapp/wechat-mp/templates')
    return r?.keyword_hints || {}
  } catch {
    return {}
  }
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
  } catch {
    return s
  }
}

async function onSubscribeOne(tpl: WechatTemplate) {
  if (hasPlaceholder.value) {
    uni.showToast({ title: '模板 ID 未配置，请联系管理员', icon: 'none' })
    return
  }
  subscribing.value = tpl.event_code
  try {
    const r = await requestSubscribe([tpl.template_id], { showToast: true, recordOnServer: true })
    if (r.accepted.length) {
      mySubs.value = await loadMySubs()
    }
  } finally {
    subscribing.value = ''
  }
}

async function onSubscribeAll() {
  if (hasPlaceholder.value) {
    uni.showToast({ title: '模板 ID 未配置，请联系管理员', icon: 'none' })
    return
  }
  const wanted = templates.value
  if (!wanted.length) {
    uni.showToast({ title: '暂无可订阅模板', icon: 'none' })
    return
  }
  bulkLoading.value = true
  try {
    let totalAccepted = 0
    for (let i = 0; i < wanted.length; i += 3) {
      const slice = wanted.slice(i, i + 3)
      const r = await requestSubscribe(
        slice.map((t) => t.template_id),
        { showToast: false, recordOnServer: true }
      )
      totalAccepted += r.accepted.length
    }
    if (totalAccepted > 0) {
      uni.showToast({ title: `已订阅 ${totalAccepted} 个`, icon: 'success' })
      mySubs.value = await loadMySubs()
    } else {
      uni.showToast({ title: '未订阅', icon: 'none' })
    }
  } finally {
    bulkLoading.value = false
  }
}
</script>

<style scoped lang="scss">
.emp-page {
  padding: 24rpx;
  background: linear-gradient(180deg, #f0f4ff, #f5f7fa);
  min-height: 100vh;
}
.section-head {
  font-size: 34rpx;
  font-weight: 700;
  color: #1a1a1a;
  margin: 8rpx 0 24rpx;
}
.emp-card {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 16rpx rgba(0, 0, 0, 0.05);
}
.emp-empty {
  text-align: center;
  padding: 100rpx 0;
  .empty-icon {
    display: block;
    font-size: 60rpx;
    margin-bottom: 16rpx;
  }
  .empty-text {
    display: block;
    font-size: 28rpx;
    color: #666;
  }
  .empty-hint {
    display: block;
    font-size: 24rpx;
    color: #999;
    margin-top: 8rpx;
  }
}
/* 介绍卡 */
.intro-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #333;
  display: block;
  margin-bottom: 8rpx;
}
.intro-body {
  font-size: 26rpx;
  color: #666;
  line-height: 1.6;
  display: block;
}
/* 警告卡 */
.warn-card {
  background: #fff8e1;
  border-left: 6rpx solid #fa8c16;
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
}
.warn-icon {
  font-size: 32rpx;
  flex-shrink: 0;
  margin-top: 2rpx;
}
.warn-text {
  font-size: 26rpx;
  color: #8c5e00;
  line-height: 1.5;
}
/* 模板卡 */
.tpl-card {
  &.subscribed {
    border-left: 6rpx solid #07c160;
  }
}
.tpl-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}
.tpl-icon-wrap {
  width: 72rpx;
  height: 72rpx;
  border-radius: 18rpx;
  background: #f0f4ff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tpl-icon {
  font-size: 36rpx;
}
.tpl-title-area {
  flex: 1;
  min-width: 0;
}
.tpl-name {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #1a1a1a;
}
.tpl-desc {
  display: block;
  font-size: 24rpx;
  color: #999;
  margin-top: 4rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.emp-tag {
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  border-radius: 24rpx;
  flex-shrink: 0;
  &.info {
    background: #fff7e6;
    color: #fa8c16;
  }
  &.success {
    background: #e8f9ed;
    color: #07c160;
  }
}
/* 统计行 */
.tpl-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 4rpx;
  margin-bottom: 16rpx;
  font-size: 24rpx;
}
.stat-item {
  color: #07c160;
  &.dim {
    color: #999;
  }
}
/* 推送字段 */
.keyword-hint {
  background: #f8f9fa;
  border-radius: 12rpx;
  padding: 16rpx;
  margin-bottom: 16rpx;
}
.hint-title {
  display: block;
  font-size: 24rpx;
  color: #999;
  margin-bottom: 8rpx;
}
.hint-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #5b6c7c;
  background: #fff;
  padding: 4rpx 14rpx;
  border-radius: 8rpx;
  margin: 4rpx 8rpx 4rpx 0;
  border: 1rpx solid #eee;
}
/* 按钮 */
.emp-btn-primary {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  border-radius: 12rpx;
  font-size: 28rpx;
  padding: 20rpx 0;
  text-align: center;
  border: none;
  width: 100%;
  &::after { border: none; }
  &[disabled] {
    background: #ccc;
    color: #fff;
  }
}
.subscribe-btn {
  margin-top: 8rpx;
}
.bulk-action {
  margin: 32rpx 0 48rpx;
}
.bulk-btn {
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  font-size: 30rpx;
  font-weight: 600;
  padding: 24rpx 0;
}
</style>
