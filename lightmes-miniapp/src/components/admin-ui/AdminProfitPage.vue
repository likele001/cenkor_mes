<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="month" class="search" placeholder="月份 YYYY-MM" @confirm="loadData" />
      <button class="refresh" size="mini" @tap="loadData">查询</button>
    </view>

    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="data" class="cards">
      <view class="card green">
        <text class="label">收入</text>
        <text class="value">¥{{ fmt(data.revenue) }}</text>
      </view>
      <view class="card red">
        <text class="label">成本</text>
        <text class="value">¥{{ fmt(data.cost) }}</text>
      </view>
      <view class="card orange">
        <text class="label">毛利</text>
        <text class="value">¥{{ fmt(data.gross_profit) }}</text>
      </view>
      <view class="card violet">
        <text class="label">毛利率</text>
        <text class="value">{{ pct(data.gross_margin) }}</text>
      </view>
    </view>

    <view v-if="data" class="section">
      <text class="section-title">客户收入拆分</text>
      <view v-for="c in data.breakdown.customers" :key="c.customer_id" class="row">
        <text>{{ c.customer_name || `#${c.customer_id}` }}</text>
        <text class="amt in">¥{{ fmt(c.amount) }}</text>
      </view>
      <view v-if="!data.breakdown.customers.length" class="empty">暂无</view>
    </view>

    <view v-if="data" class="section">
      <text class="section-title">供应商成本拆分</text>
      <view v-for="s in data.breakdown.suppliers" :key="s.supplier_id" class="row">
        <text>{{ s.supplier_name || `#${s.supplier_id}` }}</text>
        <text class="amt out">¥{{ fmt(s.amount) }}</text>
      </view>
      <view v-if="!data.breakdown.suppliers.length" class="empty">暂无</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { financeAdminApi, type ProfitData } from '@/api/admin/finance'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const loading = ref(false)
const month = ref('')
const data = ref<ProfitData | null>(null)

onShow(async () => {
  if (!requirePermission('finance.manage')) return
  const d = new Date()
  month.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  await loadData()
})

function fmt(v?: number) {
  return Number(v || 0).toFixed(2)
}
function pct(v?: number) {
  return `${(Number(v || 0) * 100).toFixed(2)}%`
}

async function loadData() {
  if (!month.value.trim()) return
  loading.value = true
  try {
    data.value = await financeAdminApi.getProfit(month.value.trim())
  } catch {
    data.value = null
    uni.showToast({ title: '查询失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.refresh { background: #f1f5f9; color: #475569; border-radius: 999rpx; }
.loading { text-align: center; color: #94a3b8; padding: 40rpx; }
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; margin-bottom: 24rpx; }
.card { border-radius: 16rpx; padding: 24rpx; background: #fff; }
.card .label { display: block; font-size: 24rpx; color: #64748b; }
.card .value { display: block; font-size: 36rpx; font-weight: 700; margin-top: 8rpx; }
.green .value { color: #059669; }
.red .value { color: #dc2626; }
.orange .value { color: #ea580c; }
.violet .value { color: #7c3aed; }
.section { background: #fff; border-radius: 16rpx; padding: 24rpx; margin-bottom: 20rpx; }
.section-title { display: block; font-size: 30rpx; font-weight: 700; margin-bottom: 16rpx; }
.row { display: flex; justify-content: space-between; padding: 14rpx 0; border-bottom: 1rpx solid #f1f5f9; font-size: 28rpx; }
.amt.in { color: #059669; font-weight: 600; }
.amt.out { color: #dc2626; font-weight: 600; }
.empty { color: #94a3b8; font-size: 26rpx; padding: 16rpx 0; }
</style>
