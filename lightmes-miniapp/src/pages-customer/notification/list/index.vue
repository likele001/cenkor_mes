<template>
  <view class="cust-page">
    <view class="cust-card tappable subscribe-entry" @tap="goSubscribe">
      <view class="entry-icon">📬</view>
      <view class="entry-body">
        <text class="entry-title">微信消息推送</text>
        <text class="entry-hint">管理订单进度/发货/对账等推送授权</text>
      </view>
      <text class="entry-arrow">›</text>
    </view>

    <view v-if="!items.length" class="cust-empty">暂无消息</view>
    <view v-for="n in items" :key="n.id" class="cust-card cust-card--striped tappable" :class="n.is_read ? 'strip-info' : 'strip-working'" @tap="read(n)">
      <view class="notice-head">
        <text class="notice-title" :class="{ unread: !n.is_read }">{{ n.title }}</text>
        <text v-if="!n.is_read" class="cust-tag info">未读</text>
      </view>
      <text class="notice-body">{{ n.content }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { getNotifications, markRead } from '@/api/h5/notifications'
import { useAuthStore } from '@/stores/auth'

type NoticeItem = { id: number; title: string; content?: string; is_read?: boolean; biz_type?: string }
const items = ref<NoticeItem[]>([])
const auth = useAuthStore()

onShow(async () => {
  const r = await getNotifications({ limit: 50 })
  items.value = (r.items || []) as NoticeItem[]
  auth.refreshUnread()
})

async function read(n: NoticeItem) {
  await markRead(n.id)
  n.is_read = true
  auth.refreshUnread()
}

function goSubscribe() {
  uni.navigateTo({ url: '/pages-customer/notification/subscriptions/index' })
}
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.subscribe-entry {
  display: flex;
  align-items: center;
  gap: 24rpx;
  background: linear-gradient(135deg, #f0f9ff, #f0fdf4);
  border: 1rpx solid rgba(186, 230, 253, 0.6);
}
.entry-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: 16rpx;
  background: rgba(14, 165, 233, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  flex-shrink: 0;
}
.entry-body { flex: 1; min-width: 0; }
.entry-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #0c4a6e;
}
.entry-hint {
  display: block;
  font-size: 22rpx;
  color: #64748b;
  margin-top: 4rpx;
}
.entry-arrow {
  color: #cbd5e1;
  font-size: 34rpx;
  flex-shrink: 0;
}
.notice-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 12rpx;
}
.notice-title {
  flex: 1;
  font-size: 28rpx;
  font-weight: 500;
  color: #334155;
  line-height: 1.4;
}
.notice-title.unread {
  font-weight: 700;
  color: #0c4a6e;
}
.notice-body {
  font-size: 24rpx;
  color: #64748b;
  line-height: 1.5;
}
</style>
