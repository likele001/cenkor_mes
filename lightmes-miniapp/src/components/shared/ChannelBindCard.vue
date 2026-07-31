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

    <view v-if="wecomEnabled" class="block">
      <view class="head">
        <text class="title">企业微信通知</text>
        <text class="status" :class="{ ok: wecomBound }">{{ wecomBound ? '已绑定' : '未绑定' }}</text>
      </view>
      <text v-if="wecomBound && wecomUserid" class="hint">企微账号：{{ wecomUserid }}</text>
      <text v-else-if="!wecomBound" class="hint">复制链接在手机企业微信中打开完成授权绑定</text>
      <button v-if="!wecomBound" class="btn" size="mini" :loading="wecomLoading" @tap="bindWecom">复制链接绑定企微</button>
    </view>

    <view v-if="dingtalkEnabled" class="block">
      <view class="head">
        <text class="title">钉钉通知</text>
        <text class="status" :class="{ ok: dingtalkBound }">{{ dingtalkBound ? '已绑定' : '未绑定' }}</text>
      </view>
      <text v-if="dingtalkBound && dingtalkUserid" class="hint">钉钉账号：{{ dingtalkUserid }}</text>
      <text v-else-if="!dingtalkBound" class="hint">复制链接在手机钉钉中打开完成授权绑定</text>
      <button v-if="!dingtalkBound" class="btn" size="mini" :loading="dingtalkLoading" @tap="bindDingtalk">复制链接绑定钉钉</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getFeishuBindStatus, getFeishuBindUrl } from '@/api/h5/feishu'
import { getWecomBindStatus, getWecomBindUrl } from '@/api/h5/wecom'
import { getDingtalkBindStatus, getDingtalkBindUrl } from '@/api/h5/dingtalk'

const loaded = ref(false)
const feishuEnabled = ref(false)
const feishuBound = ref(false)
const feishuBotLink = ref('')
const feishuLoading = ref(false)
const wecomEnabled = ref(false)
const wecomBound = ref(false)
const wecomUserid = ref('')
const wecomLoading = ref(false)
const dingtalkEnabled = ref(false)
const dingtalkBound = ref(false)
const dingtalkUserid = ref('')
const dingtalkLoading = ref(false)

async function refresh() {
  try {
    const fs = await getFeishuBindStatus()
    feishuEnabled.value = fs.enabled
    feishuBound.value = fs.bound
    feishuBotLink.value = fs.bot_open_link || ''
  } catch {
    feishuEnabled.value = false
  }
  try {
    const ws = await getWecomBindStatus()
    wecomEnabled.value = ws.enabled
    wecomBound.value = ws.bound
    wecomUserid.value = ws.wecom_userid || ''
  } catch {
    wecomEnabled.value = false
  }
  try {
    const ds = await getDingtalkBindStatus()
    dingtalkEnabled.value = ds.enabled
    dingtalkBound.value = ds.bound
    dingtalkUserid.value = ds.dingtalk_userid || ''
  } catch {
    dingtalkEnabled.value = false
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

async function bindWecom() {
  wecomLoading.value = true
  try {
    const res = await getWecomBindUrl()
    await new Promise<void>((resolve, reject) => {
      uni.setClipboardData({
        data: res.authorize_url,
        success: () => resolve(),
        fail: () => reject(new Error('复制失败')),
      })
    })
    uni.showToast({ title: '链接已复制，请在手机企业微信打开', icon: 'none', duration: 3000 })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '获取链接失败', icon: 'none' })
  } finally {
    wecomLoading.value = false
  }
}

async function bindDingtalk() {
  dingtalkLoading.value = true
  try {
    const res = await getDingtalkBindUrl()
    await new Promise<void>((resolve, reject) => {
      uni.setClipboardData({
        data: res.authorize_url,
        success: () => resolve(),
        fail: () => reject(new Error('复制失败')),
      })
    })
    uni.showToast({ title: '链接已复制，请在手机钉钉打开', icon: 'none', duration: 3000 })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '获取链接失败', icon: 'none' })
  } finally {
    dingtalkLoading.value = false
  }
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
