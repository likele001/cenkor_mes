<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="month" class="search" placeholder="月份 YYYY-MM" @confirm="reload" />
      <button class="refresh" size="mini" @tap="reload">查询</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无工资数据" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.user_name || item.full_name || item.username || `#${item.user_id}` }}</text>
          <text class="adm-list-badge tone-active">¥{{ item.total_amount ?? item.total ?? 0 }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '计件工资', value: `¥${item.piece_amount ?? item.amount ?? 0}` },
          { label: '合计', value: `¥${item.total_amount ?? item.total ?? 0}` },
          { label: '月份', value: month || '—' },
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
import { apiGet } from '@/api/request'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<Record<string, unknown>[]>([])
const loading = ref(false)
const month = ref('')

onShow(async () => {
  if (!requirePermission('salary.manage')) return
  const d = new Date()
  month.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  await reload()
})

async function reload() {
  loading.value = true
  try {
    const r = await apiGet<{ items: Record<string, unknown>[] }>(
      '/admin/production/reports/salary/summary',
      { month: month.value.trim() || undefined },
      true,
    )
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
.refresh { background: #f1f5f9; color: #475569; border-radius: 999rpx; }
</style>
