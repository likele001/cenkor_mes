<template>
  <view v-if="show" class="privacy-mask">
    <view class="privacy-dialog">
      <view class="privacy-title">隐私保护提示</view>
      <view class="privacy-content">
        在使用拍照、相册等功能前，请阅读并同意
        <text class="privacy-link" @click="openContract">《隐私保护指引》</text>
      </view>
      <view class="privacy-btns">
        <view class="privacy-btn privacy-btn-reject" @click="handleReject">拒绝</view>
        <button
          class="privacy-btn privacy-btn-agree"
          id="agree-btn"
          open-type="agreePrivacyAuthorization"
          @agreeprivacyauthorization="handleAgree"
        >
          同意
        </button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const show = ref(false)
let resolveFn: ((result: { buttonId: string; event: string }) => void) | null = null
let rejectFn: (() => void) | null = null

function openPrivacyPopup(resolve: typeof resolveFn, reject: typeof rejectFn) {
  resolveFn = resolve
  rejectFn = reject
  show.value = true
}

function openContract() {
  // @ts-ignore
  wx.openPrivacyContract()
}

function handleAgree() {
  show.value = false
  if (resolveFn) {
    resolveFn({ buttonId: 'agree-btn', event: 'agree' })
  }
}

function handleReject() {
  show.value = false
  if (rejectFn) {
    rejectFn()
  }
}

// Expose for App.vue
defineExpose({ openPrivacyPopup })
</script>

<style scoped>
.privacy-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}
.privacy-dialog {
  width: 80%;
  background: #fff;
  border-radius: 24rpx;
  padding: 40rpx 32rpx;
}
.privacy-title {
  font-size: 34rpx;
  font-weight: 600;
  text-align: center;
  margin-bottom: 20rpx;
}
.privacy-content {
  font-size: 28rpx;
  color: #666;
  line-height: 1.6;
  margin-bottom: 40rpx;
}
.privacy-link {
  color: #07c160;
}
.privacy-btns {
  display: flex;
  gap: 20rpx;
}
.privacy-btn {
  flex: 1;
  height: 80rpx;
  line-height: 80rpx;
  text-align: center;
  border-radius: 12rpx;
  font-size: 30rpx;
}
.privacy-btn-reject {
  background: #f5f5f5;
  color: #999;
}
.privacy-btn-agree {
  background: #07c160;
  color: #fff;
  border: none;
  margin: 0;
  padding: 0;
}
</style>
