<template>
  <view class="adm-page">
    <!-- 搜索和状态筛选 -->
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索工单" @confirm="applyFilter" />
    </view>
    <scroll-view scroll-x class="tabs">
      <view
        v-for="tab in statusTabs"
        :key="tab.key"
        class="tab"
        :class="{ active: statusFilter === tab.key }"
        @tap="statusFilter = tab.key; applyFilter()"
      >
        {{ tab.label }}
      </view>
    </scroll-view>

    <!-- 统计概览 -->
    <view v-if="!loading && allItems.length" class="adm-card overview">
      <view class="adm-stat-grid">
        <view class="stat-item">
          <text class="stat-val">{{ allItems.length }}</text>
          <text class="stat-lbl">总工单</text>
        </view>
        <view class="stat-item">
          <text class="stat-val">{{ inProgressCount }}</text>
          <text class="stat-lbl">进行中</text>
        </view>
        <view class="stat-item">
          <text class="stat-val">{{ doneCount }}</text>
          <text class="stat-lbl">已完成</text>
        </view>
      </view>
    </view>

    <MListLayout :items="items" :loading="loading" empty-text="暂无工单" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">工单 #{{ item.id }}</text>
          <text class="adm-list-badge" :class="woTone(String(item.status))">{{ woStatusLabel(String(item.status)) }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '订单', value: String(item.order_id) },
          { label: '型号', value: skuLabel(item) },
          { label: '数量', value: `${item.qty} 件` },
          { label: '创建时间', value: item.created_at ? String(item.created_at).slice(0, 16).replace('T', ' ') : '—' },
        ]" />
        <!-- 进度条 -->
        <view v-if="item.tasks && item.tasks.length" class="progress-row">
          <view class="progress-bar">
            <view class="progress-fill" :style="{ width: woProgress(item) + '%' }" />
          </view>
          <text class="progress-text">{{ woProgress(item) }}%</text>
        </view>
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn success" @tap="openDetail(item)">详情</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="detailVisible" class="mask" @tap="detailVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">工单 #{{ detail?.id }}</text></view>
        <scroll-view scroll-y class="body">
          <view class="kv"><text class="k">订单</text><text class="v">{{ detail?.order_id }}</text></view>
          <view class="kv"><text class="k">型号</text><text class="v">{{ skuLabel(detail!) }}</text></view>
          <view class="kv"><text class="k">数量</text><text class="v">{{ detail?.qty }}</text></view>
          <view class="kv"><text class="k">状态</text><text class="v">{{ woStatusLabel(String(detail?.status)) }}</text></view>

          <!-- 时间线 -->
          <view v-if="detail" class="section-title">时间线</view>
          <view v-if="detail?.created_at" class="tl-item">
            <text class="tl-dot" />
            <view class="tl-content">
              <text class="tl-label">创建</text>
              <text class="tl-time">{{ String(detail.created_at).slice(0, 16).replace('T', ' ') }}</text>
            </view>
          </view>
          <view v-if="detail?.started_at" class="tl-item">
            <text class="tl-dot active" />
            <view class="tl-content">
              <text class="tl-label">开工</text>
              <text class="tl-time">{{ String(detail.started_at).slice(0, 16).replace('T', ' ') }}</text>
            </view>
          </view>
          <view v-if="detail?.completed_at" class="tl-item">
            <text class="tl-dot done" />
            <view class="tl-content">
              <text class="tl-label">完成</text>
              <text class="tl-time">{{ String(detail.completed_at).slice(0, 16).replace('T', ' ') }}</text>
            </view>
          </view>

          <view v-if="tasks.length" class="section-title">工序任务</view>
          <view v-for="t in tasks" :key="t.id" class="line">
            <text>{{ t.seq }}. {{ t.process?.name || t.task_code }} · {{ t.status }} · {{ t.done_qty ?? 0 }}/{{ t.planned_qty }}</text>
          </view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { adminApi } from '@/api/admin/index'
import { productionAdminApi } from '@/api/admin/production'
import { usePermission } from '@/composables/usePermission'

type Wo = {
  id: number
  order_id: number
  qty: number
  status: string
  sku_id?: number
  sku?: { name?: string; display_label?: string; code?: string }
  created_at?: string
  started_at?: string
  completed_at?: string
  tasks?: { id: number; seq?: number; task_code?: string; status: string; planned_qty?: number; done_qty?: number; process?: { name?: string } }[]
}

const { requirePermission } = usePermission()
const allItems = ref<Wo[]>([])
const items = ref<Wo[]>([])
const loading = ref(false)
const keyword = ref('')
const statusFilter = ref('')
const detailVisible = ref(false)
const detail = ref<Wo | null>(null)

const statusTabs = [
  { key: '', label: '全部' },
  { key: 'open', label: '待处理' },
  { key: 'in_progress', label: '进行中' },
  { key: 'done', label: '已完成' },
]

const inProgressCount = computed(() => allItems.value.filter((i) => i.status === 'in_progress').length)
const doneCount = computed(() => allItems.value.filter((i) => i.status === 'done').length)

const tasks = computed(() => {
  const d = detail.value as Record<string, unknown> | null
  return (d?.tasks as Wo['tasks']) || []
})

onShow(async () => {
  if (!requirePermission('work.manage')) return
  await reload()
})

function skuLabel(item: Wo) {
  return item.sku?.display_label || item.sku?.name || item.sku?.code || `#${item.sku_id}`
}

function woStatusLabel(s: string) {
  const map: Record<string, string> = { open: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消' }
  return map[s] || s
}

function woTone(s: string) {
  if (s === 'done') return 'tone-success'
  if (s === 'in_progress') return 'tone-active'
  if (s === 'cancelled') return 'tone-muted'
  return 'tone-warn'
}

function woProgress(item: Wo) {
  if (!item.tasks?.length) return 0
  const total = item.tasks.reduce((s, t) => s + (t.planned_qty ?? 0), 0)
  const done = item.tasks.reduce((s, t) => s + (t.done_qty ?? 0), 0)
  if (!total) return 0
  return Math.min(100, Math.round((done / total) * 100))
}

async function reload() {
  loading.value = true
  try {
    const r = await adminApi.listWorkOrders({ limit: 50 })
    allItems.value = (r.items || []) as Wo[]
    applyFilter()
  } catch {
    allItems.value = []
    items.value = []
  } finally {
    loading.value = false
  }
}

function applyFilter() {
  let list = allItems.value
  if (statusFilter.value) {
    list = list.filter((i) => i.status === statusFilter.value)
  }
  const kw = keyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter((i) => String(i.id).includes(kw) || String(i.order_id).includes(kw))
  }
  items.value = list
}

async function openDetail(row: Wo) {
  try {
    detail.value = (await productionAdminApi.getWorkOrder(row.id)) as Wo
    detailVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 16rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; box-shadow: 0 2rpx 12rpx rgba(15,23,42,.04); }
.tabs { white-space: nowrap; margin-bottom: 16rpx; }
.tab { display: inline-block; padding: 10rpx 24rpx; margin-right: 12rpx; border-radius: 999rpx; font-size: 24rpx; color: #64748b; background: #fff; border: 1rpx solid #e2e8f0; }
.tab.active { background: #2563eb; color: #fff; border-color: #2563eb; }
.overview { padding: 20rpx 24rpx; }
.adm-stat-grid { display: flex; gap: 12rpx; }
.stat-item { flex: 1; text-align: center; background: #f8fafc; border-radius: 12rpx; padding: 16rpx 8rpx; }
.stat-val { display: block; font-size: 32rpx; font-weight: 700; color: #1e293b; }
.stat-lbl { display: block; font-size: 22rpx; color: #64748b; margin-top: 4rpx; }
.progress-row { display: flex; align-items: center; gap: 12rpx; margin-top: 12rpx; }
.progress-bar { flex: 1; height: 12rpx; background: #e2e8f0; border-radius: 999rpx; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #22c55e, #16a34a); border-radius: 999rpx; }
.progress-text { font-size: 22rpx; font-weight: 600; color: #15803d; min-width: 60rpx; text-align: right; }
.tone-success { background: #dcfce7 !important; color: #15803d !important; }
.tone-active { background: #dbeafe !important; color: #2563eb !important; }
.tone-warn { background: #fef3c7 !important; color: #b45309 !important; }
.tone-muted { background: #f1f5f9 !important; color: #94a3b8 !important; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 75vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 55vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.kv { display: flex; gap: 16rpx; margin-bottom: 12rpx; font-size: 26rpx; }
.k { color: #64748b; width: 120rpx; }
.v { flex: 1; }
.section-title { font-size: 28rpx; font-weight: 600; margin: 20rpx 0 12rpx; }
.line { font-size: 26rpx; padding: 10rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.tl-item { display: flex; align-items: flex-start; gap: 16rpx; margin-bottom: 16rpx; position: relative; padding-left: 24rpx; }
.tl-dot { width: 16rpx; height: 16rpx; border-radius: 50%; background: #cbd5e1; position: absolute; left: 0; top: 6rpx; }
.tl-dot.active { background: #2563eb; }
.tl-dot.done { background: #22c55e; }
.tl-content { display: flex; gap: 16rpx; }
.tl-label { font-size: 26rpx; color: #334155; }
.tl-time { font-size: 24rpx; color: #94a3b8; }
</style>
