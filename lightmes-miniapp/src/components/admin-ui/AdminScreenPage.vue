<template>
  <view class="adm-page screen">
    <view class="hero">
      <text class="hero-title">车间实时看板</text>
      <text class="hero-sub">今日生产概览 · {{ updatedAt }}</text>
    </view>

    <view v-if="loading" class="tip">加载中...</view>
    <view v-else class="stats">
      <view class="stat"><text class="l">今日合格</text><text class="v green">{{ today.good_qty ?? 0 }}</text></view>
      <view class="stat"><text class="l">今日不良</text><text class="v red">{{ today.bad_qty ?? 0 }}</text></view>
      <view class="stat"><text class="l">待审核</text><text class="v orange">{{ reports.pending_audit ?? 0 }}</text></view>
      <view class="stat"><text class="l">任务待办</text><text class="v blue">{{ tasks.pending ?? 0 }}</text></view>
    </view>

    <view class="section-title">订单进度滚动</view>
    <scroll-view scroll-y class="order-scroll">
      <view v-for="o in orders" :key="o.id" class="order-row">
        <text class="code">{{ o.code }}</text>
        <text class="meta">{{ o.customer?.name || '—' }} · {{ o.done_qty ?? 0 }}/{{ o.total_qty ?? 0 }}</text>
      </view>
      <view v-if="!orders.length" class="empty">暂无订单</view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { onHide, onShow } from '@dcloudio/uni-app'
import { reactive, ref } from 'vue'
import { dashboardAdminApi, type KanbanOrder } from '@/api/admin/dashboard'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const loading = ref(false)
const orders = ref<KanbanOrder[]>([])
const updatedAt = ref('')
const today = reactive<Record<string, number>>({})
const reports = reactive<Record<string, number>>({})
const tasks = reactive<Record<string, number>>({})
let timer: ReturnType<typeof setInterval> | null = null

onShow(async () => {
  if (!requirePermission('dashboard.view')) return
  await reload()
  timer = setInterval(reload, 15000)
})

onHide(() => {
  if (timer) clearInterval(timer)
  timer = null
})

async function reload() {
  loading.value = orders.value.length === 0
  try {
    const [sum, kanban] = await Promise.all([
      dashboardAdminApi.summary(),
      dashboardAdminApi.kanbanOrders({ limit: 30 }),
    ])
    Object.assign(today, (sum.today as Record<string, number>) || {})
    Object.assign(reports, (sum.reports as Record<string, number>) || {})
    Object.assign(tasks, (sum.tasks as Record<string, number>) || {})
    orders.value = kanban.items || []
    updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    orders.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.screen { background: #0f172a; min-height: 100vh; color: #e2e8f0; padding: 24rpx; box-sizing: border-box; }
.hero-title { display: block; font-size: 36rpx; font-weight: 700; }
.hero-sub { display: block; font-size: 24rpx; color: #94a3b8; margin-top: 8rpx; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; margin: 24rpx 0; }
.stat { background: #1e293b; border-radius: 16rpx; padding: 20rpx; }
.stat .l { display: block; font-size: 24rpx; color: #94a3b8; }
.stat .v { display: block; font-size: 40rpx; font-weight: 700; margin-top: 8rpx; }
.green { color: #34d399; }
.red { color: #f87171; }
.orange { color: #fbbf24; }
.blue { color: #60a5fa; }
.section-title { font-size: 28rpx; margin-bottom: 12rpx; }
.order-scroll { max-height: 55vh; }
.order-row { padding: 16rpx; border-bottom: 1rpx solid #334155; }
.code { display: block; font-size: 28rpx; font-weight: 600; }
.meta { display: block; font-size: 24rpx; color: #94a3b8; margin-top: 4rpx; }
.empty, .tip { text-align: center; color: #64748b; padding: 40rpx; }
</style>
