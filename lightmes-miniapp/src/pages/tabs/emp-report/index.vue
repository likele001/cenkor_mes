<template>
  <view class="emp-page">
    <view class="emp-page-head">
      <text class="emp-page-title">报工</text>
    </view>

    <!-- 扫码大卡：蓝色渐变 + 大图标 -->
    <view class="scan-hero emp-card--brand" @tap="scan">
      <view class="scan-icon-wrap">
        <view class="scan-icon">⌘</view>
        <view class="scan-corner tl" />
        <view class="scan-corner tr" />
        <view class="scan-corner bl" />
        <view class="scan-corner br" />
      </view>
      <text class="scan-title">扫码报工</text>
      <text class="scan-hint">对准任务二维码即可快速报工</text>
    </view>

    <!-- 输入任务码 -->
    <view class="emp-card">
      <text class="label">或手动输入任务码</text>
      <view class="input-row">
        <input v-model="taskCode" class="input" placeholder="请输入任务码" confirm-type="go" @confirm="goManual" />
        <button class="emp-btn-primary go-btn" @tap="goManual">确认</button>
      </view>
    </view>

    <!-- 快捷链接 -->
    <view class="link-grid">
      <view class="link-item" @tap="go('/pages-employee/report/manual/index')">
        <view class="link-icon icon-amber">手</view>
        <view class="link-body">
          <text class="link-title">主动报工</text>
          <text class="link-sub">手动选择任务报工</text>
        </view>
        <text class="link-arrow">›</text>
      </view>
      <view class="link-item" @tap="go('/pages-employee/report/history/index')">
        <view class="link-icon icon-emerald">录</view>
        <view class="link-body">
          <text class="link-title">报工记录</text>
          <text class="link-sub">查看历史报工明细</text>
        </view>
        <text class="link-arrow">›</text>
      </view>
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
// 扫码 hero
.scan-hero {
  padding: $space-7 $space-6;
  border-radius: $radius-xl;
  text-align: center;
  margin-bottom: $space-5;
  transition: transform $dur-fast $ease-smooth;
  &:active { transform: scale(0.985); }
}

.scan-icon-wrap {
  position: relative;
  width: 144rpx;
  height: 144rpx;
  margin: 0 auto $space-4;
}

.scan-icon {
  width: 100%;
  height: 100%;
  border-radius: $radius-xl;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(8rpx);
  border: 2rpx solid rgba(255, 255, 255, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 64rpx;
  font-weight: $fw-bold;
  color: #fff;
}

.scan-corner {
  position: absolute;
  width: 24rpx;
  height: 24rpx;
  border: 4rpx solid #fff;
  border-radius: 4rpx;
}
.scan-corner.tl { top: -8rpx; left: -8rpx; border-right: none; border-bottom: none; }
.scan-corner.tr { top: -8rpx; right: -8rpx; border-left: none; border-bottom: none; }
.scan-corner.bl { bottom: -8rpx; left: -8rpx; border-right: none; border-top: none; }
.scan-corner.br { bottom: -8rpx; right: -8rpx; border-left: none; border-top: none; }

.scan-title {
  display: block;
  font-size: $text-xl;
  font-weight: $fw-bold;
  color: #fff;
  letter-spacing: 1rpx;
}
.scan-hint {
  margin-top: $space-1;
  font-size: $text-sm;
  color: rgba(255, 255, 255, 0.78);
}

// 输入卡
.label {
  display: block;
  font-size: $text-sm;
  color: $slate-500;
  margin-bottom: $space-3;
  font-weight: $fw-medium;
}
.input-row {
  display: flex;
  gap: $space-3;
  align-items: center;
}
.input {
  flex: 1;
  background: $slate-50;
  padding: 22rpx 24rpx;
  border-radius: $radius-md;
  border: 1rpx solid $slate-200;
  font-size: $text-md;
  color: $slate-800;
  font-variant-numeric: tabular-nums;
  transition: border-color $dur-fast $ease-smooth;
  &:focus { border-color: $brand-500; }
}
.go-btn {
  height: 76rpx;
  line-height: 76rpx;
  padding: 0 32rpx;
  font-size: $text-md;
}

// 快捷链接
.link-grid {
  display: flex;
  flex-direction: column;
  gap: $space-3;
  margin-top: $space-2;
}
.link-item {
  display: flex;
  align-items: center;
  gap: $space-4;
  background: #fff;
  border-radius: $radius-lg;
  padding: $space-5;
  box-shadow: $shadow-sm;
  border: 1rpx solid rgba($slate-200, 0.6);
  transition: transform $dur-fast $ease-smooth;
  &:active { transform: scale(0.985); }
}
.link-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30rpx;
  font-weight: $fw-bold;
  flex-shrink: 0;
}
.icon-amber   { background: $warn-bg;    color: $warn-deep; }
.icon-emerald { background: $success-bg; color: $success-deep; }
.link-body {
  flex: 1;
  min-width: 0;
}
.link-title {
  display: block;
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-800;
}
.link-sub {
  margin-top: 4rpx;
  display: block;
  font-size: $text-xs;
  color: $slate-500;
}
.link-arrow {
  color: $slate-300;
  font-size: $text-xl;
}
</style>
