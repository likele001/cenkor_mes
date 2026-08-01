<template>
  <view class="cust-page">
    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <template v-else-if="items.length">
      <!-- 汇总卡 -->
      <view class="cust-card cust-card--brand summary-card">
        <view class="summary-row">
          <view class="summary-item">
            <text class="summary-val">{{ items.length }}</text>
            <text class="summary-lbl">总发货</text>
          </view>
          <view class="summary-divider" />
          <view class="summary-item">
            <text class="summary-val">{{ shippedCount }}</text>
            <text class="summary-lbl">已发货</text>
          </view>
        </view>
      </view>

      <!-- 时间线 -->
      <view class="timeline">
        <view v-for="(s, idx) in items" :key="s.id" class="timeline-item">
          <view class="timeline-dot" :class="dotClass(s.status)" />
          <view v-if="idx < items.length - 1" class="timeline-line" />
          <view class="cust-card timeline-content">
            <view class="content-head">
              <text class="cust-title mono">{{ s.code }}</text>
              <text class="cust-tag" :class="tagClass(s.status)">{{ statusText(s.status) }}</text>
            </view>
            <view class="cust-kv-grid" style="margin-top: 12rpx;">
              <view v-if="s.logistics_company" class="cust-kv-row"><text class="cust-kv-k">{{ t('customer.orderDetail.logistics') }}</text><text class="cust-kv-v accent">{{ s.logistics_company }}</text></view>
              <view v-if="s.logistics_no" class="cust-kv-row"><text class="cust-kv-k">运单号</text><text class="cust-kv-v mono">{{ s.logistics_no }}</text></view>
              <view v-if="s.shipped_at" class="cust-kv-row"><text class="cust-kv-k">{{ t('customer.orderDetail.shipTime') }}</text><text class="cust-kv-v">{{ fmtTime(s.shipped_at) }}</text></view>
              <view v-if="s.remark" class="cust-kv-row"><text class="cust-kv-k">{{ t('common.remark') }}</text><text class="cust-kv-v">{{ s.remark }}</text></view>
            </view>
          </view>
        </view>
      </view>
    </template>

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
  const map: Record<string, string> = { pending: '待发', shipped: '已发货', received: '已收货', cancelled: '已取消' }
  return map[s] || orderStatusLabel(s) || s
}
function tagClass(s: string) {
  if (s === 'shipped' || s === 'received') return 'ok'
  if (s === 'pending') return 'warn'
  return 'muted'
}
function dotClass(s: string) {
  if (s === 'shipped' || s === 'received') return 'done'
  if (s === 'pending') return 'pending'
  return 'default'
}
function fmtTime(v: string | null) { return v ? v.slice(0, 16).replace('T', ' ') : '—' }

async function load() {
  if (!orderId.value) return
  loading.value = true
  try { const res = await getOrderShipments(orderId.value); items.value = res?.items ?? [] } finally { loading.value = false }
}

onLoad((q) => { orderId.value = Number(q?.id || 0) })
onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.orderDetail.shipmentInfo')
  load()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.summary-card { padding: 24rpx; border-radius: 20rpx; }
.summary-row { display: flex; align-items: center; }
.summary-item { flex: 1; text-align: center; }
.summary-val { font-size: 40rpx; font-weight: 700; color: #fff; }
.summary-lbl { display: block; font-size: 22rpx; color: rgba(255,255,255,0.78); margin-top: 4rpx; }
.summary-divider { width: 1rpx; height: 48rpx; background: rgba(255,255,255,0.2); }

.timeline { position: relative; padding-left: 40rpx; }
.timeline-item { position: relative; padding-bottom: 20rpx; }
.timeline-dot {
  position: absolute; left: -32rpx; top: 28rpx;
  width: 20rpx; height: 20rpx; border-radius: 50%;
  background: #cbd5e1; z-index: 2;
  border: 4rpx solid #fff;
  &.done { background: #22c55e; }
  &.pending { background: #f59e0b; }
}
.timeline-line {
  position: absolute; left: -23rpx; top: 48rpx;
  width: 2rpx; height: calc(100% - 20rpx);
  background: #e0f2fe; z-index: 1;
}
.timeline-content { margin-left: 0; }
.content-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12rpx; }
.mono { font-family: monospace; }
.accent { color: #0284c7 !important; }

.empty-card { text-align: center; padding: 60rpx 24rpx; }
.empty-icon { display: block; font-size: 64rpx; margin-bottom: 16rpx; }
.empty-text { display: block; font-size: 28rpx; color: #64748b; }
.empty-sub { display: block; font-size: 24rpx; color: #94a3b8; margin-top: 8rpx; }
</style>
