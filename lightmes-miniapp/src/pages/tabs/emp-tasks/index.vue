<template>
  <view class="emp-page">
    <view class="emp-page-head">
      <text class="emp-page-title">我的任务</text>
      <view class="emp-page-action" @tap="load(true)">↻</view>
    </view>

    <!-- 概览渐变卡 -->
    <view class="emp-card emp-card--brand overview-card">
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

    <!-- 横向筛选 tab -->
    <scroll-view scroll-x class="emp-tabs">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        class="emp-tab"
        :class="{ active: statusFilter === tab.key }"
        @tap="onTab(tab.key)"
      >
        {{ tab.label }}
      </view>
    </scroll-view>

    <view v-if="loading" class="emp-empty">
      <text class="emp-empty-icon">◌</text>
      加载中...
    </view>
    <EmpTaskCard
      v-for="t in filteredItems"
      :key="t.task_code"
      :task="t"
      @tap="goDetail(t.task_code)"
      @report="goReport(t)"
    />
    <view v-if="!loading && !filteredItems.length" class="emp-empty">
      <text class="emp-empty-icon">✓</text>
      暂无任务
    </view>
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
  backdrop-filter: blur(8rpx);
}
</style>
