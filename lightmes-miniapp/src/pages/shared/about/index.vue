<template>
  <view class="emp-page about-page">
    <view class="about-hero">
      <text class="about-logo">CenkorMES</text>
      <text class="about-ver">v2.0.0</text>
    </view>
    <view class="emp-card about-card">
      <view class="about-row"><text class="about-label">框架</text><text class="about-val">uni-app 3 + Vue 3 + TS</text></view>
      <view class="about-row"><text class="about-label">目标平台</text><text class="about-val">微信小程序</text></view>
      <view class="about-row"><text class="about-label">后端</text><text class="about-val">FastAPI + MySQL + Redis</text></view>
      <view class="about-row"><text class="about-label">构建</text><text class="about-val">{{ buildTime }}</text></view>
    </view>
    <view class="emp-card about-desc">
      <text class="about-desc-text">轻量化生产管理系统，聚焦计件工资、扫码报工、工序管控与全流程质量溯源。</text>
    </view>
    <view class="about-footer">
      <text class="about-copy">CenkorMES  ·  KeleMes 重构版</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const buildTime = ref(import.meta.env?.BUILD_TIME || new Date().toISOString().slice(0, 10))
</script>

<style scoped lang="scss">
.about-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 80rpx;
}
.about-hero {
  text-align: center;
  margin-bottom: 40rpx;
}
.about-logo {
  font-size: 56rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: block;
}
.about-ver {
  font-size: 28rpx;
  color: #94a3b8;
  margin-top: 8rpx;
  display: block;
}
.about-card {
  width: 100%;
  padding: 24rpx;
}
.about-row {
  display: flex;
  justify-content: space-between;
  padding: 20rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
}
.about-row:last-child { border-bottom: none; }
.about-label { font-size: 26rpx; color: #64748b; }
.about-val { font-size: 26rpx; color: #334155; font-weight: 500; }
.about-desc {
  width: 100%;
  padding: 24rpx;
}
.about-desc-text {
  font-size: 26rpx;
  color: #475569;
  line-height: 1.6;
}
.about-footer {
  margin-top: 48rpx;
}
.about-copy {
  font-size: 22rpx;
  color: #94a3b8;
}
</style>
