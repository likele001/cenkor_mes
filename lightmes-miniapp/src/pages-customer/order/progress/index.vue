<template>
  <view class="cust-page">
    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <template v-else-if="data">
      <!-- 总进度渐变卡 -->
      <view class="cust-card cust-card--brand progress-hero">
        <view class="hero-head">
          <text class="hero-code mono">{{ data.code }}</text>
          <text class="cust-tag" :class="statusTone(data.status)">{{ orderStatusLabel(data.status) }}</text>
        </view>
        <view class="hero-progress">
          <view class="hero-bar"><view class="hero-fill" :style="{ width: pct(data.progress) + '%' }" /></view>
          <text class="hero-pct">{{ pct(data.progress) }}%</text>
        </view>
        <view class="hero-meta">
          <view class="meta-item"><text class="meta-val">{{ data.done_qty }}/{{ data.total_qty }}</text><text class="meta-lbl">{{ t('customer.orderProgress.quantity') }}</text></view>
          <view class="meta-item"><text class="meta-val">{{ data.due_date || '—' }}</text><text class="meta-lbl">{{ t('customer.orderDetail.dueDate') }}</text></view>
        </view>
      </view>

      <!-- 工单列表 -->
      <view class="cust-card">
        <text class="cust-section-title">{{ t('customer.orderProgress.workOrders') }}</text>
        <view v-if="!data.work_orders?.length" class="cust-empty">{{ t('customer.orderProgress.noTask') }}</view>
        <view v-for="wo in data.work_orders" :key="wo.id" class="wo-block">
          <view class="wo-head">
            <text class="wo-title">{{ wo.sku?.display_name || wo.sku?.name || `#${wo.id}` }}</text>
            <text class="wo-pct">{{ pct(wo.progress) }}%</text>
          </view>
          <view class="wo-bar"><view class="wo-fill" :style="{ width: pct(wo.progress) + '%' }" /></view>
          <view class="wo-meta"><text>{{ wo.done_qty }}/{{ wo.qty }}</text></view>
          <view v-for="task in wo.tasks" :key="task.id" class="task-row">
            <view class="task-left">
              <text class="task-name">{{ task.process?.name || task.task_code }}</text>
              <text class="cust-tag" :class="taskTone(task)">{{ taskStatusText(task) }}</text>
            </view>
            <view class="task-right">
              <text class="task-qty">{{ task.done_qty ?? 0 }}/{{ task.planned_qty }}</text>
              <text class="task-pct">{{ pct(task.progress) }}%</text>
            </view>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import { getMyOrderProgress, type CustomerOrderProgress } from '@/api/h5/customer'
import { useCustomerLabels } from '@/composables/useCustomerLabels'
import { useCustomerLocale } from '@/composables/useCustomerLocale'
import { usePermission } from '@/composables/usePermission'

const { t } = useI18n()
const { orderStatusLabel, toPercent } = useCustomerLabels()
const { setNavTitle } = useCustomerLocale()
const { requireCustomer } = usePermission()

const orderId = ref(0)
const loading = ref(false)
const data = ref<CustomerOrderProgress | null>(null)

function pct(v: number | undefined | null) { return toPercent(v) }
function statusTone(s: string) {
  if (s === 'done' || s === 'completed') return 'ok'
  if (s === 'producing') return 'info'
  return 'muted'
}

type TaskItem = { process?: { name?: string }; task_code?: string; done_qty?: number; planned_qty?: number; progress?: number; status?: string }
function taskStatusText(task: TaskItem) {
  if (task.status === 'done') return '完成'
  if (task.status === 'working') return '进行中'
  if (task.done_qty && task.done_qty > 0) return '部分完成'
  return '待开始'
}
function taskTone(task: TaskItem) {
  if (task.status === 'done') return 'ok'
  if (task.status === 'working' || (task.done_qty && task.done_qty > 0)) return 'info'
  return 'muted'
}

async function load() {
  if (!orderId.value) return
  loading.value = true
  try { data.value = await getMyOrderProgress(orderId.value) } finally { loading.value = false }
}

onLoad((q) => { orderId.value = Number(q?.id || 0) })
onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.orderProgress.title')
  load()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.progress-hero { padding: 28rpx; border-radius: 24rpx; }
.hero-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20rpx; }
.hero-code { font-family: monospace; font-size: 30rpx; font-weight: 700; color: #fff; }
.hero-progress { display: flex; align-items: center; gap: 16rpx; margin-bottom: 20rpx; }
.hero-bar { flex: 1; height: 24rpx; background: rgba(255,255,255,0.2); border-radius: 999rpx; overflow: hidden; }
.hero-fill { height: 100%; background: #fff; border-radius: 999rpx; transition: width 0.4s ease; }
.hero-pct { font-size: 28rpx; font-weight: 700; color: #fff; min-width: 80rpx; text-align: right; }
.hero-meta { display: flex; gap: 24rpx; }
.meta-item { flex: 1; }
.meta-val { display: block; font-size: 28rpx; font-weight: 700; color: #fff; }
.meta-lbl { display: block; font-size: 20rpx; color: rgba(255,255,255,0.72); margin-top: 4rpx; }

.wo-block { padding: 16rpx 0; border-bottom: 1rpx solid #f0f9ff; }
.wo-block:last-child { border-bottom: none; }
.wo-head { display: flex; justify-content: space-between; align-items: center; }
.wo-title { font-weight: 600; font-size: 26rpx; color: #0c4a6e; }
.wo-pct { font-size: 26rpx; font-weight: 700; color: #0284c7; }
.wo-bar { height: 12rpx; background: #e0f2fe; border-radius: 999rpx; overflow: hidden; margin: 8rpx 0; }
.wo-fill { height: 100%; background: linear-gradient(90deg, #0ea5e9, #0284c7); border-radius: 999rpx; }
.wo-meta { font-size: 22rpx; color: #64748b; margin-bottom: 8rpx; }
.task-row { display: flex; justify-content: space-between; align-items: center; padding: 12rpx 16rpx; margin-top: 8rpx; background: #f0f9ff; border-radius: 10rpx; }
.task-left { display: flex; align-items: center; gap: 12rpx; }
.task-name { font-size: 22rpx; color: #334155; }
.task-right { display: flex; align-items: center; gap: 12rpx; }
.task-qty { font-size: 20rpx; color: #64748b; }
.task-pct { font-size: 20rpx; font-weight: 600; color: #0284c7; }
</style>
