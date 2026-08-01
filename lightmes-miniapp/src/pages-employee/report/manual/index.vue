<template>
  <view class="emp-page">
    <view class="emp-page-head">
      <text class="emp-page-title">手动报工</text>
    </view>

    <view class="emp-card">
      <text class="label">输入任务码</text>
      <input v-model="code" class="input" placeholder="请输入任务码" confirm-type="go" @confirm="go" />
      <button class="emp-btn-primary" @tap="go">进入逐件报工</button>
    </view>

    <view class="emp-empty">
      <text class="emp-empty-icon">?</text>
      不知道任务码？请使用「扫码报工」扫描任务二维码
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const code = ref('')

function go() {
  if (!code.value.trim()) {
    uni.showToast({ title: '请输入任务码', icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages-employee/report/unit/index?task_code=${encodeURIComponent(code.value.trim())}` })
}
</script>

<style scoped lang="scss">
.label {
  display: block;
  font-size: $text-sm;
  color: $slate-500;
  margin-bottom: $space-3;
  font-weight: $fw-medium;
}
.input {
  background: $slate-50;
  padding: 22rpx 24rpx;
  border-radius: $radius-md;
  margin-bottom: $space-4;
  border: 1rpx solid $slate-200;
  font-size: $text-md;
  color: $slate-800;
  font-variant-numeric: tabular-nums;
  transition: border-color $dur-fast $ease-smooth;
  &:focus { border-color: $brand-500; }
}
.emp-btn-primary {
  width: 100%;
}
</style>
