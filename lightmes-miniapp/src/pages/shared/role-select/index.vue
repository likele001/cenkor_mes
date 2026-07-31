<template>
  <view class="page">
    <text class="title">选择工作模式</text>
    <view v-if="canAccessCustomer" class="card" @tap="goCustomer">
      <text class="name">客户端</text>
      <text class="desc">浏览产品、下单、查进度与对账单</text>
    </view>
    <view v-if="canAccessEmployee" class="card" @tap="goEmployee">
      <text class="name">员工端</text>
      <text class="desc">扫码报工、任务、考勤、工资</text>
    </view>
    <view v-if="canAccessAdmin" class="card" @tap="goAdmin">
      <text class="name">管理端</text>
      <text class="desc">看板、审核、订单、全厂管理</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { switchToAdminMode, switchToCustomerMode, switchToEmployeeMode } from '@/utils/navigate'
import { usePermission } from '@/composables/usePermission'

const { canAccessEmployee, canAccessAdmin, canAccessCustomer } = usePermission()

function goEmployee() {
  if (!canAccessEmployee.value) {
    uni.showToast({ title: '无员工端权限', icon: 'none' })
    return
  }
  switchToEmployeeMode()
}
function goAdmin() {
  if (!canAccessAdmin.value) {
    uni.showToast({ title: '无管理端权限', icon: 'none' })
    return
  }
  switchToAdminMode()
}
function goCustomer() {
  if (!canAccessCustomer.value) {
    uni.showToast({ title: '无客户端权限', icon: 'none' })
    return
  }
  switchToCustomerMode()
}
</script>

<style scoped lang="scss">
.page {
  padding: 60rpx 40rpx;
}
.title {
  font-size: 40rpx;
  font-weight: 700;
  margin-bottom: 40rpx;
}
.card {
  background: #fff;
  border-radius: 24rpx;
  padding: 40rpx;
  margin-bottom: 24rpx;
}
.name {
  font-size: 34rpx;
  font-weight: 600;
  display: block;
}
.desc {
  font-size: 26rpx;
  color: #64748b;
  margin-top: 8rpx;
}
</style>
