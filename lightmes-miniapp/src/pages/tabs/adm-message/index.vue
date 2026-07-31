<template>
  <view class="adm-page">
    <view class="adm-hero">
      <text class="adm-hero-title">消息中心</text>
      <text class="adm-hero-sub">系统通知与待办提醒</text>
    </view>

    <view class="adm-audit-card" @tap="go">
      <view class="adm-audit-icon blue">🔔</view>
      <view class="adm-audit-body">
        <text class="adm-audit-title">全部消息</text>
        <text class="adm-audit-desc">未读 {{ auth.unreadCount }} 条</text>
      </view>
      <text class="adm-list-arrow">›</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { updateTabBarBadge } from '@/mixins/tabBar'

const auth = useAuthStore()

onShow(async () => {
  await auth.refreshUnread()
  updateTabBarBadge(auth.unreadCount)
})

function go() {
  uni.navigateTo({ url: '/pages-admin/notification/list/index' })
}
</script>

<style scoped>
.adm-audit-icon.blue { background: #eff6ff; }
</style>
