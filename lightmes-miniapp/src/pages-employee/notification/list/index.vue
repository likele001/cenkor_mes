<template>
  <view class="emp-page">
    <view class="emp-card subscribe-entry" @tap="goSubscribe">
      <text class="entry-title">📬 微信消息推送订阅管理</text>
      <text class="entry-hint">管理工资/报工/审核等推送授权（点击消息直接跳到对应页面）</text>
    </view>

    <view v-if="!items.length" class="emp-empty">暂无消息</view>
    <view
      v-for="n in items"
      :key="n.id"
      class="emp-card notice-card"
      hover-class="notice-card-hover"
      @tap="read(n)"
    >
      <view class="notice-head">
        <text class="notice-title" :class="{ unread: !n.is_read }">{{ n.title }}</text>
        <text v-if="!n.is_read" class="emp-tag info">未读</text>
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
  const biz = n.biz_type
  if (biz === 'salary_slip') uni.navigateTo({ url: '/pages-employee/salary/slip/index' })
  else if (biz === 'report') uni.switchTab({ url: '/pages/tabs/emp-tasks/index' })
}

function goSubscribe() {
  uni.navigateTo({ url: '/pages-employee/notification/subscriptions/index' })
}
</script>

<style scoped lang="scss">
.subscribe-entry {
  background: linear-gradient(135deg, #eef2ff, #f0fdf4);
  border-left: 6rpx solid #4f46e5;
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
</style>
