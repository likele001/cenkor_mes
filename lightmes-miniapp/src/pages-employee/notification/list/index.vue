<template>
  <view class="emp-page">
    <!-- 订阅入口卡 -->
    <view class="emp-card subscribe-entry tappable" @tap="goSubscribe">
      <view class="entry-icon-wrap">
        <view class="entry-icon">📬</view>
      </view>
      <view class="entry-body">
        <text class="entry-title">微信消息推送</text>
        <text class="entry-hint">管理工资/报工/审核推送授权，点击消息直接跳转对应页面</text>
      </view>
      <text class="entry-arrow">›</text>
    </view>

    <!-- 消息列表 -->
    <view v-if="!items.length" class="emp-empty">
      <text class="emp-empty-icon">🔕</text>
      暂无消息
    </view>

    <view
      v-for="n in items"
      :key="n.id"
      class="emp-card emp-card--striped notice-card tappable"
      :class="n.is_read ? 'strip-info' : 'strip-working'"
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
  n.is_read = true
  auth.refreshUnread()
  const biz = n.biz_type
  if (biz === 'salary_slip') uni.navigateTo({ url: '/pages-employee/salary/slip/index' })
  else if (biz === 'report') uni.switchTab({ url: '/pages/tabs/emp-tasks/index' })
}

function goSubscribe() {
  uni.navigateTo({ url: '/pages-employee/notification/subscriptions/index' })
}
</script>

<style scoped lang="scss">
// 订阅入口
.subscribe-entry {
  display: flex;
  align-items: center;
  gap: $space-4;
  background: linear-gradient(135deg, #eef2ff, #f0fdf4);
  border: 1rpx solid rgba($brand-200, 0.4);
}
.entry-icon-wrap {
  flex-shrink: 0;
}
.entry-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: $radius-md;
  background: rgba($brand-600, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
}
.entry-body {
  flex: 1;
  min-width: 0;
}
.entry-title {
  display: block;
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-800;
  margin-bottom: 4rpx;
}
.entry-hint {
  display: block;
  font-size: $text-xs;
  color: $slate-500;
  line-height: 1.5;
}
.entry-arrow {
  color: $slate-300;
  font-size: $text-xl;
  flex-shrink: 0;
}

// 消息卡
.notice-card {
  padding: $space-5;
  padding-left: 32rpx;
}
.notice-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: $space-3;
  margin-bottom: $space-2;
}
.notice-title {
  flex: 1;
  min-width: 0;
  font-size: $text-md;
  font-weight: $fw-medium;
  color: $slate-700;
  line-height: 1.4;
  display: block;
}
.notice-title.unread {
  font-weight: $fw-bold;
  color: $slate-900;
}
.notice-body {
  font-size: $text-sm;
  color: $slate-500;
  line-height: 1.5;
  display: block;
}
</style>
