<template>
  <view class="emp-page">
    <view class="page-head">
      <text class="page-title">工资统计</text>
      <text class="refresh" @tap="load">↻</text>
    </view>

    <picker mode="date" fields="month" @change="onMonth">
      <view class="emp-card month-row">
        <text class="label">选择月份</text>
        <text class="value">{{ monthLabel }} ›</text>
      </view>
    </picker>

    <view class="emp-card overview">
      <view class="overview-top">
        <text class="overview-title">工资概览</text>
        <text class="count-badge">{{ month || '当月' }}</text>
      </view>
      <view class="emp-stat-grid">
        <view class="stat-item">
          <view class="stat-val money">¥{{ total }}</view>
          <view class="stat-lbl">总工资</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ totalQty }}</view>
          <view class="stat-lbl">总报工数</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">¥{{ avgPrice }}</view>
          <view class="stat-lbl">平均单价</view>
        </view>
      </view>
    </view>

    <view v-for="row in items" :key="row.id" class="emp-card row-card">
      <view class="row-head">
        <text class="proc">{{ row.process_name || `工序#${row.process_id}` }}</text>
        <text class="amt">¥{{ formatMoney(row.amount) }}</text>
      </view>
      <view class="row-sub">{{ row.good_qty }} 件 × ¥{{ formatMoney(row.unit_price) }}</view>
    </view>

    <view v-if="!items.length && loaded" class="emp-empty">该月份没有报工记录</view>
    <button class="emp-btn-outline slip-btn" @tap="goSlip">查看电子工资条</button>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getSalary, getSalarySummary } from '@/api/h5/salary'
import type { H5SalaryItem } from '@/api/h5/tasks'
import { formatMoney } from '@/utils/taskDisplay'
import { smartAutoSubscribe } from '@/utils/subscribe'

const month = ref('')
const total = ref('0.00')
const totalQty = ref(0)
const items = ref<H5SalaryItem[]>([])
const loaded = ref(false)

const monthLabel = computed(() => {
  if (!month.value) return '选择月份'
  const [y, m] = month.value.split('-')
  return `${y}年${m}月`
})

const avgPrice = computed(() => {
  if (!totalQty.value) return '0.00'
  return formatMoney(Number(total.value) / totalQty.value)
})

onMounted(() => {
  const now = new Date()
  month.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  load()
  // 工资页：用户最关心工资，订阅提醒推送
  smartAutoSubscribe('emp-salary', [
    'salary.slip_remind',
    'salary.slip_reset',
    'salary.slip_rejected',
  ]).catch(() => {})
})

function onMonth(e: { detail: { value: string } }) {
  month.value = e.detail.value.slice(0, 7)
  load()
}

async function load() {
  loaded.value = false
  const m = month.value || undefined
  const s = await getSalarySummary(m)
  const sum = (s.items as { total_amount?: number; total_qty?: number }[])?.[0]
  total.value = formatMoney(sum?.total_amount ?? 0)
  totalQty.value = sum?.total_qty ?? 0
  const r = await getSalary(m)
  items.value = r.items || []
  loaded.value = true
}

function goSlip() {
  uni.navigateTo({ url: `/pages-employee/salary/slip/index${month.value ? '?month=' + month.value : ''}` })
}
</script>

<style scoped lang="scss">
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #1e293b;
}
.refresh {
  font-size: 40rpx;
  color: #2563eb;
}
.month-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.label {
  font-size: 28rpx;
  color: #64748b;
}
.value {
  font-size: 28rpx;
  font-weight: 600;
  color: #1e293b;
}
.overview-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 20rpx;
}
.overview-title {
  font-size: 28rpx;
  font-weight: 600;
}
.count-badge {
  font-size: 22rpx;
  color: #64748b;
  background: #f1f5f9;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
}
.money {
  font-size: 36rpx;
}
.row-card {
  padding: 24rpx;
}
.row-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.proc {
  font-size: 28rpx;
  font-weight: 600;
  color: #1e293b;
}
.amt {
  font-size: 30rpx;
  font-weight: 700;
  color: #2563eb;
}
.row-sub {
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #94a3b8;
}
.slip-btn {
  margin-top: 24rpx;
}
</style>
