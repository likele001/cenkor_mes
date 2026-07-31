<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="month" class="search" placeholder="YYYY-MM" @confirm="reload" />
      <button class="btn" size="mini" @tap="reload">查询</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无统计" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.material_name || item.material_code }}</text>
          <text class="adm-list-badge tone-active">¥{{ fmt(item.net_amount) }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '供应商', value: item.supplier_name || '—' },
          { label: '净入库', value: String(item.net_qty ?? 0) },
          { label: '金额', value: `¥${fmt(item.net_amount)}` },
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
const loading = ref(false)

onShow(async () => {
  if (!requirePermission('report.view')) return
  const d = new Date()
  month.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  await reload()
})

function fmt(v: unknown) {
  return Number(v || 0).toFixed(2)
}

async function reload() {
  loading.value = true
  try {
    const r = await dashboardAdminApi.purchaseStats({ month: month.value.trim() || undefined })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.btn { background: #059669; color: #fff; border-radius: 999rpx; }
</style>
