<template>
  <view class="adm-page">
    <view class="toolbar">
      <button class="add-btn" size="mini" @tap="openAddType">+ 字典类型</button>
    </view>
    <MListLayout :items="types" :loading="loading" empty-text="暂无字典类型" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.name }}</text>
        </view>
        <AdminKvGrid :rows="[{ label: '编码', value: item.code || '—' }]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="openType(item)">管理项</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="itemsVisible" class="mask" @tap="itemsVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">{{ currentType?.name }}</text>
          <text class="link" @tap="openAddItem">+ 项</text>
        </view>
        <scroll-view scroll-y class="body">
          <view v-for="it in dictItems" :key="it.id" class="item-row">
            <text class="label">{{ it.label }}</text>
            <text class="value">{{ it.value }}</text>
          </view>
          <view v-if="!dictItems.length" class="empty">暂无字典项</view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { systemAdminApi } from '@/api/admin/system'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const types = ref<{ id: number; code: string; name: string }[]>([])
const dictItems = ref<{ id: number; label: string; value: string }[]>([])
const loading = ref(false)
const itemsVisible = ref(false)
const currentType = ref<{ id: number; code: string; name: string } | null>(null)

onShow(async () => {
  if (!requirePermission('dict.manage')) return
  await reload()
})

async function reload() {
  loading.value = true
  try {
    const r = await systemAdminApi.listDictTypes()
    types.value = r.items || []
  } catch {
    types.value = []
  } finally {
    loading.value = false
  }
}

async function openType(row: { id: number; code: string; name: string }) {
  currentType.value = row
  try {
    const r = await systemAdminApi.listDictItems(row.id)
    dictItems.value = r.items || []
    itemsVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function openAddType() {
  uni.showModal({
    title: '新建字典类型',
    editable: true,
    placeholderText: '编码,名称（逗号分隔）',
    success: async (res) => {
      if (!res.confirm || !res.content) return
      const [code, name] = res.content.split(/[,，]/).map((s) => s.trim())
      if (!code || !name) {
        uni.showToast({ title: '格式：编码,名称', icon: 'none' })
        return
      }
      await systemAdminApi.createDictType(code, name)
      uni.showToast({ title: '已创建', icon: 'success' })
      await reload()
    },
  })
}

function openAddItem() {
  if (!currentType.value) return
  uni.showModal({
    title: '新建字典项',
    editable: true,
    placeholderText: '显示名,值（逗号分隔）',
    success: async (res) => {
      if (!res.confirm || !res.content || !currentType.value) return
      const [label, value] = res.content.split(/[,，]/).map((s) => s.trim())
      if (!label || !value) {
        uni.showToast({ title: '格式：显示名,值', icon: 'none' })
        return
      }
      await systemAdminApi.createDictItem(currentType.value.id, label, value)
      uni.showToast({ title: '已创建', icon: 'success' })
      const r = await systemAdminApi.listDictItems(currentType.value.id)
      dictItems.value = r.items || []
    },
  })
}
</script>

<style scoped lang="scss">
.toolbar { margin-bottom: 20rpx; }
.add-btn { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 70vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 32rpx; font-weight: 700; }
.link { color: #4338ca; font-size: 26rpx; }
.body { max-height: 55vh; padding: 16rpx 32rpx; }
.item-row { display: flex; justify-content: space-between; padding: 16rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.label { font-size: 28rpx; }
.value { font-size: 26rpx; color: #64748b; }
.empty { text-align: center; color: #94a3b8; padding: 40rpx; }
</style>
