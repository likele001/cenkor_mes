<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索商机" @confirm="reload" />
      <button class="refresh" size="mini" @tap="reload">刷新</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="公海暂无商机" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.title || item.code }}</text>
          <text class="adm-list-badge tone-active">{{ item.stage || '公海' }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '客户', value: item.customer_name || '—' },
          { label: '阶段', value: item.stage || '—' },
          { label: '金额', value: `¥${item.amount ?? 0}` },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn success" @tap="claim(item)">认领</button>
        </view>
      </template>
    </MListLayout>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { apiGet, apiPost } from '@/api/request'
import { usePermission } from '@/composables/usePermission'

type Opp = { id: number; title?: string; code?: string; customer_name?: string; stage?: string; amount?: number }

const { requirePermission } = usePermission()
const items = ref<Opp[]>([])
const loading = ref(false)
const keyword = ref('')

onShow(async () => {
  const { hasPermission } = usePermission()
  if (!hasPermission('customer.manage') && !hasPermission('crm.sales')) {
    requirePermission('crm.sales')
    return
  }
  await reload()
})

async function reload() {
  loading.value = true
  try {
    const r = await apiGet<{ items: Opp[] }>('/admin/production/crm/public-pool/opportunities', { limit: 50, keyword: keyword.value.trim() || undefined }, true)
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function claim(row: Opp) {
  uni.showModal({
    title: '认领商机',
    content: `确认认领「${row.title || row.code}」？`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        await apiPost(`/admin/production/crm/public-pool/opportunities/${row.id}/claim`, {}, true)
        uni.showToast({ title: '认领成功', icon: 'success' })
        await reload()
      } catch (e: unknown) {
        uni.showToast({ title: (e as Error).message || '认领失败', icon: 'none' })
      }
    },
  })
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.refresh { background: #f1f5f9; color: #475569; border-radius: 999rpx; }
.act { display: block; font-size: 24rpx; color: #4338ca; margin-top: 8rpx; }
</style>
