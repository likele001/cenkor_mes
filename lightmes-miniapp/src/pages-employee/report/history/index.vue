<template>
  <view class="emp-page">
    <view class="emp-page-head">
      <text class="emp-page-title">报工记录</text>
      <view class="emp-page-action" @tap="load">↻</view>
    </view>

    <!-- 月份切换 -->
    <view class="emp-card month-bar">
      <view class="month-arrow" @tap="changeMonth(-1)">◀</view>
      <text class="month-text">{{ monthDisplay }}</text>
      <view class="month-arrow" @tap="changeMonth(1)">▶</view>
    </view>

    <!-- 概览渐变卡 -->
    <view class="emp-card emp-card--brand overview-card">
      <view class="overview-top">
        <text class="overview-title">本月概览</text>
        <text class="count-badge">{{ filteredItems.length }} 条</text>
      </view>
      <view class="emp-stat-grid">
        <view class="stat-item">
          <view class="stat-val">{{ stats.totalQty }}</view>
          <view class="stat-lbl">总报工</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ stats.approved }}</view>
          <view class="stat-lbl">已通过</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ stats.pending }}</view>
          <view class="stat-lbl">待审核</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ stats.dayCount }}</view>
          <view class="stat-lbl">工作天</view>
        </view>
      </view>
    </view>

    <!-- 按日期分组 -->
    <view v-for="group in groupedItems" :key="group.date" class="day-group">
      <view class="day-head">
        <text class="day-date">{{ group.displayDate }}</text>
        <view class="day-stats">
          <text class="day-badge">{{ group.count }} 件</text>
          <text v-if="group.approvedCount" class="day-badge ok-badge">{{ group.approvedCount }} 通过</text>
        </view>
      </view>
      <EmpRecordCard v-for="u in group.items" :key="u.id" :item="u" />
    </view>

    <view v-if="!filteredItems.length && !loading" class="emp-empty">
      <text class="emp-empty-icon">📋</text>
      本月暂无报工记录
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import EmpRecordCard from '@/components/employee-ui/EmpRecordCard.vue'
import { getMyReportUnits, type ReportUnitItem } from '@/api/h5/reportUnits'
import { smartAutoSubscribe } from '@/utils/subscribe'

const items = ref<ReportUnitItem[]>([])
const loading = ref(false)
const currentMonth = ref(getCurrentMonth())

function getCurrentMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const monthDisplay = computed(() => {
  const [y, m] = currentMonth.value.split('-')
  return `${y}年${m}月`
})

function changeMonth(delta: number) {
  const [y, m] = currentMonth.value.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  currentMonth.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  load()
}

const filteredItems = computed(() => {
  const prefix = currentMonth.value
  return items.value.filter((i) => {
    const dt = i.created_at || i.submitted_at || ''
    return dt.startsWith(prefix)
  })
})

const stats = computed(() => {
  const list = filteredItems.value
  const approved = list.filter((i) => i.status === 'qc_approved').length
  const pending = list.filter((i) => i.status === 'submitted' || i.status === 'leader_approved').length
  const days = new Set(list.map((i) => (i.created_at || i.submitted_at || '').slice(0, 10)))
  return { totalQty: list.length, approved, pending, dayCount: days.size }
})

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

const groupedItems = computed(() => {
  const map = new Map<string, ReportUnitItem[]>()
  for (const item of filteredItems.value) {
    const dateKey = (item.created_at || item.submitted_at || '').slice(0, 10)
    if (!dateKey) continue
    const arr = map.get(dateKey) || []
    arr.push(item)
    map.set(dateKey, arr)
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => (a > b ? -1 : 1))
    .map(([date, groupItems]) => {
      const d = new Date(date)
      const weekday = WEEKDAYS[d.getDay() || 0]
      const approvedCount = groupItems.filter((i) => i.status === 'qc_approved').length
      return {
        date,
        displayDate: `${date} 周${weekday}`,
        items: groupItems,
        count: groupItems.length,
        approvedCount,
      }
    })
})

onShow(() => {
  load()
  smartAutoSubscribe('emp-report', [
    'report.leader_approved',
    'report.qc_approved',
    'report.rejected',
  ]).catch(() => {})
})

async function load() {
  loading.value = true
  try {
    const r = await getMyReportUnits({ limit: 200 })
    items.value = (r.items || []).filter((i) => i.status !== 'draft')
  } finally {
    loading.value = false
  }
}

onPullDownRefresh(() => {
  load().finally(() => uni.stopPullDownRefresh())
})
</script>

<style scoped lang="scss">
// 月份切换
.month-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $space-4 $space-5;
}
.month-arrow {
  font-size: $text-md;
  color: $brand-600;
  padding: $space-1 $space-3;
  border-radius: $radius-sm;
  transition: background $dur-fast $ease-smooth;
  &:active { background: $brand-50; }
}
.month-text {
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-800;
  min-width: 160rpx;
  text-align: center;
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

// 日期分组
.day-group {
  margin-bottom: $space-5;
}
.day-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: $space-3 $space-2;
  margin-bottom: $space-3;
}
.day-date {
  font-size: $text-sm;
  font-weight: $fw-bold;
  color: $slate-700;
}
.day-stats {
  display: flex;
  gap: $space-2;
}
.day-badge {
  font-size: $text-xs;
  color: $slate-600;
  background: $slate-100;
  padding: 4rpx 14rpx;
  border-radius: $radius-pill;
  font-weight: $fw-medium;
}
.day-badge.ok-badge {
  background: $success-bg;
  color: $success-deep;
}
</style>
