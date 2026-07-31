<template>
  <view class="emp-page">
    <view class="scan-card" @tap="scan">
      <text class="scan-title">扫码报工</text>
      <text class="scan-hint">对准任务二维码</text>
    </view>

    <view class="emp-card">
      <text class="label">或输入任务码</text>
      <input v-model="taskCode" class="input" placeholder="任务码" />
      <button class="emp-btn-primary" @tap="goManual">确认报工</button>
    </view>

    <view class="link-grid">
      <view class="link-item" @tap="go('/pages-employee/report/manual/index')">主动报工</view>
      <view class="link-item" @tap="go('/pages-employee/report/history/index')">报工记录</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { parseTaskCodeFromScan } from '@/utils/parseTaskCode'

const taskCode = ref('')

async function scan() {
  try {
    const res = await uni.scanCode({ onlyFromCamera: false })
    const code = parseTaskCodeFromScan(res.result)
    if (!code) {
      uni.showToast({ title: '无法识别任务码', icon: 'none' })
      return
    }
    uni.vibrateShort({})
    goReport(code)
  } catch {
    /* cancel */
  }
}

function goManual() {
  const code = taskCode.value.trim()
  if (!code) {
    uni.showToast({ title: '请输入任务码', icon: 'none' })
    return
  }
  goReport(code)
}

function goReport(code: string) {
  uni.navigateTo({ url: `/pages-employee/report/scan/index?task_code=${encodeURIComponent(code)}` })
}

function go(url: string) {
  uni.navigateTo({ url })
}
</script>

<style scoped lang="scss">
.scan-card {
  background: #fff;
  border: 2rpx dashed #93c5fd;
  border-radius: 20rpx;
  padding: 72rpx 24rpx;
  text-align: center;
  margin-bottom: 24rpx;
}
.scan-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #2563eb;
  display: block;
}
.scan-hint {
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #64748b;
}
.label {
  display: block;
  font-size: 26rpx;
  color: #64748b;
  margin-bottom: 12rpx;
}
.input {
  background: #f8fafc;
  padding: 24rpx;
  border-radius: 12rpx;
  margin-bottom: 24rpx;
  border: 1rpx solid #e2e8f0;
}
.link-grid {
  display: flex;
  gap: 16rpx;
  margin-top: 8rpx;
}
.link-item {
  flex: 1;
  text-align: center;
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  font-size: 28rpx;
  color: #2563eb;
  border: 1rpx solid #dbeafe;
}
</style>
