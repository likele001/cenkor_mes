<template>
  <view class="emp-card record-card">
    <view class="head">
      <text class="title">{{ title }}</text>
      <text class="emp-tag" :class="status.tone">{{ status.text }}</text>
    </view>
    <view class="emp-kv-grid">
      <view class="emp-kv">
        <text class="k">订单号</text>
        <text class="v">{{ item.order_code || '—' }}</text>
      </view>
      <view class="emp-kv">
        <text class="k">工序</text>
        <text class="v">{{ item.process_name || '—' }}</text>
      </view>
      <view class="emp-kv">
        <text class="k">报工数量</text>
        <text class="v">{{ qtyText }}</text>
      </view>
      <view class="emp-kv">
        <text class="k">结果</text>
        <text class="v">{{ resultText }}</text>
      </view>
    </view>
    <view class="foot">
      <text class="time">🕐 {{ timeText }}</text>
      <text class="type-tag">计件</text>
    </view>
    <view v-if="item.remark" class="remark">备注：{{ item.remark }}</view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ReportUnitItem } from '@/api/h5/reportUnits'
import { reportStatusLabel } from '@/utils/statusLabels'
import { formatDateTime } from '@/utils/taskDisplay'

const props = defineProps<{ item: ReportUnitItem }>()

const title = computed(
  () => props.item.sku_label || props.item.unit_label || props.item.task_code || `第${props.item.unit_seq}件`,
)
const status = computed(() => reportStatusLabel(props.item.status))
const qtyText = computed(() => (props.item.unit_seq ? `1（第${props.item.unit_seq}件）` : '1'))
const resultText = computed(() => (props.item.result_type === 'bad' ? '不良' : '合格'))
const timeText = computed(() => formatDateTime(props.item.submitted_at || props.item.created_at))
</script>

<style scoped lang="scss">
.head {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 20rpx;
}
.title {
  flex: 1;
  font-size: 30rpx;
  font-weight: 700;
  color: #1e293b;
}
.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid #f1f5f9;
}
.time {
  font-size: 22rpx;
  color: #94a3b8;
}
.type-tag {
  font-size: 22rpx;
  color: #64748b;
  background: #f8fafc;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}
.remark {
  margin-top: 16rpx;
  padding: 16rpx;
  background: #f8fafc;
  border-radius: 12rpx;
  font-size: 24rpx;
  color: #64748b;
}
</style>
