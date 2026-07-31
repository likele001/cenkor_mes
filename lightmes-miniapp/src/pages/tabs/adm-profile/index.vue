<template>
  <view class="adm-page">
    <!-- 头像信息卡 -->
    <view class="adm-card profile-card">
      <view class="profile-row">
        <view class="avatar">{{ avatarText }}</view>
        <view class="profile-info">
          <text class="profile-name">{{ userName }}</text>
          <text class="profile-role">{{ rolesText }}</text>
          <text v-if="auth.userInfo?.is_superuser" class="super-tag">超级管理员</text>
        </view>
      </view>
      <view class="profile-meta">
        <view v-if="auth.userInfo?.phone" class="meta-item">
          <text class="meta-label">手机</text>
          <text class="meta-value">{{ auth.userInfo.phone }}</text>
        </view>
        <view v-if="auth.userInfo?.email" class="meta-item">
          <text class="meta-label">邮箱</text>
          <text class="meta-value">{{ auth.userInfo.email }}</text>
        </view>
      </view>
    </view>

    <!-- 权限概览 -->
    <view class="adm-card overview">
      <view class="overview-title">权限概览</view>
      <view class="adm-stat-grid">
        <view class="stat-item">
          <view class="stat-val">{{ auth.permissions.length }}</view>
          <view class="stat-lbl">权限点</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ auth.roles.length }}</view>
          <view class="stat-lbl">角色数</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ unread }}</view>
          <view class="stat-lbl">未读消息</view>
        </view>
      </view>
    </view>

    <!-- 功能菜单 -->
    <view class="adm-card menu-card">
      <view class="menu-row" @tap="goAssistant" v-if="auth.hasPermission(PermissionCode.AI_USE)">
        <view class="menu-left">
          <text class="menu-icon">🤖</text>
          <text class="menu-text">工厂助手</text>
        </view>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-row" @tap="goHelp">
        <view class="menu-left">
          <text class="menu-icon">💡</text>
          <text class="menu-text">智能帮助</text>
        </view>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-row" @tap="go('/pages-admin/notification/list/index')">
        <view class="menu-left">
          <text class="menu-icon">🔔</text>
          <text class="menu-text">消息通知</text>
        </view>
        <view class="menu-right">
          <text v-if="unread > 0" class="badge">{{ unread }}</text>
          <text class="menu-arrow">›</text>
        </view>
      </view>
      <view class="menu-row" @tap="go('/pages-employee/notification/subscriptions/index')">
        <view class="menu-left">
          <text class="menu-icon">📬</text>
          <text class="menu-text">消息订阅管理</text>
        </view>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-row" @tap="goAbout">
        <view class="menu-left">
          <text class="menu-icon">ℹ️</text>
          <text class="menu-text">关于 CenkorMES</text>
        </view>
        <text class="menu-arrow">›</text>
      </view>
    </view>

    <!-- 切换/退出 -->
    <view class="adm-card bottom-card">
      <view v-if="auth.canSwitchMode" class="action-btn switch-btn" @tap="switchEmp">
        <text>切换到员工端</text>
        <text class="arrow">→</text>
      </view>
      <view class="action-btn logout-btn" @tap="auth.logout()">
        <text>退出登录</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { PermissionCode } from '@/constants/permissions'
import { switchToEmployeeMode } from '@/utils/navigate'
import { updateTabBarBadge } from '@/mixins/tabBar'

const auth = useAuthStore()
const unread = computed(() => auth.unreadCount)

const userName = computed(() => auth.userInfo?.full_name || auth.userInfo?.username || '管理员')
const avatarText = computed(() => (userName.value.slice(0, 1) || '管').toUpperCase())
const rolesText = computed(() => auth.roles.join(' · ') || '管理员')

onShow(async () => {
  await auth.refreshUnread()
  updateTabBarBadge(auth.unreadCount)
})

function switchEmp() {
  switchToEmployeeMode()
}
function goAbout() {
  uni.navigateTo({ url: '/pages/shared/about/index' })
}
function goHelp() {
  uni.navigateTo({ url: '/pages/shared/help/index' })
}
function goAssistant() {
  uni.navigateTo({ url: '/pages-admin/ai/assistant/index' })
}
function go(url: string) {
  uni.navigateTo({ url })
}
</script>

<style scoped lang="scss">
.profile-card {
  padding: 32rpx;
}
.profile-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
}
.avatar {
  width: 108rpx;
  height: 108rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #4338ca);
  color: #fff;
  font-size: 46rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.profile-info {
  flex: 1;
}
.profile-name {
  display: block;
  font-size: 36rpx;
  font-weight: 700;
  color: #1e293b;
}
.profile-role {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #64748b;
}
.super-tag {
  display: inline-block;
  margin-top: 8rpx;
  font-size: 20rpx;
  color: #fff;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}
.profile-meta {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid #f1f5f9;
  display: flex;
  gap: 32rpx;
}
.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.meta-label {
  font-size: 22rpx;
  color: #94a3b8;
}
.meta-value {
  font-size: 26rpx;
  color: #334155;
}
.overview {
  padding: 24rpx;
}
.overview-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #334155;
  margin-bottom: 16rpx;
}
.adm-stat-grid {
  display: flex;
  gap: 16rpx;
}
.stat-item {
  flex: 1;
  background: #f8fafc;
  border-radius: 16rpx;
  padding: 20rpx 12rpx;
  text-align: center;
}
.stat-val {
  font-size: 36rpx;
  font-weight: 700;
  color: #1e293b;
}
.stat-lbl {
  font-size: 22rpx;
  color: #64748b;
  margin-top: 4rpx;
}
.menu-card {
  padding: 8rpx 0;
}
.menu-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28rpx 32rpx;
  border-bottom: 1rpx solid #f1f5f9;
}
.menu-row:last-child {
  border-bottom: none;
}
.menu-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.menu-icon {
  font-size: 36rpx;
}
.menu-text {
  font-size: 28rpx;
  color: #334155;
}
.menu-arrow {
  font-size: 32rpx;
  color: #cbd5e1;
}
.menu-right {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.badge {
  background: #ef4444;
  color: #fff;
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
}
.bottom-card {
  padding: 16rpx 32rpx;
}
.action-btn {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28rpx 0;
  font-size: 28rpx;
  color: #334155;
  border-bottom: 1rpx solid #f1f5f9;
}
.action-btn:last-child {
  border-bottom: none;
}
.switch-btn {
  color: #2563eb;
}
.logout-btn {
  color: #ef4444;
}
.arrow {
  font-size: 28rpx;
  color: #cbd5e1;
}
</style>
