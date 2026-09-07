<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <view v-if="loaded" class="channel-bind">
    <view v-if="feishuEnabled" class="block">
      <view class="head">
        <text class="title">飞书通知</text>
        <text class="status" :class="{ ok: feishuBound }">{{ feishuBound ? '已绑定' : '未绑定' }}</text>
      </view>
      <text v-if="!feishuBound" class="hint">绑定后派工/报工/工资等通知会推送到飞书机器人</text>
      <button v-if="!feishuBound" class="btn" size="mini" :loading="feishuLoading" @tap="bindFeishu">复制链接绑定飞书</button>
      <button v-else class="btn" size="mini" @tap="openFeishuBot">打开飞书机器人</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getFeishuBindStatus, getFeishuBindUrl } from '@/api/h5/feishu'

const loaded = ref(false)
const feishuEnabled = ref(false)
const feishuBound = ref(false)
const feishuBotLink = ref('')
const feishuLoading = ref(false)

async function refresh() {
  try {
    const fs = await getFeishuBindStatus()
    feishuEnabled.value = fs.enabled
    feishuBound.value = fs.bound
    feishuBotLink.value = fs.bot_open_link || ''
  } catch {
    feishuEnabled.value = false
  }
  loaded.value = true
}

async function bindFeishu() {
  feishuLoading.value = true
  try {
    const res = await getFeishuBindUrl()
    await new Promise<void>((resolve, reject) => {
      uni.setClipboardData({
        data: res.authorize_url,
        success: () => resolve(),
        fail: () => reject(new Error('复制失败')),
      })
    })
    uni.showToast({ title: '链接已复制，请在浏览器打开完成绑定', icon: 'none', duration: 3000 })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '获取链接失败', icon: 'none' })
  } finally {
    feishuLoading.value = false
  }
}

function openFeishuBot() {
  if (!feishuBotLink.value) {
    uni.showToast({ title: '未配置飞书机器人链接', icon: 'none' })
    return
  }
  uni.setClipboardData({
    data: feishuBotLink.value,
    success: () => uni.showToast({ title: '机器人链接已复制', icon: 'none' }),
  })
}

onMounted(refresh)

defineExpose({ refresh })
</script>

<style scoped lang="scss">
.channel-bind {
  margin-top: 16rpx;
}
.block {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 28rpx;
  font-weight: 600;
  color: #334155;
}
.status {
  font-size: 24rpx;
  color: #f59e0b;
}
.status.ok {
  color: #16a34a;
}
.hint {
  display: block;
  margin-top: 12rpx;
  font-size: 22rpx;
  color: #94a3b8;
  line-height: 1.5;
}
.btn {
  margin-top: 16rpx;
  background: #eff6ff;
  color: #2563eb;
}
</style>
