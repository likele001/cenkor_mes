<template>
  <view class="emp-page">
    <input v-model="code" class="input" placeholder="输入任务码" />
    <button class="emp-btn-primary" @tap="go">进入逐件报工</button>
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

<style scoped>
.input {
  background: #f1f5f9;
  padding: 24rpx;
  border-radius: 12rpx;
  margin-bottom: 24rpx;
}
</style>
