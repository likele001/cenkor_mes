<template>
  <view class="adm-page">
    <!-- 顶部统计 -->
    <view class="stats-bar">
      <view class="stats-item">
        <view class="stats-val">{{ allItems.length }}</view>
        <view class="stats-lbl">全部</view>
      </view>
      <view class="stats-item">
        <view class="stats-val active">{{ countByStatus('pending') }}</view>
        <view class="stats-lbl">待开始</view>
      </view>
      <view class="stats-item">
        <view class="stats-val working">{{ countByStatus('working') }}</view>
        <view class="stats-lbl">进行中</view>
      </view>
      <view class="stats-item">
        <view class="stats-val done">{{ countByStatus('done') }}</view>
        <view class="stats-lbl">已完成</view>
      </view>
    </view>

    <!-- 搜索栏 -->
    <view class="search-bar">
      <input
        class="search-input"
        v-model="searchText"
        placeholder="搜索任务码 / 型号"
        confirm-type="search"
        @input="onSearch"
      />
      <text v-if="searchText" class="search-clear" @tap="clearSearch">✕</text>
    </view>

    <!-- 状态筛选 -->
    <view class="filter-tabs">
      <view
        v-for="tab in TABS"
        :key="tab.key"
        class="filter-tab"
        :class="{ active: activeTab === tab.key }"
        @tap="activeTab = tab.key"
      >
        <text>{{ tab.label }}</text>
        <text class="filter-count">{{ countForTab(tab.key) }}</text>
      </view>
    </view>

    <!-- 列表 -->
    <MListLayout :items="filteredItems" :loading="loading" empty-text="暂无匹配任务" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ taskTitle(item) }}</text>
          <text class="adm-list-badge" :class="statusTone(item.status)">{{ statusLabel(item.status) }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '工序', value: processLabel(item) },
          { label: '订单', value: orderLabel(item) },
          { label: '计划数量', value: `${item.planned_qty} 件` },
          { label: '派工情况', value: assignText(item) },
        ]" />
        <!-- 进度条 -->
        <view class="progress-row">
          <view class="progress-bar-wrap">
            <view class="progress-bar" :style="{ width: progressPct(item) + '%' }" />
          </view>
          <text class="progress-text">{{ progressPct(item) }}%</text>
        </view>
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="openDetail(item)">详情</button>
          <button class="adm-card-btn edit" @tap="goAssign(item)">派工</button>
        </view>
      </template>
    </MListLayout>

    <!-- 详情弹窗 -->
    <view v-if="detailVisible" class="mask" @tap="detailVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">{{ taskTitle(detail!) }}</text></view>
        <scroll-view scroll-y class="body">
          <view class="kv"><text class="k">任务码</text><text class="v">{{ detail?.task_code }}</text></view>
          <view class="kv"><text class="k">订单</text><text class="v">{{ orderLabel(detail!) }}</text></view>
          <view class="kv"><text class="k">型号</text><text class="v">{{ skuLabel(detail!) }}</text></view>
          <view class="kv"><text class="k">工序</text><text class="v">{{ processLabel(detail!) }}</text></view>
          <view class="kv"><text class="k">计划</text><text class="v">{{ detail?.planned_qty }}</text></view>
          <view class="kv"><text class="k">状态</text><text class="v">{{ statusLabel(detail?.status || '') }}</text></view>
          <view class="kv"><text class="k">进度</text><text class="v">{{ progressPct(detail!) }}%</text></view>
        </scroll-view>
        <view class="foot">
          <button class="btn primary" @tap="goAssign">去派工</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow, onUnload } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { productionAdminApi, type TaskOut } from '@/api/admin/production'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const allItems = ref<TaskOut[]>([])
const loading = ref(false)
const detailVisible = ref(false)
const detail = ref<TaskOut | null>(null)
const searchText = ref('')
const activeTab = ref('all')

const STATUS: Record<string, string> = {
  pending: '待开始',
  working: '进行中',
  done: '已完成',
}

const STATUS_TONE: Record<string, string> = {
  pending: 'tone-warn',
  working: 'tone-active',
  done: 'tone-ok',
}

const TABS = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待开始' },
  { key: 'working', label: '进行中' },
  { key: 'done', label: '已完成' },
]

function countByStatus(s: string) {
  return allItems.value.filter((i) => i.status === s).length
}
function countForTab(key: string) {
  if (key === 'all') return allItems.value.length
  return countByStatus(key)
}

const filteredItems = computed(() => {
  let list = allItems.value
  if (activeTab.value !== 'all') {
    list = list.filter((i) => i.status === activeTab.value)
  }
  const q = searchText.value.trim().toLowerCase()
  if (q) {
    list = list.filter((i) => {
      const code = (i.task_code || '').toLowerCase()
      const skuName = (i.sku?.display_label || i.sku?.name || i.sku?.code || '').toLowerCase()
      const orderCode = (i.order?.code || '').toLowerCase()
      return code.includes(q) || skuName.includes(q) || orderCode.includes(q)
    })
  }
  return list
})

function progressPct(item: TaskOut) {
  const planned = Number(item.planned_qty || 0)
  if (!planned) return 0
  const assigned = Number(item.assigned_total_qty || 0)
  return Math.min(100, Math.round((assigned / planned) * 100))
}

function statusTone(s: string) {
  return STATUS_TONE[s] || ''
}

function onSearch() {
  // reactive via v-model, no-op needed
}
function clearSearch() {
  searchText.value = ''
}

function upsertTaskItem(task: TaskOut) {
  const idx = allItems.value.findIndex((t) => t.id === task.id)
  if (idx >= 0) {
    allItems.value.splice(idx, 1, { ...allItems.value[idx], ...task })
  } else {
    allItems.value.unshift(task)
  }
  allItems.value = [...allItems.value]
}

function onTaskAssignUpdated(task: TaskOut) {
  upsertTaskItem(task)
}

onShow(async () => {
  if (!requirePermission('task.manage') && !requirePermission('dispatch.manage')) return
  uni.$on('admin:task-assign-updated', onTaskAssignUpdated)
  await reload()
})

onUnload(() => {
  uni.$off('admin:task-assign-updated', onTaskAssignUpdated)
})

function taskTitle(item: TaskOut) {
  return item.sku?.display_label || item.sku?.display_name || item.sku?.name || item.task_code || `#${item.id}`
}
function skuLabel(item: TaskOut) {
  const s = item.sku
  if (!s) return '—'
  return s.display_label || s.display_name || `${s.code} ${s.name || ''}`.trim()
}
function orderLabel(item: TaskOut) {
  return item.order?.code || (item.work_order?.order_id ? `#${item.work_order.order_id}` : '—')
}
function processLabel(item: TaskOut) {
  const p = item.process
  return p?.display_name || p?.name || p?.code || '工序'
}
function statusLabel(s: string) {
  return STATUS[s] || s
}
function assignText(item: TaskOut) {
  const total = Number(item.assigned_total_qty ?? 0)
  const count = item.assignments?.length ?? (total > 0 ? 1 : 0)
  if (!total && !count) return '未派工'
  return `${count}人 · ${total}/${item.planned_qty}`
}

async function reload() {
  loading.value = true
  try {
    const r = await productionAdminApi.listTasks({ limit: 100 })
    allItems.value = r.items || []
  } catch {
    allItems.value = []
  } finally {
    loading.value = false
  }
}

function openDetail(row: TaskOut) {
  detail.value = row
  detailVisible.value = true
}

function goAssign(item?: TaskOut) {
  detailVisible.value = false
  const id = item?.id ?? detail.value?.id
  uni.navigateTo({
    url: id
      ? `/pages-admin/production/task-assign/index?taskId=${id}`
      : '/pages-admin/production/task-assign/index',
  })
}
</script>

<style scoped lang="scss">
/* 顶部统计 */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
  background: #f8fafc;
  border-radius: 12rpx;
  padding: 20rpx 12rpx;
  margin-bottom: 20rpx;
}
.stats-item { text-align: center; }
.stats-val { font-size: 32rpx; font-weight: 700; color: #1e293b; }
.stats-val.active { color: #a16207; }
.stats-val.working { color: #2563eb; }
.stats-val.done { color: #15803d; }
.stats-lbl { font-size: 22rpx; color: #94a3b8; margin-top: 4rpx; }

/* 搜索栏 */
.search-bar {
  position: relative;
  margin-bottom: 16rpx;
}
.search-input {
  width: 100%;
  height: 72rpx;
  background: #f1f5f9;
  border-radius: 12rpx;
  padding: 0 60rpx 0 24rpx;
  font-size: 26rpx;
}
.search-clear {
  position: absolute;
  right: 20rpx;
  top: 50%;
  transform: translateY(-50%);
  font-size: 28rpx;
  color: #94a3b8;
  padding: 8rpx;
}

/* 状态筛选 */
.filter-tabs {
  display: flex;
  gap: 12rpx;
  margin-bottom: 20rpx;
  overflow-x: auto;
}
.filter-tab {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 12rpx 24rpx;
  border-radius: 999rpx;
  background: #f1f5f9;
  font-size: 24rpx;
  color: #64748b;
  white-space: nowrap;
  flex-shrink: 0;
}
.filter-tab.active {
  background: #2563eb;
  color: #fff;
}
.filter-count {
  font-size: 22rpx;
  opacity: 0.7;
}

/* 进度条 */
.progress-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-top: 12rpx;
}
.progress-bar-wrap {
  flex: 1;
  height: 8rpx;
  background: #e2e8f0;
  border-radius: 4rpx;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  border-radius: 4rpx;
  transition: width 0.3s;
}
.progress-text {
  font-size: 22rpx;
  color: #64748b;
  min-width: 60rpx;
  text-align: right;
}

/* 弹窗 */
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 60vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 40vh; padding: 16rpx 32rpx; }
.kv { display: flex; gap: 16rpx; margin-bottom: 12rpx; font-size: 26rpx; }
.k { color: #64748b; width: 100rpx; flex-shrink: 0; }
.v { flex: 1; word-break: break-all; }
.foot { padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); }
.btn { border-radius: 12rpx; font-size: 28rpx; }
.primary { background: #2563eb; color: #fff; }
</style>
