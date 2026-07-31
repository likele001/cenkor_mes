<template>
  <view class="adm-page">
    <view class="adm-section-head" v-if="moldName">
      <text class="adm-section-title">{{ moldName }} 的关联工序</text>
    </view>

    <view class="adm-card" v-if="allProcesses.length">
      <view v-for="p in allProcesses" :key="p.id" class="checkbox-row">
        <label class="checkbox-label">
          <checkbox :checked="selected.has(p.id)" @tap="toggle(p.id)" />
          <text class="checkbox-text">{{ p.name }}</text>
        </label>
      </view>
      <view v-if="!allProcesses.length && !loading" class="adm-empty-tip">暂无工序数据</view>
    </view>

    <view class="foot-bar">
      <button class="btn primary" :loading="saving" @tap="saveBindings">保存工序关联</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { apiGet } from '@/api/request'
import { moldApi } from '@/api/admin/mold'

const moldId = ref(0)
const moldName = ref('')
const allProcesses = ref<{ id: number; name: string }[]>([])
const selected = ref(new Set<number>())
const loading = ref(false)
const saving = ref(false)

onLoad(async (q) => {
  moldId.value = Number(q?.moldId || 0)
  moldName.value = q?.name ? decodeURIComponent(q.name as string) : ''
  await loadProcesses()
  await loadBindings()
})

async function loadProcesses() {
  loading.value = true
  try {
    const r = await apiGet<{ items: { id: number; name: string }[] }>('/admin/processes', { limit: 200 }, true)
    allProcesses.value = r.items
  } catch { allProcesses.value = [] }
  finally { loading.value = false }
}

async function loadBindings() {
  if (!moldId.value) return
  try {
    const r = await moldApi.listProcessBindings(moldId.value)
    selected.value = new Set(r.items.map(b => b.process_id))
  } catch { /* ok */ }
}

function toggle(id: number) {
  const s = new Set(selected.value)
  if (s.has(id)) s.delete(id); else s.add(id)
  selected.value = s
}

async function saveBindings() {
  if (!moldId.value) return
  saving.value = true
  try {
    await moldApi.setProcessBindings(moldId.value, [...selected.value])
    uni.showToast({ title: '保存成功', icon: 'success' })
  } catch { /* handled */ }
  finally { saving.value = false }
}
</script>

<style scoped>
.checkbox-row { padding: 20rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.checkbox-row:last-child { border-bottom: none; }
.checkbox-label { display: flex; align-items: center; gap: 16rpx; }
.checkbox-text { font-size: 28rpx; color: #334155; }
.foot-bar { padding: 24rpx 0; }
</style>
