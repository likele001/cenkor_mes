<template>
  <view class="adm-page">
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="detail" class="adm-card">
      <text class="title">{{ detail.code }}</text>
      <text class="sub">{{ statusLabel(detail.status) }} · {{ detail.supplier_name || '—' }}</text>
      <view class="kv"><text class="k">备注</text><text class="v">{{ detail.remark || '—' }}</text></view>
      <view class="section">明细</view>
      <view v-for="(it, idx) in detail.items || []" :key="idx" class="line">
        <text class="mat">{{ it.material_code }} {{ it.material_name }}</text>
        <text class="nums">采购 {{ it.qty }} · 已入 {{ it.received_qty ?? 0 }}</text>
      </view>
    </view>
    <view v-else class="loading">未找到采购单</view>
  </view>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { purchaseAdminApi, type PurchaseOrder } from '@/api/admin/purchase'
import { usePermission } from '@/composables/usePermission'

const detail = ref<PurchaseOrder | null>(null)
const loading = ref(true)
const { requirePermission } = usePermission()

function statusLabel(s: string) {
  return ({ draft: '草稿', confirmed: '已确认', receiving: '入库中', completed: '已完成', cancelled: '已作废' } as Record<string, string>)[s] || s
}

onLoad(async (q) => {
  requirePermission('purchase.manage')
  const id = Number(q?.id || 0)
  if (!id) {
    loading.value = false
    return
  }
  try {
    detail.value = await purchaseAdminApi.get(id)
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
.line { padding: 12rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.mat { display: block; font-size: 26rpx; }
.nums { font-size: 24rpx; color: #64748b; }
</style>
