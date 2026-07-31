<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="days" class="search" type="number" placeholder="近N天(默认7)" @confirm="reload" />
      <button class="btn" size="mini" @tap="reload">刷新</button>
    </view>

    <view class="section">
      <text class="section-title">产量趋势</text>
      <view v-for="d in trend" :key="d.date" class="row">
        <text>{{ d.date }}</text>
        <text>合格 {{ d.good_qty }} · 不良 {{ d.bad_qty }}</text>
      </view>
      <view v-if="!trend.length" class="empty">暂无数据</view>
    </view>

    <view class="section">
      <text class="section-title">工序产量排行</text>
      <view v-for="(p, i) in rank" :key="i" class="row">
        <text>{{ p.process_name }}</text>
        <text>合格 {{ p.good_qty }} · 不良 {{ p.bad_qty }}</text>
      </view>
      <view v-if="!rank.length" class="empty">暂无数据</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { dashboardAdminApi } from '@/api/admin/dashboard'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const days = ref('7')
const trend = ref<{ date: string; good_qty: number; bad_qty: number }[]>([])
const rank = ref<{ process_name: string; good_qty: number; bad_qty: number }[]>([])

onShow(async () => {
  if (!requirePermission('report.view')) return
  await reload()
})

async function reload() {
  try {
    const n = Number(days.value) || 7
    const r = await dashboardAdminApi.charts(n)
    trend.value = r.daily_trend || []
    rank.value = r.process_rank || []
  } catch {
    trend.value = []
    rank.value = []
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.btn { background: #4338ca; color: #fff; border-radius: 999rpx; }
.section { background: #fff; border-radius: 16rpx; padding: 24rpx; margin-bottom: 20rpx; }
.section-title { display: block; font-size: 30rpx; font-weight: 700; margin-bottom: 16rpx; }
.row { display: flex; justify-content: space-between; font-size: 26rpx; padding: 12rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.empty { color: #94a3b8; font-size: 26rpx; padding: 16rpx 0; }
</style>
