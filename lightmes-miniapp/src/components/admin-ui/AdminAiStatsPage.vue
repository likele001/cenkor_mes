<template>
  <view class="adm-page">
    <view class="hero">
      <text class="hero-title">AI 调用统计</text>
      <text class="hero-sub">基于 assistant 消息统计 token</text>
      <view class="toolbar">
        <input v-model.number="days" type="number" class="input" />
        <button class="btn primary" size="mini" :loading="loading" @tap="load">查询</button>
      </view>
    </view>

    <view v-if="stats" class="stat-grid">
      <view class="stat"><text class="label">总调用</text><text class="value">{{ stats.total_calls }}</text></view>
      <view class="stat"><text class="label">Tokens In</text><text class="value">{{ stats.tokens_in }}</text></view>
      <view class="stat"><text class="label">Tokens Out</text><text class="value">{{ stats.tokens_out }}</text></view>
    </view>

    <view v-if="stats?.by_scene?.length" class="card">
      <text class="card-title">按场景</text>
      <view v-for="(row, i) in stats.by_scene" :key="'s' + i" class="row">
        <text class="row-main">{{ row.scene }}</text>
        <text class="row-sub">{{ row.calls }} 次 · In {{ row.tokens_in }} · Out {{ row.tokens_out }}</text>
      </view>
    </view>

    <view v-if="stats?.daily?.length" class="card">
      <text class="card-title">每日趋势</text>
      <view v-for="(row, i) in stats.daily" :key="'d' + i" class="row">
        <text class="row-main">{{ row.date }}</text>
        <text class="row-sub">{{ row.calls }} 次 · In {{ row.tokens_in }} · Out {{ row.tokens_out }}</text>
      </view>
    </view>

    <view v-if="!loading && !stats" class="tip">暂无统计数据</view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { aiAdminApi } from '@/api/admin/ai'

const loading = ref(false)
const days = ref(30)
const stats = ref<{
  total_calls: number
  tokens_in: number
  tokens_out: number
  by_scene: Array<{ scene: string; calls: number; tokens_in: number; tokens_out: number }>
  daily: Array<{ date: string; calls: number; tokens_in: number; tokens_out: number }>
} | null>(null)

async function load() {
  loading.value = true
  try {
    stats.value = await aiAdminApi.stats(days.value)
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped lang="scss">
.hero { padding: 24rpx; }
.hero-title { display: block; font-size: 34rpx; font-weight: 700; }
.hero-sub { display: block; font-size: 24rpx; color: #64748b; margin: 8rpx 0 16rpx; }
.toolbar { display: flex; gap: 12rpx; align-items: center; }
.input { flex: 1; background: #fff; border-radius: 12rpx; padding: 12rpx 16rpx; font-size: 28rpx; }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12rpx; padding: 0 24rpx 20rpx; }
.stat { background: #fff; border-radius: 12rpx; padding: 20rpx; text-align: center; }
.label { display: block; font-size: 22rpx; color: #94a3b8; }
.value { display: block; font-size: 36rpx; font-weight: 700; color: #4338ca; margin-top: 8rpx; }
.card { background: #fff; border-radius: 16rpx; margin: 0 24rpx 20rpx; padding: 24rpx; }
.card-title { display: block; font-size: 28rpx; font-weight: 600; margin-bottom: 16rpx; }
.row { padding: 12rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.row-main { display: block; font-size: 26rpx; color: #334155; }
.row-sub { display: block; font-size: 24rpx; color: #64748b; margin-top: 6rpx; }
.tip { padding: 24rpx; text-align: center; color: #94a3b8; }
.btn.primary { background: #4338ca; color: #fff; border-radius: 12rpx; }
</style>
