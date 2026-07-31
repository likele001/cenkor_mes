<template>
  <view class="cust-page">
    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <view v-else-if="!items.length" class="cust-empty">{{ t('common.noData') }}</view>
    <view v-for="a in items" :key="a.id" class="cust-card">
      <text class="cust-title mono">{{ a.code }}</text>
      <view class="kv">
        <text class="k">{{ t('common.status') }}</text>
        <text class="v">{{ saleStatusLabel(a.status) }}</text>
      </view>
      <view class="kv">
        <text class="k">{{ t('customer.orderDetail.afterSale') }}</text>
        <text class="v">{{ saleTypeLabel(a.sale_type) }}</text>
      </view>
      <view v-if="a.reason" class="kv">
        <text class="k">{{ t('customer.orderDetail.reason') }}</text>
        <text class="v">{{ a.reason }}</text>
      </view>
      <view v-if="a.solution" class="kv">
        <text class="k">{{ t('customer.orderDetail.solution') }}</text>
        <text class="v">{{ a.solution }}</text>
      </view>
      <view v-if="a.created_at" class="kv">
        <text class="k">{{ t('customer.orderDetail.applyTime') }}</text>
        <text class="v">{{ a.created_at.slice(0, 16).replace('T', ' ') }}</text>
      </view>
    </view>

    <view class="footer">
      <button class="cust-btn-primary" @tap="applyAfterSale">{{ t('customer.orderDetail.applyAfterSale') }}</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import {
  createAfterSale,
  getOrderAfterSales,
  type AfterSaleOut,
} from '@/api/h5/customer'
import { useCustomerLabels } from '@/composables/useCustomerLabels'
import { useCustomerLocale } from '@/composables/useCustomerLocale'
import { usePermission } from '@/composables/usePermission'

const { t } = useI18n()
const { saleTypeLabel, saleStatusLabel } = useCustomerLabels()
const { setNavTitle } = useCustomerLocale()
const { requireCustomer } = usePermission()

const orderId = ref(0)
const loading = ref(false)
const items = ref<AfterSaleOut[]>([])

const saleTypes = [
  { key: 'return', labelKey: 'customer.afterSale.returnGoods' },
  { key: 'exchange', labelKey: 'customer.afterSale.exchange' },
  { key: 'repair', labelKey: 'customer.afterSale.repair' },
  { key: 'other', labelKey: 'customer.afterSale.other' },
]

async function load() {
  if (!orderId.value) return
  loading.value = true
  try {
    const res = await getOrderAfterSales(orderId.value)
    items.value = res?.items ?? []
  } finally {
    loading.value = false
  }
}

function applyAfterSale() {
  uni.showActionSheet({
    itemList: saleTypes.map((x) => t(x.labelKey)),
    success: (res) => {
      const picked = saleTypes[res.tapIndex]
      if (!picked) return
      uni.showModal({
        title: t('common.confirm'),
        content: t('customer.orderDetail.confirmApply'),
        success: async (r) => {
          if (!r.confirm) return
          try {
            await createAfterSale(orderId.value, { sale_type: picked.key })
            uni.showToast({ title: t('customer.orderDetail.applySuccess'), icon: 'success' })
            load()
          } catch {
            /* toast from request */
          }
        },
      })
    },
  })
}

onLoad((q) => {
  orderId.value = Number(q?.id || 0)
})

onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.orderDetail.afterSale')
  load()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.kv {
  display: flex;
  justify-content: space-between;
  padding: 10rpx 0;
  font-size: 26rpx;
}
.k {
  color: #64748b;
}
.mono {
  font-family: monospace;
  display: block;
  margin-bottom: 12rpx;
}
.footer {
  padding: 24rpx;
}
</style>
