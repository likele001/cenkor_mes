<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="month" class="search" placeholder="YYYY-MM" @confirm="reload" />
      <button class="btn" size="mini" @tap="reload">查询</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无工资条" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.user_full_name || item.username || `员工#${item.user_id}` }}</text>
          <text :class="['adm-list-badge', item.confirmed_at ? 'tone-success' : 'tone-active']">
            {{ item.confirmed_at ? '已确认' : '待确认' }}
          </text>
        </view>
        <AdminKvGrid :rows="[
          { label: '合计', value: `¥${fmt(item.total_amount)}` },
          { label: '月份', value: month || '—' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="onSelect(item)">查看</button>
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
import { productionAdminApi } from '@/api/admin/production'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const month = ref('')
const items = ref<{ id: number; user_id: number; total_amount?: number; confirmed_at?: string | null; user_full_name?: string; username?: string }[]>([])
const loading = ref(false)

onShow(async () => {
  if (!requirePermission('salary.manage')) return
  const d = new Date()
  month.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  await reload()
})

function fmt(v?: number) {
  return Number(v || 0).toFixed(2)
}

async function reload() {
  loading.value = true
  try {
    const r = await productionAdminApi.listSalarySlips({ month: month.value.trim(), limit: 50 })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onSelect(row: { id: number; confirmed_at?: string | null }) {
  if (row.confirmed_at) {
    uni.showModal({
      title: '重置确认',
      content: '该工资条员工已确认，是否重置？',
      success: async (res) => {
        if (!res.confirm) return
        await productionAdminApi.resetSalarySlipConfirm(row.id)
        uni.showToast({ title: '已重置', icon: 'success' })
        await reload()
      },
    })
    return
  }
  uni.showToast({ title: '员工尚未确认', icon: 'none' })
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.btn { background: #4338ca; color: #fff; border-radius: 999rpx; }
</style>
