<template>
  <view class="cust-page">
    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <template v-else-if="items.length">
      <!-- 发货汇总 -->
      <view class="cust-card summary-card">
        <view class="summary-row">
          <text class="summary-label">共 {{ items.length }} 次发货</text>
          <text class="summary-sub">{{ shippedCount }} 已发货</text>
        </view>
      </view>

      <!-- 时间线列表 -->
      <view class="timeline">
        <view v-for="(s, idx) in items" :key="s.id" class="timeline-item" :class="{ first: idx === 0 }">
          <view class="timeline-dot" :class="dotClass(s.status)" />
          <view class="timeline-line" v-if="idx < items.length - 1" />
          <view class="timeline-content cust-card">
            <view class="content-head">
              <text class="cust-title mono">{{ s.code }}</text>
              <text class="cust-tag" :class="tagClass(s.status)">{{ statusText(s.status) }}</text>
            </view>
            <view v-if="s.logistics_company" class="kv">
              <text class="k">{{ t('customer.orderDetail.logistics') }}</text>
              <text class="v accent">{{ s.logistics_company }}</text>
            </view>
            <view v-if="s.logistics_no" class="kv">
              <text class="k">运单号</text>
              <text class="v mono">{{ s.logistics_no }}</text>
            </view>
            <view v-if="s.shipped_at" class="kv">
              <text class="k">{{ t('customer.orderDetail.shipTime') }}</text>
              <text class="v">{{ fmtTime(s.shipped_at) }}</text>
            </view>
            <view v-if="s.remark" class="kv">
              <text class="k">{{ t('common.remark') }}</text>
              <text class="v">{{ s.remark }}</text>
            </view>
          </view>
        </view>
      </view>
    </template>

    <!-- 空状态 -->
    <view v-else class="cust-card empty-card">
      <text class="empty-icon">📦</text>
      <text class="empty-text">暂无发货信息</text>
      <text class="empty-sub">订单确认后将安排发货</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import { getOrderShipments, type ShipmentOut } from '@/api/h5/customer'
import { useCustomerLabels } from '@/composables/useCustomerLabels'
import { useCustomerLocale } from '@/composables/useCustomerLocale'
import { usePermission } from '@/composables/usePermission'

const { t } = useI18n()
const { orderStatusLabel } = useCustomerLabels()
const { setNavTitle } = useCustomerLocale()
const { requireCustomer } = usePermission()

const orderId = ref(0)
const loading = ref(false)
const items = ref<ShipmentOut[]>([])

const shippedCount = computed(() => items.value.filter((i) => i.shipped_at).length)

function statusText(s: string) {
  const map: Record<string, string> = {
    pending: '待发',
    shipped: '已发货',
    received: '已收货',
    cancelled: '已取消',
  }
  return map[s] || orderStatusLabel(s) || s
}

function tagClass(s: string) {
  if (s === 'shipped' || s === 'received') return 'tone-ok'
  if (s === 'pending') return 'tone-warn'
  return ''
}

function dotClass(s: string) {
  if (s === 'shipped' || s === 'received') return 'done'
  if (s === 'pending') return 'pending'
  return 'default'
}

function fmtTime(v: string | null) {
  return v ? v.slice(0, 16).replace('T', ' ') : '—'
}

async function load() {
  if (!orderId.value) return
  loading.value = true
  try {
    const res = await getOrderShipments(orderId.value)
    items.value = res?.items ?? []
  } finally {
    loading.value = false
  }
}

onLoad((q) => {
  orderId.value = Number(q?.id || 0)
})

onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.orderDetail.shipmentInfo')
  load()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.summary-card {
  padding: 20rpx 24rpx;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.summary-label {
  font-size: 28rpx;
  font-weight: 600;
  color: #1e293b;
}
.summary-sub {
  font-size: 24rpx;
  color: #15803d;
  background: #dcfce7;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}
.timeline {
  position: relative;
  padding-left: 48rpx;
}
.timeline-item {
  position: relative;
  padding-bottom: 24rpx;
}
.timeline-dot {
  position: absolute;
  left: -40rpx;
  top: 32rpx;
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  background: #cbd5e1;
  z-index: 2;
}
.timeline-dot.done { background: #22c55e; }
.timeline-dot.pending { background: #f59e0b; }
.timeline-line {
  position: absolute;
  left: -31rpx;
  top: 52rpx;
  width: 2rpx;
  height: calc(100% - 24rpx);
  background: #e2e8f0;
  z-index: 1;
}
.timeline-content {
  margin-left: 0;
}
.content-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.kv {
  display: flex;
  justify-content: space-between;
  padding: 8rpx 0;
  font-size: 26rpx;
}
.k {
  color: #64748b;
}
.v {
  text-align: right;
}
.v.accent {
  color: #0369a1;
  font-weight: 600;
}
.mono {
  font-family: monospace;
}
.tone-ok { background: #dcfce7; color: #15803d; }
.tone-warn { background: #fef3c7; color: #b45309; }
.empty-card {
  text-align: center;
  padding: 60rpx 24rpx;
}
.empty-icon {
  display: block;
  font-size: 64rpx;
  margin-bottom: 16rpx;
}
.empty-text {
  display: block;
  font-size: 28rpx;
  color: #64748b;
}
.empty-sub {
  display: block;
  font-size: 24rpx;
  color: #94a3b8;
  margin-top: 8rpx;
}
</style>
