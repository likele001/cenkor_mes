<template>
  <view class="cust-page">
    <view class="cust-card profile">
      <text class="avatar">{{ avatarText }}</text>
      <view>
        <text class="cust-title">{{ auth.userInfo?.full_name || auth.userInfo?.username }}</text>
        <text class="cust-sub">{{ auth.roles.join(' · ') }}</text>
      </view>
    </view>

    <view class="cust-card menu">
      <view class="menu-row" @tap="goNotifications">
        <text>消息中心</text>
        <text v-if="auth.unreadCount > 0" class="badge">{{ auth.unreadCount }}</text>
        <text v-else class="arrow">›</text>
      </view>
      <view class="menu-row" @tap="pickLanguage(() => setNavTitle('customer.nav.profile'))">
        <text>{{ t('common.language') }}</text>
        <text class="arrow">{{ currentLocaleLabel() }} ›</text>
      </view>
      <view class="menu-row" @tap="goTrace">
        <text>{{ t('login.traceQuery') }}</text>
        <text class="arrow">›</text>
      </view>
      <!-- CUSTOMER_CHANNEL_BIND_SLOT: 后续可挂载 ChannelBindCard -->
      <view v-if="auth.canSwitchMode" class="menu-row" @tap="goRoleSelect">
        <text>切换工作模式</text>
        <text class="arrow">›</text>
      </view>
      <view class="menu-row danger" @tap="logout">
        <text>{{ t('layout.logout') }}</text>
      </view>
    </view>

    <CustTabBar :active="2" />
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import CustTabBar from '@/components/customer-ui/CustTabBar.vue'
import { useCustomerLocale } from '@/composables/useCustomerLocale'
import { usePermission } from '@/composables/usePermission'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const { currentLocaleLabel, pickLanguage, setNavTitle } = useCustomerLocale()
const { requireCustomer } = usePermission()

const avatarText = computed(() => {
  const n = auth.userInfo?.full_name || auth.userInfo?.username || 'C'
  return n.slice(0, 1).toUpperCase()
})

function goNotifications() {
  uni.navigateTo({ url: '/pages-customer/notification/list/index' })
}

function goTrace() {
  uni.navigateTo({ url: '/pages/shared/trace/index' })
}

function goRoleSelect() {
  uni.navigateTo({ url: '/pages/shared/role-select/index' })
}

function logout() {
  auth.logout()
}

onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.nav.profile')
  auth.refreshUnread()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.profile {
  display: flex;
  align-items: center;
  gap: 24rpx;
}
.avatar {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  background: #bae6fd;
  color: #0369a1;
  font-size: 40rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.menu-row {
  display: flex;
  justify-content: space-between;
  padding: 28rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
  font-size: 28rpx;
}
.arrow {
  color: #94a3b8;
}
.danger {
  color: #ef4444;
  border-bottom: none;
}
.badge {
  background: #ef4444;
  color: #fff;
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
}
</style>
