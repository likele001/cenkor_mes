<template>
  <view class="emp-card emp-card--striped tappable" :class="stripClass" @tap="emit('tap')">
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
        <text class="v reported">{{ reportedQty }}</text>
      </view>
    </view>

    <view class="emp-progress">
      <view class="emp-progress-bar">
        <view class="emp-progress-fill" :style="{ width: progressWidth }" />
      </view>
      <view class="emp-progress-meta">
        <text>完成进度</text>
        <text class="progress-pct">{{ progressPct }}%</text>
      </view>
    </view>

    <view v-if="showAction" class="foot" @tap.stop="emit('report')">
      <button class="emp-btn-primary action-btn">开始报工</button>
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

const stripClass = computed(() => {
  const map: Record<string, string> = {
    pending: 'strip-pending',
    working: 'strip-working',
    done: 'strip-done',
  }
  return map[props.task.status] || 'strip-info'
})

const progressPct = computed(() => {
  const a = Number(assignedQty.value)
  const r = Number(reportedQty.value)
  if (!a) return 0
  return Math.min(100, Math.round((r / a) * 100))
})

const progressWidth = computed(() => `${progressPct.value}%`)

const showAction = computed(
  () => props.showAction !== false && props.task.status !== 'done' && (props.task.remaining_qty ?? 0) > 0,
)
</script>

<style scoped lang="scss">
// uni.scss 由 uni-app 自动注入

.task-card {
  padding: $space-5;
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: $space-3;
  margin-bottom: $space-4;
}
.title {
  flex: 1;
  font-size: $text-lg;
  font-weight: $fw-bold;
  color: $slate-800;
  line-height: 1.4;
  letter-spacing: -0.3rpx;
}
.emp-kv {
  .v.reported {
    color: $brand-600;
  }
}
.progress-pct {
  color: $brand-600;
  font-weight: $fw-semibold;
}
.foot {
  margin-top: $space-5;
}
.action-btn {
  width: 100%;
  height: 80rpx;
  line-height: 80rpx;
  font-size: $text-md;
  font-weight: $fw-semibold;
  letter-spacing: 2rpx;
}
</style>
