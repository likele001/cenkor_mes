<template>
  <view class="emp-page help-page">
    <view class="emp-card">
      <text class="emp-title">智能帮助</text>
      <text class="help-sub">检索系统文档，解答 CenkorMES 操作问题</text>
      <textarea v-model="question" class="help-input" placeholder="例如：如何扫码报工？工资怎么算？" />
      <button class="help-btn" :loading="loading" @tap="ask">提问</button>
    </view>

    <view v-if="answer" class="emp-card">
      <text class="answer-title">回答</text>
      <text class="answer-body">{{ answer }}</text>
      <view v-if="sources.length" class="sources">
        <text class="sources-title">参考文档</text>
        <text v-for="(s, i) in sources" :key="i" class="source-item">· {{ s.source }} — {{ s.title }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { aiHelp } from '@/api/h5/ai'

const question = ref('')
const loading = ref(false)
const answer = ref('')
const sources = ref<Array<{ source: string; title: string }>>([])

async function ask() {
  const q = question.value.trim()
  if (!q) return
  loading.value = true
  answer.value = ''
  sources.value = []
  try {
    const res = await aiHelp(q)
    answer.value = res.answer
    sources.value = res.sources || []
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '帮助暂不可用', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.help-page { padding: 24rpx; }
.help-sub { display: block; font-size: 24rpx; color: #909399; margin: 8rpx 0 24rpx; }
.help-input {
  width: 100%;
  min-height: 160rpx;
  padding: 16rpx;
  box-sizing: border-box;
  border: 1px solid #e4e7ed;
  border-radius: 12rpx;
  font-size: 28rpx;
}
.help-btn {
  margin-top: 24rpx;
  background: #2563eb;
  color: #fff;
  border-radius: 12rpx;
  font-size: 28rpx;
}
.answer-title { font-weight: 600; font-size: 30rpx; display: block; margin-bottom: 16rpx; }
.answer-body { font-size: 28rpx; line-height: 1.6; white-space: pre-wrap; color: #303133; }
.sources { margin-top: 24rpx; }
.sources-title { font-size: 24rpx; color: #909399; display: block; margin-bottom: 8rpx; }
.source-item { display: block; font-size: 22rpx; color: #606266; line-height: 1.5; }
</style>
