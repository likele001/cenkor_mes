<template>
  <view class="adm-page">
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="detail" class="adm-card">
      <text class="title">{{ detail.code }}</text>
      <text class="sub">{{ detail.customer?.name }} · ¥{{ fmt(detail.total_amount) }} · {{ detail.status }}</text>
      <view v-for="(it, idx) in detail.items || []" :key="idx" class="line">
        <text>{{ it.order_code || `#${it.order_id}` }} · ¥{{ fmt(it.amount) }}</text>
      </view>
    </view>
  </view>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { financeAdminApi, type CustomerStatement } from '@/api/admin/finance'
import { usePermission } from '@/composables/usePermission'

const detail = ref<CustomerStatement | null>(null)
const loading = ref(true)
const { requirePermission } = usePermission()

onLoad(async (q) => {
  requirePermission('finance.manage')
  const id = Number(q?.id || 0)
  if (!id) return
  try {
    detail.value = await financeAdminApi.getStatement(id)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
})

function fmt(v?: number) {
  return Number(v || 0).toFixed(2)
}
</script>
<style scoped>
.loading { padding: 40rpx; text-align: center; color: #94a3b8; }
.title { display: block; font-size: 32rpx; font-weight: 700; }
.sub { display: block; font-size: 26rpx; color: #64748b; margin: 12rpx 0 20rpx; }
.line { font-size: 26rpx; padding: 10rpx 0; border-bottom: 1rpx solid #f1f5f9; }
</style>
