<template>
  <view class="adm-page">
    <MListLayout :items="items" :loading="loading" empty-text="暂无订单进度" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.code }}</text>
          <text class="adm-list-badge" :class="warningTone(item.warning_level)">{{ progressText(item) }}</text>
        </view>
        <AdminKvGrid :rows="kanbanKvRows(item)" />
        <view class="adm-progress-wrap">
          <view class="adm-progress-meta"><text>完成率</text><text>{{ kanbanPct(item) }}%</text></view>
          <view class="adm-progress-bar"><view class="adm-progress-fill" :style="{ width: `${kanbanPct(item)}%` }" /></view>
        </view>
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="openDetail(item)">详情</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="detailVisible" class="mask" @tap="detailVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <view class="head-top">
            <text class="title">{{ detail?.code }}</text>
            <text class="close" @tap="detailVisible = false">关闭</text>
          </view>
        </view>
        <scroll-view scroll-y class="body">
          <view class="kv"><text class="k">客户</text><text class="v">{{ detail?.customer?.name }}</text></view>
          <view class="kv"><text class="k">进度</text><text class="v">{{ detail?.done_qty }}/{{ detail?.total_qty }}</text></view>

          <view class="section">工序进度</view>
          <view v-if="processList.length" class="ring-row">
            <RingProgress
              v-for="p in processList"
              :key="p.processId"
              :percentage="toPercent(p.progress)"
              :label="p.processName"
              :sub="`${p.doneQty}/${p.totalQty}`"
              :size="110"
              :color="ringColor(p.progress)"
            />
          </view>
          <text v-else class="empty-hint">暂无工序数据</text>

          <view class="section">工单与任务</view>
          <view v-for="wo in detail?.work_orders || []" :key="wo.id" class="wo">
            <text class="wo-title">{{ wo.sku?.display_label || wo.sku?.name || `工单#${wo.id}` }}</text>
            <text v-for="t in wo.tasks || []" :key="t.id" class="task">{{ t.seq }}. {{ t.process?.name || t.task_code }} · {{ t.done_qty ?? 0 }}/{{ t.planned_qty }}</text>
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
import RingProgress from '@/components/admin-ui/RingProgress.vue'
import { dashboardAdminApi, type KanbanOrder, type KanbanOrderDetail } from '@/api/admin/dashboard'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<KanbanOrder[]>([])
const loading = ref(false)
const detailVisible = ref(false)
const detail = ref<KanbanOrderDetail | null>(null)

type ProcessProgress = {
  processId: number
  processName: string
  totalQty: number
  doneQty: number
  progress: number | null
}

const processList = computed<ProcessProgress[]>(() => {
  const d = detail.value
  if (!d?.work_orders) return []
  const map = new Map<number, ProcessProgress>()
  for (const wo of d.work_orders) {
    for (const t of wo.tasks || []) {
      if (!t.process?.name) continue
      const pid = t.process.name
      const existing = [...map.values()].find(p => p.processName === pid)
      if (existing) {
        existing.totalQty += t.planned_qty ?? 0
        existing.doneQty += t.done_qty ?? 0
      } else {
        map.set(t.id ?? 0, {
          processId: t.id ?? 0,
          processName: pid,
          totalQty: t.planned_qty ?? 0,
          doneQty: t.done_qty ?? 0,
          progress: null,
        })
      }
    }
  }
  const result = Array.from(map.values())
  for (const p of result) {
    p.progress = p.totalQty > 0 ? (p.doneQty / p.totalQty) * 100 : 0
  }
  return result
})

function toPercent(v: number | null) {
  if (typeof v !== 'number') return 0
  return Math.max(0, Math.min(100, Math.round(v)))
}

function ringColor(progress: number | null) {
  const p = progress ?? 0
  if (p >= 100) return '#10b981'
  if (p >= 50) return '#f59e0b'
  return '#ef4444'
}

function kanbanPct(item: KanbanOrder) {
  if (item.progress != null) return Math.round(item.progress * 100)
  const total = Number(item.total_qty || 0)
  const done = Number(item.done_qty || 0)
  return total > 0 ? Math.round((done / total) * 100) : 0
}

function warningTone(level?: string) {
  if (level === 'overdue') return 'tone-danger'
  if (level === 'warn') return 'tone-pending'
  return 'tone-success'
}

function kanbanKvRows(item: KanbanOrder) {
  return [
    { label: '客户名称', value: item.customer?.name || '—' },
    { label: '订单数量', value: String(item.total_qty ?? 0) },
    { label: '完成数量', value: String(item.done_qty ?? 0) },
    { label: '交货日期', value: item.due_date ? String(item.due_date).slice(0, 10) : '未设置' },
    { label: '状态', value: orderStatusLabel(item.status) },
  ]
}

function progressText(item: KanbanOrder) {
  return `${kanbanPct(item)}%`
}
function orderStatusLabel(s: string) {
  return ({ draft: '草稿', confirmed: '已确认', in_production: '生产中', completed: '已完成' } as Record<string, string>)[s] || s
}

async function reload() {
  loading.value = true
  try {
    const r = await dashboardAdminApi.kanbanOrders({ limit: 50 })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function openDetail(row: KanbanOrder) {
  try {
    detail.value = await dashboardAdminApi.kanbanOrder(row.id)
    detailVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}
</script>

<style scoped lang="scss">
.row-head { display: flex; justify-content: space-between; align-items: center; }
.tag { font-size: 22rpx; padding: 4rpx 12rpx; border-radius: 999rpx; background: #ecfdf5; color: #059669; }
.tag.warn { background: #fef3c7; color: #b45309; }
.tag.overdue { background: #fee2e2; color: #b91c1c; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 80vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.head-top { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 32rpx; font-weight: 700; }
.close { font-size: 26rpx; color: #64748b; }
.body { max-height: 60vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.kv { display: flex; gap: 16rpx; margin-bottom: 12rpx; font-size: 26rpx; }
.k { color: #64748b; width: 100rpx; }
.v { flex: 1; }
.section { font-weight: 600; font-size: 26rpx; margin: 20rpx 0 12rpx; }
.empty-hint { display: block; font-size: 24rpx; color: #94a3b8; padding: 8rpx 0; }
.ring-row { display: flex; flex-wrap: wrap; gap: 16rpx; padding: 8rpx 0; }
.wo { margin-bottom: 16rpx; padding: 12rpx; background: #f8fafc; border-radius: 12rpx; }
.wo-title { display: block; font-weight: 600; font-size: 28rpx; margin-bottom: 8rpx; }
.task { display: block; font-size: 24rpx; color: #64748b; padding: 4rpx 0; }
</style>
