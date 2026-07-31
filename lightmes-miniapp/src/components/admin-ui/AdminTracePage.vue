<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="code" class="search" placeholder="成品码/追溯码" @confirm="search" />
      <button class="btn" size="mini" @tap="search">查询</button>
    </view>

    <view v-if="chain" class="result adm-card">
      <text class="title">{{ chain.product_code || chain.trace_code }}</text>
      <view class="kv"><text class="k">订单</text><text class="v">{{ orderText }}</text></view>
      <view class="kv"><text class="k">型号</text><text class="v">{{ skuText }}</text></view>
      <view class="kv"><text class="k">报工</text><text class="v">{{ reportText }}</text></view>
      <view v-if="flowSteps.length" class="section-title">工序链</view>
      <view v-for="(s, i) in flowSteps" :key="i" class="step">{{ s.process_name }} · {{ s.user_full_name || s.username || '—' }}</view>
    </view>

    <view class="section-title list-title">追溯记录</view>
    <MListLayout :items="records" :loading="loading" empty-text="暂无记录" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.product_code || item.code }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '订单', value: item.order_id ? `#${item.order_id}` : '—' },
          { label: '创建时间', value: item.created_at?.slice(0, 16) || '—' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="pickRecord(item)">查询</button>
        </view>
      </template>
    </MListLayout>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { productionAdminApi } from '@/api/admin/production'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const code = ref('')
const chain = ref<Record<string, unknown> | null>(null)
const records = ref<{ id: number; code: string; product_code?: string; order_id: number; created_at: string }[]>([])
const loading = ref(false)

const orderText = computed(() => {
  const o = chain.value?.order as { code?: string; id?: number } | undefined
  return o ? `${o.code || o.id}` : '—'
})
const skuText = computed(() => {
  const s = chain.value?.sku as { display_label?: string; name?: string } | undefined
  return s?.display_label || s?.name || '—'
})
const reportText = computed(() => {
  const r = chain.value?.report as { status?: string; good_qty?: number; bad_qty?: number } | undefined
  return r ? `${r.status} · 良${r.good_qty}/不良${r.bad_qty}` : '—'
})
const flowSteps = computed(() => (chain.value?.flow_chain as { process_name?: string; user_full_name?: string; username?: string }[]) || [])

onShow(async () => {
  if (!requirePermission('trace.query')) return
  await reload()
})

async function reload() {
  loading.value = true
  try {
    const r = await productionAdminApi.traceList({ limit: 50 })
    records.value = r.items || []
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}

async function search() {
  const c = code.value.trim()
  if (!c) return
  try {
    chain.value = await productionAdminApi.traceQuery(c)
  } catch (e: unknown) {
    chain.value = null
    uni.showToast({ title: (e as Error).message || '未找到', icon: 'none' })
  }
}

function pickRecord(row: { code: string }) {
  code.value = row.code
  search()
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.btn { background: #4338ca; color: #fff; border-radius: 999rpx; }
.result { margin-bottom: 24rpx; }
.title { display: block; font-size: 30rpx; font-weight: 700; margin-bottom: 12rpx; font-family: monospace; }
.kv { display: flex; gap: 16rpx; margin-bottom: 8rpx; font-size: 26rpx; }
.k { color: #64748b; width: 100rpx; }
.v { flex: 1; }
.section-title { font-size: 28rpx; font-weight: 600; margin: 12rpx 0; }
.list-title { margin-top: 8rpx; }
.step { font-size: 26rpx; padding: 8rpx 0; color: #475569; border-bottom: 1rpx solid #f1f5f9; }
</style>
