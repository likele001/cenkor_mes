<template>
  <view class="adm-page">
    <view class="toolbar">
      <button class="btn" size="mini" @tap="markAll">全部已读</button>
      <button class="btn ghost" size="mini" @tap="reload">刷新</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无消息" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.title || '通知' }}</text>
          <text v-if="!item.is_read" class="adm-list-badge tone-danger">未读</text>
          <text v-else class="adm-list-badge">已读</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '内容', value: item.content || '—' },
          { label: '时间', value: item.created_at?.slice(0, 16) || '—' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button v-if="!item.is_read" class="adm-card-btn primary" @tap="markOne(item)">标为已读</button>
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
import { markAllRead, markRead } from '@/api/h5/notifications'
import { adminApi } from '@/api/admin/index'
import { useAuthStore } from '@/stores/auth'
import { usePermission } from '@/composables/usePermission'

type N = { id: number; title?: string; content?: string; is_read?: boolean; created_at?: string }

const { requirePermission } = usePermission()
const auth = useAuthStore()
const items = ref<N[]>([])
const loading = ref(false)

onShow(async () => {
  if (!requirePermission('notification.view')) return
  await reload()
})

async function reload() {
  loading.value = true
  try {
    const r = await adminApi.listNotifications({ limit: 50 })
    items.value = (r.items || []) as N[]
    await auth.refreshUnread()
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function markOne(row: N) {
  if (row.is_read) return
  try {
    await markRead(row.id)
    row.is_read = true
    await auth.refreshUnread()
  } catch {
    uni.showToast({ title: '操作失败', icon: 'none' })
  }
}

async function markAll() {
  try {
    await markAllRead()
    uni.showToast({ title: '已全部已读', icon: 'success' })
    await reload()
  } catch {
    uni.showToast({ title: '操作失败', icon: 'none' })
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; justify-content: flex-end; }
.btn { background: #4338ca; color: #fff; border-radius: 999rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.row-head { display: flex; justify-content: space-between; align-items: center; }
.dot { font-size: 22rpx; color: #ef4444; }
</style>
