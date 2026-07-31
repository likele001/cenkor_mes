<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="month" class="search" placeholder="YYYY-MM" @confirm="reload" />
      <button class="btn" size="mini" @tap="reload">查询</button>
    </view>
    <view class="summary">
      <text>机会 {{ totalCount }} 个 · 金额 ¥{{ fmt(totalAmount) }}</text>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无统计" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ rowTitle(item) }}</text>
          <text class="adm-list-badge tone-active">{{ item.count ?? 0 }} 个</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '机会数', value: String(item.count ?? 0) },
          { label: '金额', value: `¥${fmt(item.amount)}` },
        ]" />
      </template>
    </MListLayout>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { dashboardAdminApi } from '@/api/admin/dashboard'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const month = ref('')
const items = ref<Record<string, unknown>[]>([])
const totalCount = ref(0)
const totalAmount = ref(0)
const loading = ref(false)

onShow(async () => {
  if (!requirePermission('customer.manage')) return
  const d = new Date()
  month.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  await reload()
})

function fmt(v: unknown) {
  return Number(v || 0).toFixed(2)
}
function stageLabel(s: string) {
  const map: Record<string, string> = { prospecting: '线索', qualified: '已评估', quoted: '已报价', negotiation: '谈判中', won: '赢单', lost: '输单' }
  return map[s] || s
}
function rowTitle(item: Record<string, unknown>) {
  if (item.stage) return stageLabel(String(item.stage))
  if (item.owner_name) return String(item.owner_name)
  if (item.customer_name) return String(item.customer_name)
  return '汇总'
}

async function reload() {
  loading.value = true
  try {
    const r = await dashboardAdminApi.crmOpportunityStats({ month: month.value.trim(), group_by: 'stage' })
    items.value = r.items || []
    totalCount.value = r.total_count ?? 0
    totalAmount.value = r.total_amount ?? 0
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 12rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.btn { background: #7c3aed; color: #fff; border-radius: 999rpx; }
.summary { font-size: 26rpx; color: #64748b; margin-bottom: 16rpx; padding: 0 8rpx; }
</style>
