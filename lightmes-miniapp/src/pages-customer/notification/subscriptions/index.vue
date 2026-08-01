<template>
  <view class="cust-page">
    <view class="cust-page-head"><text class="cust-page-title">消息订阅</text></view>

    <view class="cust-card intro-card">
      <view class="intro-icon">💡</view>
      <view class="intro-body">
        <text class="intro-title">为什么需要订阅？</text>
        <text class="intro-text">微信小程序推送需要您主动授权。每次订阅后可收到一条相关消息（如订单进度、发货通知）。</text>
      </view>
    </view>

    <view v-if="loading" class="cust-empty">加载中...</view>
    <view v-else-if="!templates.length" class="cust-empty">暂无可订阅的模板（请联系管理员配置）</view>

    <view v-else>
      <view v-for="tpl in templates" :key="tpl.event_code" class="cust-card cust-card--striped tappable" :class="isSubscribed(tpl.event_code) ? 'strip-done' : 'strip-info'">
        <view class="tpl-head">
          <text class="tpl-name">{{ tpl.name }}</text>
          <text v-if="isSubscribed(tpl.event_code)" class="cust-tag ok">已订阅</text>
          <text v-else class="cust-tag muted">未订阅</text>
        </view>
        <view class="tpl-meta">
          <text class="meta-line">事件：{{ tpl.event_code }}</text>
          <text class="meta-line">点击消息跳转：{{ tpl.page || '默认首页' }}</text>
          <text v-if="getMyStatus(tpl.event_code)" class="meta-line ok-line">
            历史：同意 {{ getMyStatus(tpl.event_code)!.accept_count }} 次 · 拒绝 {{ getMyStatus(tpl.event_code)!.reject_count }} 次
          </text>
        </view>
        <button class="cust-btn-primary" :loading="subscribing === tpl.event_code" @tap="onSubscribeOne(tpl)">
          {{ isSubscribed(tpl.event_code) ? '再次订阅' : '立即订阅' }}
        </button>
      </view>

      <button class="cust-btn-primary bulk-btn" :loading="bulkLoading" @tap="onSubscribeAll">
        一键订阅全部
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { apiGet } from '@/api/request'
import { listAvailableTemplates, requestSubscribe, type WechatTemplate } from '@/utils/subscribe'

type MySub = {
  event_code: string; template_id: string; accept_count: number; reject_count: number;
  last_accepted_at: string | null; last_rejected_at: string | null;
}

const loading = ref(false)
const templates = ref<WechatTemplate[]>([])
const mySubs = ref<MySub[]>([])
const subscribing = ref('')
const bulkLoading = ref(false)

onShow(async () => { await load() })

async function load() {
  loading.value = true
  try {
    const [tpls, mine] = await Promise.all([listAvailableTemplates(), loadMySubs()])
    templates.value = tpls
    mySubs.value = mine
  } finally { loading.value = false }
}

async function loadMySubs(): Promise<MySub[]> {
  try {
    const r = await apiGet<{ items: MySub[] }>('/miniapp/wechat-mp/my-subscriptions')
    return r?.items || []
  } catch { return [] }
}

function isSubscribed(eventCode: string): boolean {
  const sub = mySubs.value.find((s) => s.event_code === eventCode)
  if (!sub || (sub.accept_count || 0) <= 0) return false
  if (sub.last_rejected_at && sub.last_rejected_at > (sub.last_accepted_at || '')) {
    return (sub.accept_count || 0) > (sub.reject_count || 0)
  }
  return true
}

function getMyStatus(eventCode: string): MySub | undefined {
  return mySubs.value.find((s) => s.event_code === eventCode)
}

async function onSubscribeOne(tpl: WechatTemplate) {
  subscribing.value = tpl.event_code
  try {
    const r = await requestSubscribe([tpl.template_id], { showToast: true, recordOnServer: true })
    if (r.accepted.length) mySubs.value = await loadMySubs()
  } finally { subscribing.value = '' }
}

async function onSubscribeAll() {
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
    } else { uni.showToast({ title: '未订阅', icon: 'none' }) }
  } finally { bulkLoading.value = false }
}
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.intro-card {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  background: linear-gradient(135deg, #f0f9ff, #f0fdf4);
  border: 1rpx solid rgba(186, 230, 253, 0.5);
}
.intro-icon { font-size: 36rpx; flex-shrink: 0; }
.intro-body { flex: 1; }
.intro-title { display: block; font-size: 28rpx; font-weight: 600; color: #0c4a6e; margin-bottom: 6rpx; }
.intro-text { display: block; font-size: 24rpx; color: #64748b; line-height: 1.6; }

.tpl-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16rpx; }
.tpl-name { font-size: 28rpx; font-weight: 600; color: #0c4a6e; flex: 1; }
.tpl-meta { margin-bottom: 16rpx; }
.meta-line { display: block; font-size: 22rpx; color: #64748b; line-height: 1.7; }
.meta-line.ok-line { color: #15803d; }

.bulk-btn {
  width: 100%;
  margin: 32rpx 0 24rpx;
  background: linear-gradient(135deg, #0ea5e9, #7c3aed);
  box-shadow: 0 4rpx 12rpx rgba(124, 58, 237, 0.22);
}
</style>
