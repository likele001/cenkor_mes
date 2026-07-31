<template>
  <view class="emp-page">
    <view class="page-head">
      <text class="page-title">报工记录</text>
      <text class="refresh" @tap="load">↻</text>
    </view>

    <!-- 月份选择器 -->
    <view class="month-bar">
      <text class="month-arrow" @tap="changeMonth(-1)">◀</text>
      <text class="month-text">{{ currentMonth }}</text>
      <text class="month-arrow" @tap="changeMonth(1)">▶</text>
    </view>

    <!-- 概览统计 -->
    <view class="emp-card overview">
      <view class="overview-top">
        <text class="overview-title">本月概览</text>
        <text class="count-badge">{{ filteredItems.length }} 条记录</text>
      </view>
      <view class="emp-stat-grid">
        <view class="stat-item">
          <view class="stat-val">{{ stats.totalQty }}</view>
          <view class="stat-lbl">总报工数</view>
        </view>
        <view class="stat-item">
          <view class="stat-val ok">{{ stats.approved }}</view>
          <view class="stat-lbl">已通过</view>
        </view>
        <view class="stat-item">
          <view class="stat-val warn">{{ stats.pending }}</view>
          <view class="stat-lbl">待审核</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ stats.dayCount }}</view>
          <view class="stat-lbl">工作天数</view>
        </view>
      </view>
    </view>

    <!-- 按日期分组 -->
    <view v-for="group in groupedItems" :key="group.date" class="day-group">
      <view class="day-head">
        <text class="day-date">{{ group.displayDate }}</text>
        <view class="day-stats">
          <text class="day-badge">{{ group.count }} 件</text>
          <text v-if="group.approvedCount" class="day-badge ok">{{ group.approvedCount }} 通过</text>
        </view>
      </view>
      <EmpRecordCard v-for="u in group.items" :key="u.id" :item="u" />
    </view>

    <view v-if="!filteredItems.length && !loading" class="emp-empty">
      <text class="empty-icon">📋</text>
      <text class="empty-text">本月暂无报工记录</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { onPullDownRefresh } from '@dcloudio/uni-app'
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
  const groups = Array.from(map.entries())
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
  return groups
})

onShow(() => {
  load()
  // 报工历史页：订阅审核结果
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
  padding: 8rpx 16rpx;
}

/* 月份选择器 */
.month-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32rpx;
  background: #fff;
  border-radius: 12rpx;
  padding: 16rpx;
  margin-bottom: 20rpx;
}
.month-arrow {
  font-size: 28rpx;
  color: #2563eb;
  padding: 8rpx 16rpx;
}
.month-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #1e293b;
  min-width: 180rpx;
  text-align: center;
}

.overview-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
.ok {
  color: #15803d;
}
.warn {
  color: #b45309;
}

/* 日期分组 */
.day-group {
  margin-bottom: 20rpx;
}
.day-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12rpx 8rpx;
  border-bottom: 1rpx solid #e2e8f0;
}
.day-date {
  font-size: 26rpx;
  font-weight: 600;
  color: #334155;
}
.day-stats {
  display: flex;
  gap: 12rpx;
}
.day-badge {
  font-size: 22rpx;
  color: #64748b;
  background: #f1f5f9;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}
.day-badge.ok {
  background: #dcfce7;
  color: #15803d;
}

/* 空状态 */
.emp-empty {
  text-align: center;
  padding: 60rpx 0;
}
.empty-icon {
  display: block;
  font-size: 60rpx;
  margin-bottom: 16rpx;
}
.empty-text {
  font-size: 26rpx;
  color: #94a3b8;
}
</style>
