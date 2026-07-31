<template>
  <view class="cust-page">
    <view class="section-head">消息推送订阅</view>
    <view class="cust-card intro-card">
      <text class="intro-title">为什么需要订阅？</text>
      <text class="intro-body">微信小程序推送需要您主动授权。每次订阅后，您可以收到一条相关消息（如订单进度、发货通知）。点击下方按钮可随时管理订阅状态。</text>
    </view>

    <view v-if="loading" class="cust-empty">加载中...</view>
    <view v-else-if="!templates.length" class="cust-empty">
      暂无可订阅的模板（请联系管理员配置）
    </view>

    <view v-else>
      <view
        v-for="tpl in templates"
        :key="tpl.event_code"
        class="cust-card tpl-card"
        :class="{ subscribed: isSubscribed(tpl.event_code) }"
      >
        <view class="tpl-head">
          <text class="tpl-name">{{ tpl.name }}</text>
          <text v-if="isSubscribed(tpl.event_code)" class="cust-tag success">已订阅</text>
          <text v-else class="cust-tag info">未订阅</text>
        </view>

        <view class="tpl-meta">
          <text class="meta-line">事件：{{ tpl.event_code }}</text>
          <text class="meta-line">模板 ID：{{ tpl.template_id }}</text>
          <text class="meta-line">点击消息跳转：{{ tpl.page || '默认首页' }}</text>
          <text v-if="getMyStatus(tpl.event_code)" class="meta-line success-line">
            历史：同意 {{ getMyStatus(tpl.event_code).accept_count }} 次 · 拒绝 {{ getMyStatus(tpl.event_code).reject_count }} 次
          </text>
        </view>

        <button
          class="cust-btn-primary subscribe-btn"
          :loading="subscribing === tpl.event_code"
          @tap="onSubscribeOne(tpl)"
        >
          {{ isSubscribed(tpl.event_code) ? '再次订阅' : '立即订阅' }}
        </button>
      </view>

      <view class="bulk-action">
        <button
          class="cust-btn-primary bulk-btn"
          :loading="bulkLoading"
          @tap="onSubscribeAll"
        >
          一键订阅全部（每次最多 3 个，分批授权）
        </button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { apiGet } from '@/api/request'
import { listAvailableTemplates, requestSubscribe, type WechatTemplate } from '@/utils/subscribe'

type MySub = {
  event_code: string
  template_id: string
  accept_count: number
  reject_count: number
  last_accepted_at: string | null
  last_rejected_at: string | null
}

const loading = ref(false)
const templates = ref<WechatTemplate[]>([])
const mySubs = ref<MySub[]>([])
const subscribing = ref<string>('')
const bulkLoading = ref(false)

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
  } finally {
    loading.value = false
  }
}

async function loadMySubs(): Promise<MySub[]> {
  try {
    const r = await apiGet<{ items: MySub[] }>('/miniapp/wechat-mp/my-subscriptions')
    return r?.items || []
  } catch {
    return []
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

async function onSubscribeOne(tpl: WechatTemplate) {
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
@use '@/styles/customer-theme.scss';
.cust-page {
  padding: 24rpx;
}
.section-head {
  font-size: 32rpx;
  font-weight: 600;
  color: #1a1a1a;
  margin: 8rpx 0 24rpx;
}
.intro-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #1a1a1a;
  display: block;
  margin-bottom: 12rpx;
}
.intro-body {
  font-size: 26rpx;
  color: #666;
  line-height: 1.6;
  display: block;
}
.tpl-card {
  &.subscribed {
    border-left: 6rpx solid #07c160;
  }
}
.tpl-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}
.tpl-name {
  font-size: 30rpx;
  font-weight: 600;
  color: #1a1a1a;
  flex: 1;
}
.cust-tag {
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  border-radius: 24rpx;
  &.info {
    background: #fff7e6;
    color: #fa8c16;
  }
  &.success {
    background: #e8f9ed;
    color: #07c160;
  }
}
.tpl-meta {
  margin-bottom: 16rpx;
}
.meta-line {
  display: block;
  font-size: 24rpx;
  color: #666;
  line-height: 1.7;
  &.success-line {
    color: #07c160;
  }
}
.cust-btn-primary {
  background: #0ea5e9;
  color: #fff;
  border-radius: 12rpx;
  font-size: 28rpx;
  padding: 18rpx 0;
  text-align: center;
  border: none;
  width: 100%;
  &::after { border: none; }
}
.subscribe-btn {
  margin-top: 8rpx;
}
.bulk-action {
  margin: 32rpx 0 24rpx;
}
.bulk-btn {
  background: linear-gradient(135deg, #0ea5e9, #7c3aed);
}
.cust-empty {
  text-align: center;
  padding: 80rpx 0;
  font-size: 28rpx;
  color: #94a3b8;
}
</style>
