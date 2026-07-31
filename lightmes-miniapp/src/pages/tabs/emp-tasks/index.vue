<template>
  <view class="emp-page">
    <view class="page-head">
      <text class="page-title">我的任务</text>
      <text class="refresh" @tap="load(true)">↻</text>
    </view>

    <view class="emp-card overview">
      <view class="overview-top">
        <text class="overview-title">任务概览</text>
        <text class="count-badge">{{ stats.total }} 个任务</text>
      </view>
      <view class="emp-stat-grid">
        <view class="stat-item">
          <view class="stat-val">{{ stats.working }}</view>
          <view class="stat-lbl">进行中</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ stats.done }}</view>
          <view class="stat-lbl">已完成</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ stats.qty }}</view>
          <view class="stat-lbl">总数量</view>
        </view>
      </view>
    </view>

    <scroll-view scroll-x class="tabs">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: statusFilter === tab.key }"
        @tap="onTab(tab.key)"
      >
        {{ tab.label }}
      </view>
    </scroll-view>

    <view v-if="loading" class="emp-empty">加载中...</view>
    <EmpTaskCard
      v-for="t in filteredItems"
      :key="t.task_code"
      :task="t"
      @tap="goDetail(t.task_code)"
      @report="goReport(t)"
    />
    <view v-if="!loading && !filteredItems.length" class="emp-empty">暂无任务</view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import EmpTaskCard from '@/components/employee-ui/EmpTaskCard.vue'
import { getMyTasks, type H5Task } from '@/api/h5/tasks'

const items = ref<H5Task[]>([])
const loading = ref(false)
const statusFilter = ref('')

const tabs = [
  { key: '', label: '全部' },
  { key: 'pending', label: '待开始' },
  { key: 'working', label: '进行中' },
  { key: 'done', label: '已完成' },
]

const filteredItems = computed(() => {
  if (!statusFilter.value) return items.value
  return items.value.filter((t) => t.status === statusFilter.value)
})

const stats = computed(() => {
  const total = items.value.length
  const working = items.value.filter((t) => t.status === 'working' || t.status === 'pending').length
  const done = items.value.filter((t) => t.status === 'done').length
  const qty = items.value.reduce((s, t) => s + (t.assigned_qty ?? 0), 0)
  return { total, working, done, qty }
})

onShow(() => load())

async function load(refresh = false) {
  loading.value = true
  try {
    const r = await getMyTasks({ limit: 100 })
    items.value = r.items || []
    if (refresh) uni.showToast({ title: '已刷新', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function onTab(key: string) {
  statusFilter.value = key
}

function goDetail(code: string) {
  uni.navigateTo({ url: `/pages-employee/task/detail/index?code=${encodeURIComponent(code)}` })
}

function goReport(t: H5Task) {
  const url = t.use_unit_report
    ? `/pages-employee/report/unit/index?task_code=${encodeURIComponent(t.task_code)}`
    : `/pages-employee/report/scan/index?task_code=${encodeURIComponent(t.task_code)}`
  uni.navigateTo({ url })
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
  padding: 8rpx 16rpx;
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
  color: #334155;
}
.count-badge {
  font-size: 22rpx;
  color: #64748b;
  background: #f1f5f9;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
}
.tabs {
  white-space: nowrap;
  margin-bottom: 20rpx;
}
.tab {
  display: inline-block;
  padding: 12rpx 28rpx;
  margin-right: 12rpx;
  border-radius: 999rpx;
  font-size: 26rpx;
  color: #64748b;
  background: #fff;
  border: 1rpx solid #e2e8f0;
}
.tab.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
</style>
