<template>
  <view class="emp-card task-card" @tap="emit('tap')">
    <view class="head">
      <text class="title">{{ title }}</text>
      <text class="emp-tag" :class="status.tone">{{ status.text }}</text>
    </view>
    <view class="emp-kv-grid">
      <view class="emp-kv">
        <text class="k">订单号</text>
        <text class="v">{{ orderLabel }}</text>
      </view>
      <view class="emp-kv">
        <text class="k">工序</text>
        <text class="v">{{ processName }}</text>
      </view>
      <view class="emp-kv">
        <text class="k">分配数量</text>
        <text class="v">{{ assignedQty }}</text>
      </view>
      <view class="emp-kv">
        <text class="k">已报数量</text>
        <text class="v">{{ reportedQty }}</text>
      </view>
    </view>
    <view class="emp-progress">
      <view class="emp-progress-bar">
        <view class="emp-progress-fill" :style="{ width: progressWidth }" />
      </view>
      <view class="emp-progress-meta">
        <text>进度</text>
        <text>{{ reportedQty }} / {{ assignedQty }}</text>
      </view>
    </view>
    <view v-if="showAction" class="foot" @tap.stop="emit('report')">
      <button class="emp-btn-primary action-btn">开始报工 →</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { H5Task } from '@/api/h5/tasks'
import { taskStatusLabel } from '@/utils/statusLabels'
import { taskOrderLabel, taskSkuTitle } from '@/utils/taskDisplay'

const props = defineProps<{
  task: H5Task
  showAction?: boolean
}>()

const emit = defineEmits<{ tap: []; report: [] }>()

const title = computed(() => taskSkuTitle(props.task))
const orderLabel = computed(() => taskOrderLabel(props.task))
const processName = computed(() => props.task.process?.name || '—')
const assignedQty = computed(() => props.task.assigned_qty ?? 0)
const reportedQty = computed(() => props.task.reported_qty ?? 0)
const status = computed(() => taskStatusLabel(props.task.status))
const progressWidth = computed(() => {
  const a = Number(assignedQty.value)
  const r = Number(reportedQty.value)
  if (!a) return '0%'
  return `${Math.min(100, Math.round((r / a) * 100))}%`
})
const showAction = computed(
  () => props.showAction !== false && props.task.status !== 'done' && (props.task.remaining_qty ?? 0) > 0,
)
</script>

<style scoped lang="scss">
.task-card {
  padding: 24rpx;
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 20rpx;
}
.title {
  flex: 1;
  font-size: 30rpx;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.4;
}
.foot {
  margin-top: 20rpx;
}
.action-btn {
  width: 100%;
  height: 76rpx;
  line-height: 76rpx;
  font-size: 28rpx;
}
</style>
