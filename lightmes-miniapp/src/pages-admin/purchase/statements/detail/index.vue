<template>
  <view class="adm-page">
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="detail" class="adm-card">
      <text class="title">{{ detail.code }}</text>
      <text class="sub">{{ statusLabel(detail.status) }} · {{ detail.supplier_name || '—' }}</text>
      <view class="kv"><text class="k">期间</text><text class="v">{{ detail.period_from || '—' }} ~ {{ detail.period_to || '—' }}</text></view>
      <view class="kv"><text class="k">金额</text><text class="v">¥{{ fmt(detail.amount) }}</text></view>
      <view class="section">明细</view>
      <view v-for="(it, idx) in detail.items || []" :key="idx" class="line">
        <text>{{ it.purchase_order_code || `#${it.purchase_order_id}` }} · 入库 {{ it.received_qty }} · ¥{{ fmt(it.amount) }}</text>
      </view>
    </view>
    <view v-else class="loading">未找到对账单</view>
  </view>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { purchaseAdminApi } from '@/api/admin/purchase'
import { usePermission } from '@/composables/usePermission'

type StmtDetail = {
  code: string
  status: string
  supplier_name?: string | null
  period_from?: string | null
  period_to?: string | null
  amount?: number
  items?: { purchase_order_id: number; purchase_order_code?: string | null; received_qty: number; amount: number }[]
}

const detail = ref<StmtDetail | null>(null)
const loading = ref(true)
const { requirePermission } = usePermission()

function statusLabel(s: string) {
  return ({ draft: '草稿', confirmed: '已确认', paid: '已付款' } as Record<string, string>)[s] || s
}
function fmt(v?: number) {
  return Number(v || 0).toFixed(2)
}

onLoad(async (q) => {
  requirePermission('purchase.manage')
  const id = Number(q?.id || 0)
  if (!id) {
    loading.value = false
    return
  }
  try {
    detail.value = (await purchaseAdminApi.getStatement(id)) as StmtDetail
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
.line { font-size: 26rpx; padding: 10rpx 0; border-bottom: 1rpx solid #f1f5f9; }
</style>
