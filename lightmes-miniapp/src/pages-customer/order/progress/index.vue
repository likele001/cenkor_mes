<template>
  <view class="cust-page">
    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <template v-else-if="data">
      <!-- 总进度卡片 -->
      <view class="cust-card progress-card">
        <view class="progress-head">
          <text class="mono cust-title">{{ data.code }}</text>
          <text class="cust-tag" :class="statusTone(data.status)">{{ orderStatusLabel(data.status) }}</text>
        </view>
        <!-- 总进度条 -->
        <view class="progress-section">
          <view class="progress-bar-wrap">
            <view class="progress-bar">
              <view class="progress-fill" :style="{ width: pct(data.progress) + '%' }" />
            </view>
            <text class="progress-pct">{{ pct(data.progress) }}%</text>
          </view>
        </view>
        <view class="kv"><text class="k">{{ t('customer.orderProgress.quantity') }}</text><text class="v">{{ data.done_qty }}/{{ data.total_qty }}</text></view>
        <view class="kv"><text class="k">{{ t('customer.orderDetail.dueDate') }}</text><text class="v">{{ data.due_date || '—' }}</text></view>
      </view>

      <!-- 工单列表 -->
      <view class="cust-card">
        <text class="section">{{ t('customer.orderProgress.workOrders') }}</text>
        <view v-if="!data.work_orders?.length" class="cust-empty">{{ t('customer.orderProgress.noTask') }}</view>
        <view v-for="wo in data.work_orders" :key="wo.id" class="wo-card">
          <view class="wo-head">
            <text class="wo-title">{{ wo.sku?.display_name || wo.sku?.name || `#${wo.id}` }}</text>
            <text class="wo-pct">{{ pct(wo.progress) }}%</text>
          </view>
          <!-- 工单进度条 -->
          <view class="progress-bar small">
            <view class="progress-fill" :style="{ width: pct(wo.progress) + '%' }" />
          </view>
          <view class="wo-meta">
            <text>{{ wo.done_qty }}/{{ wo.qty }}</text>
          </view>
          <!-- 工序任务列表 -->
          <view v-for="task in wo.tasks" :key="task.id" class="task-row">
            <view class="task-left">
              <text class="task-name">{{ task.process?.name || task.task_code }}</text>
              <text class="task-tag" :class="taskTone(task)">{{ taskStatusText(task) }}</text>
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

function pct(v: number | undefined | null) {
  return toPercent(v)
}

function statusTone(s: string) {
  if (s === 'done' || s === 'completed') return 'tone-ok'
  if (s === 'producing') return 'tone-active'
  return ''
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
  if (task.status === 'working' || (task.done_qty && task.done_qty > 0)) return 'active'
  return 'pending'
}

async function load() {
  if (!orderId.value) return
  loading.value = true
  try {
    data.value = await getMyOrderProgress(orderId.value)
  } finally {
    loading.value = false
  }
}

onLoad((q) => {
  orderId.value = Number(q?.id || 0)
})

onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.orderProgress.title')
  load()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.progress-card {
  padding: 24rpx;
}
.progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}
.progress-section {
  margin-bottom: 20rpx;
}
.progress-bar-wrap {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.progress-bar {
  flex: 1;
  height: 24rpx;
  background: #e2e8f0;
  border-radius: 999rpx;
  overflow: hidden;
}
.progress-bar.small {
  height: 16rpx;
  margin: 8rpx 0;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0ea5e9, #0284c7);
  border-radius: 999rpx;
  transition: width 0.3s ease;
}
.progress-pct {
  font-size: 28rpx;
  font-weight: 700;
  color: #0369a1;
  min-width: 80rpx;
  text-align: right;
}
.kv {
  display: flex;
  justify-content: space-between;
  padding: 8rpx 0;
  font-size: 26rpx;
}
.k {
  color: #64748b;
}
.mono {
  font-family: monospace;
}
.section {
  font-weight: 600;
  display: block;
  margin-bottom: 16rpx;
}
.wo-card {
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
}
.wo-card:last-child {
  border-bottom: none;
}
.wo-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.wo-title {
  font-weight: 600;
  font-size: 26rpx;
}
.wo-pct {
  font-size: 26rpx;
  font-weight: 700;
  color: #0369a1;
}
.wo-meta {
  font-size: 22rpx;
  color: #64748b;
  margin-bottom: 12rpx;
}
.task-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12rpx 0 12rpx 16rpx;
  margin-top: 8rpx;
  background: #f8fafc;
  border-radius: 8rpx;
}
.task-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.task-name {
  font-size: 24rpx;
  color: #334155;
}
.task-tag {
  font-size: 20rpx;
  padding: 2rpx 10rpx;
  border-radius: 999rpx;
}
.task-tag.ok { background: #dcfce7; color: #15803d; }
.task-tag.active { background: #dbeafe; color: #2563eb; }
.task-tag.pending { background: #f1f5f9; color: #94a3b8; }
.task-right {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.task-qty {
  font-size: 22rpx;
  color: #64748b;
}
.task-pct {
  font-size: 22rpx;
  font-weight: 600;
  color: #0369a1;
}
.tone-ok { background: #dcfce7; color: #15803d; }
.tone-active { background: #dbeafe; color: #2563eb; }
</style>
