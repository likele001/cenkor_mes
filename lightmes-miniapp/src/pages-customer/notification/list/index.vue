<template>
  <view class="cust-page">
    <view class="cust-card subscribe-entry" @tap="goSubscribe">
      <text class="entry-title">📬 微信消息推送订阅管理</text>
      <text class="entry-hint">管理订单进度/发货/对账等推送授权</text>
    </view>

    <view v-if="!items.length" class="cust-empty">暂无消息</view>
      <view
        v-for="n in items"
        :key="n.id"
        class="cust-card notice-card"
        hover-class="notice-card-hover"
        @tap="read(n)"
      >
        <view class="notice-head">
          <text class="notice-title" :class="{ unread: !n.is_read }">{{ n.title }}</text>
          <text v-if="!n.is_read" class="cust-tag info">未读</text>
        </view>
        <text class="notice-body">{{ n.content }}</text>
      </view>

    <CustTabBar :active="2" />
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { getNotifications, markRead } from '@/api/h5/notifications'
import { useAuthStore } from '@/stores/auth'
import CustTabBar from '@/components/customer-ui/CustTabBar.vue'

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
}

function goSubscribe() {
  uni.navigateTo({ url: '/pages-customer/notification/subscriptions/index' })
}
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.subscribe-entry {
  background: linear-gradient(135deg, #eef2ff, #f0fdf4);
  border-left: 6rpx solid #0ea5e9;
}
.entry-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 8rpx;
}
.entry-hint {
  display: block;
  font-size: 24rpx;
  color: #666;
  line-height: 1.6;
}
.notice-card {
  padding: 28rpx;
}
.notice-card-hover {
  opacity: 0.92;
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
  min-width: 0;
  font-size: 30rpx;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
  display: block;
}
.notice-title.unread {
  font-weight: 700;
  color: #0f172a;
}
.notice-body {
  font-size: 26rpx;
  color: #64748b;
  line-height: 1.5;
  display: block;
}
.cust-empty {
  text-align: center;
  padding: 80rpx 0;
  font-size: 28rpx;
  color: #94a3b8;
}
.info {
  background: #fff7e6;
  color: #fa8c16;
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  border-radius: 24rpx;
}
</style>
