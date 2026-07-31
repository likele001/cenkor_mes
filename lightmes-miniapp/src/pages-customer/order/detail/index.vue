<template>
  <view class="cust-page detail-page">
    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <template v-else-if="data">
      <view class="cust-card">
        <text class="mono cust-title">{{ data.code }}</text>
        <view class="kv"><text class="k">{{ t('customer.orderDetail.status') }}</text><text class="v">{{ orderStatusLabel(data.status) }}</text></view>
        <view class="kv"><text class="k">{{ t('customer.orderDetail.progress') }}</text><text class="v">{{ toPercent(data.progress) }}%</text></view>
        <view class="kv"><text class="k">{{ t('customer.orderDetail.dueDate') }}</text><text class="v">{{ data.due_date || '—' }}</text></view>
        <view class="kv"><text class="k">{{ t('customer.orderDetail.quantity') }}</text><text class="v">{{ data.done_qty }}/{{ data.total_qty }}</text></view>
        <view v-if="data.remark" class="kv"><text class="k">{{ t('customer.orderDetail.remark') }}</text><text class="v">{{ data.remark }}</text></view>
      </view>

      <view class="cust-card">
        <text class="section">{{ t('customer.orderDetail.orderItems') }}</text>
        <view v-for="it in data.items" :key="it.id" class="line">
          <text>{{ it.sku?.display_name || it.sku?.name || it.sku?.code }} × {{ it.qty }}</text>
        </view>
      </view>

      <view v-if="shipments.length" class="cust-card">
        <text class="section">{{ t('customer.orderDetail.shipmentInfo') }}</text>
        <view v-for="s in shipments" :key="s.id" class="line">
          <text>{{ s.code }} · {{ orderStatusLabel(s.status) }}</text>
          <text v-if="s.logistics_company" class="cust-sub">{{ s.logistics_company }} {{ s.logistics_no }}</text>
        </view>
      </view>

      <view v-if="afterSales.length" class="cust-card">
        <text class="section">{{ t('customer.orderDetail.afterSale') }}</text>
        <view v-for="a in afterSales" :key="a.id" class="line">
          <text>{{ a.code }} · {{ saleTypeLabel(a.sale_type) }} · {{ saleStatusLabel(a.status) }}</text>
        </view>
      </view>

      <view class="actions">
        <button class="cust-btn-primary" @tap="goProgress">{{ t('customer.orderDetail.viewProgress') }}</button>
        <button class="btn-plain" @tap="goShipments">{{ t('customer.orderDetail.viewShipments') }}</button>
        <button class="btn-plain" @tap="goAfterSales">{{ t('customer.orderDetail.afterSale') }}</button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import {
  getMyOrderDetail,
  getOrderAfterSales,
  getOrderShipments,
  type AfterSaleOut,
  type CustomerOrderDetail,
  type ShipmentOut,
} from '@/api/h5/customer'
import { useCustomerLabels } from '@/composables/useCustomerLabels'
import { useCustomerLocale } from '@/composables/useCustomerLocale'
import { usePermission } from '@/composables/usePermission'

const { t } = useI18n()
const { orderStatusLabel, saleTypeLabel, saleStatusLabel, toPercent } = useCustomerLabels()
const { setNavTitle } = useCustomerLocale()
const { requireCustomer } = usePermission()

const orderId = ref(0)
const loading = ref(false)
const data = ref<CustomerOrderDetail | null>(null)
const shipments = ref<ShipmentOut[]>([])
const afterSales = ref<AfterSaleOut[]>([])

async function load() {
  if (!orderId.value) return
  loading.value = true
  try {
    const [order, ship, as] = await Promise.all([
      getMyOrderDetail(orderId.value),
      getOrderShipments(orderId.value),
      getOrderAfterSales(orderId.value),
    ])
    data.value = order
    shipments.value = ship?.items ?? []
    afterSales.value = as?.items ?? []
  } finally {
    loading.value = false
  }
}

function goProgress() {
  uni.navigateTo({ url: `/pages-customer/order/progress/index?id=${orderId.value}` })
}

function goShipments() {
  uni.navigateTo({ url: `/pages-customer/order/shipments/index?id=${orderId.value}` })
}

function goAfterSales() {
  uni.navigateTo({ url: `/pages-customer/order/after-sales/index?id=${orderId.value}` })
}

onLoad((q) => {
  orderId.value = Number(q?.id || 0)
})

onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.orderDetail.title')
  load()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.detail-page {
  padding-bottom: 40rpx;
}
.kv {
  display: flex;
  justify-content: space-between;
  padding: 12rpx 0;
  font-size: 26rpx;
}
.k {
  color: #64748b;
}
.mono {
  font-family: monospace;
  display: block;
  margin-bottom: 16rpx;
}
.section {
  font-weight: 600;
  display: block;
  margin-bottom: 12rpx;
}
.line {
  padding: 12rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
  font-size: 26rpx;
}
.actions {
  padding: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.btn-plain {
  background: #fff;
  color: #0284c7;
  border: 1rpx solid #bae6fd;
  border-radius: 12rpx;
}
</style>
