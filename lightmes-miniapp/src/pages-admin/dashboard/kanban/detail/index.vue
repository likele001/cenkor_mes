<template>
  <view class="adm-page">
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="detail" class="adm-card">
      <text class="title">{{ detail.code }}</text>
      <text class="sub">{{ detail.customer?.name || '—' }} · 交期 {{ detail.due_date || '—' }}</text>
      <view class="kv"><text class="k">进度</text><text class="v">{{ detail.done_qty ?? 0 }}/{{ detail.total_qty ?? 0 }}</text></view>
      <view class="kv"><text class="k">状态</text><text class="v">{{ orderStatusLabel(detail.status) }}</text></view>

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
      <view v-for="wo in detail.work_orders || []" :key="wo.id" class="wo">
        <text class="wo-title">{{ wo.sku?.display_label || wo.sku?.name || `工单#${wo.id}` }}</text>
        <text v-for="t in wo.tasks || []" :key="t.id" class="task">
          {{ t.seq }}. {{ t.process?.name || t.task_code }} · {{ t.done_qty ?? 0 }}/{{ t.planned_qty }}
        </text>
      </view>
    </view>
    <view v-else class="loading">未找到订单进度</view>
  </view>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { dashboardAdminApi, type KanbanOrderDetail } from '@/api/admin/dashboard'
import { usePermission } from '@/composables/usePermission'
import RingProgress from '@/components/admin-ui/RingProgress.vue'

const detail = ref<KanbanOrderDetail | null>(null)
const loading = ref(true)
const { requirePermission } = usePermission()

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
      const key = t.seq ?? 0
      const id = key * 1000 + Math.random()
      const existing = [...map.values()].find(p => p.processName === pid)
      if (existing) {
        existing.totalQty += t.planned_qty ?? 0
        existing.doneQty += t.done_qty ?? 0
      } else {
        map.set((t.id ?? 0) * 1000 + (t.seq ?? 0), {
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

function orderStatusLabel(s: string) {
  return ({ draft: '草稿', confirmed: '已确认', in_production: '生产中', completed: '已完成' } as Record<string, string>)[s] || s
}

onLoad(async (q) => {
  requirePermission('dashboard.view')
  const id = Number(q?.id || 0)
  if (!id) {
    loading.value = false
    return
  }
  try {
    detail.value = await dashboardAdminApi.kanbanOrder(id)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
})
</script>
<style scoped>
.loading { padding: 40rpx; text-align: center; color: #94a3b8; }
.title { display: block; font-size: 32rpx; font-weight: 700; }
.sub { display: block; font-size: 26rpx; color: #64748b; margin: 12rpx 0 20rpx; }
.kv { display: flex; justify-content: space-between; font-size: 26rpx; padding: 10rpx 0; }
.k { color: #94a3b8; }
.section { font-weight: 600; margin: 20rpx 0 12rpx; }
.empty-hint { display: block; font-size: 24rpx; color: #94a3b8; padding: 12rpx 0; }
.ring-row { display: flex; flex-wrap: wrap; gap: 16rpx; padding: 8rpx 0; }
.wo { margin-bottom: 16rpx; padding-bottom: 12rpx; border-bottom: 1rpx solid #f1f5f9; }
.wo-title { display: block; font-weight: 600; font-size: 26rpx; margin-bottom: 8rpx; }
.task { display: block; font-size: 24rpx; color: #64748b; line-height: 1.6; }
</style>
