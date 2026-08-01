<template>
  <view class="emp-page">
    <view class="emp-page-head">
      <text class="emp-page-title">工资统计</text>
      <view class="emp-page-action" @tap="load">↻</view>
    </view>

    <!-- 月份选择 -->
    <picker mode="date" fields="month" @change="onMonth">
      <view class="emp-card month-row tappable">
        <view class="month-label-wrap">
          <text class="month-icon">📅</text>
          <text class="month-label">选择月份</text>
        </view>
        <text class="month-value">{{ monthLabel }} ›</text>
      </view>
    </picker>

    <!-- 概览渐变卡 -->
    <view class="emp-card emp-card--brand overview-card">
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

    <!-- 工序明细 -->
    <view class="section-head">工序明细</view>
    <view v-for="row in items" :key="row.id" class="emp-card emp-card--striped strip-info row-card tappable">
      <view class="row-head">
        <text class="proc">{{ row.process_name || `工序#${row.process_id}` }}</text>
        <text class="amt">¥{{ formatMoney(row.amount) }}</text>
      </view>
      <view class="row-sub">{{ row.good_qty }} 件 × ¥{{ formatMoney(row.unit_price) }}</view>
    </view>

    <view v-if="!items.length && loaded" class="emp-empty">
      <text class="emp-empty-icon">📋</text>
      该月份没有报工记录
    </view>

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
// 月份选择
.month-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.month-label-wrap {
  display: flex;
  align-items: center;
  gap: $space-2;
}
.month-icon {
  font-size: $text-md;
}
.month-label {
  font-size: $text-md;
  color: $slate-600;
  font-weight: $fw-medium;
}
.month-value {
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $brand-600;
}

// 概览
.overview-card {
  padding: $space-5 $space-6;
}
.overview-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-4;
}
.overview-title {
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: rgba(255, 255, 255, 0.92);
}
.count-badge {
  font-size: $text-xs;
  color: #fff;
  background: rgba(255, 255, 255, 0.18);
  padding: 4rpx 16rpx;
  border-radius: $radius-pill;
  font-weight: $fw-medium;
}
.overview-card .stat-val.money {
  font-size: $text-lg;
}

// 区块标题
.section-head {
  font-size: $text-lg;
  font-weight: $fw-bold;
  color: $slate-800;
  margin: $space-5 0 $space-4 4rpx;
  display: flex;
  align-items: center;
  gap: $space-2;
  &::before {
    content: '';
    width: 6rpx;
    height: 28rpx;
    background: $brand-600;
    border-radius: $radius-pill;
  }
}

// 明细卡
.row-card {
  padding: $space-5;
  padding-left: 32rpx;
}
.row-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.proc {
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-800;
}
.amt {
  font-size: $text-lg;
  font-weight: $fw-bold;
  color: $brand-600;
  font-variant-numeric: tabular-nums;
}
.row-sub {
  margin-top: $space-1;
  font-size: $text-xs;
  color: $slate-400;
}

.slip-btn {
  margin-top: $space-5;
  width: 100%;
}
</style>
