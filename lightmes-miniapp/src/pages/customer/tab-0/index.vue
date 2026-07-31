<template>
  <view class="cust-page">
    <view class="cust-tabs">
      <view class="cust-tab" :class="{ active: activeTab === 0 }" @tap="activeTab = 0">{{ t('customer.order.tabBrowse') }}</view>
      <view class="cust-tab" :class="{ active: activeTab === 1 }" @tap="activeTab = 1">{{ t('customer.order.tabOrders') }}</view>
    </view>

    <view v-if="activeTab === 0">
      <view class="search-row">
        <input v-model="keyword" class="search" :placeholder="t('customer.order.searchPlaceholder')" @confirm="loadCatalog" />
      </view>
      <scroll-view scroll-x class="filter-scroll">
        <view class="filter-tags">
          <text class="filter-tag" :class="{ on: !filterProductId }" @tap="filterProductId = null">{{ t('customer.order.all') }}</text>
          <text
            v-for="p in products"
            :key="p.id"
            class="filter-tag"
            :class="{ on: filterProductId === p.id }"
            @tap="filterProductId = p.id"
          >{{ p.display_name || p.name }}</text>
        </view>
      </scroll-view>

      <view v-if="catalogLoading" class="cust-empty">{{ t('common.loading') }}</view>
      <view v-else-if="!filteredSkus.length" class="cust-empty">{{ t('customer.order.noProduct') }}</view>
      <view v-for="s in filteredSkus" :key="s.id" class="cust-card sku-card">
        <view class="sku-head">
          <text class="cust-title">{{ skuLabel(s) }}</text>
          <button class="mini-btn" size="mini" @tap="openOrder(s)">{{ t('customer.order.orderNow') }}</button>
        </view>
        <text v-if="s.color" class="cust-sub">{{ t('customer.order.color') }}{{ s.color }}</text>
        <text v-if="s.material" class="cust-sub">{{ t('customer.order.material') }}{{ s.material }}</text>
        <text v-if="s.spec" class="cust-sub">{{ t('customer.order.spec') }}{{ s.spec }}</text>
        <text class="cust-sub">{{ t('customer.order.product') }}{{ productLabel(s.product_id) }}</text>
      </view>
    </view>

    <view v-else>
      <view v-if="ordersLoading" class="cust-empty">{{ t('common.loading') }}</view>
      <view v-else-if="!orders.length" class="cust-empty">{{ t('customer.order.noOrder') }}</view>
      <view v-for="o in orders" :key="o.id" class="cust-card list-card" @tap="goDetail(o.id)">
        <view class="cust-list-head">
          <text class="cust-title mono">{{ o.code }}</text>
          <text class="cust-tag">{{ orderStatusLabel(o.status) }}</text>
        </view>
        <view class="cust-kv-grid">
          <view class="cust-kv-row">
            <text class="cust-kv-k">{{ t('customer.order.createdAt') }}</text>
            <text class="cust-kv-v">{{ fmtTime(o.created_at) }}</text>
          </view>
          <view class="cust-kv-row">
            <text class="cust-kv-k">{{ t('customer.order.dueDate') }}</text>
            <text class="cust-kv-v">{{ o.due_date || '—' }}</text>
          </view>
        </view>
      </view>
    </view>

    <view v-if="orderVisible" class="mask" @tap="orderVisible = false">
      <view class="sheet" @tap.stop>
        <text class="sheet-title">{{ t('customer.order.confirmOrder') }}</text>
        <text v-if="orderSku" class="sheet-sku">{{ skuLabel(orderSku) }}</text>
        <view class="field">
          <text class="label">{{ t('customer.order.quantity') }}</text>
          <input v-model.number="orderQty" class="input" type="number" />
        </view>
        <view class="field">
          <text class="label">{{ t('customer.order.remark') }}</text>
          <input v-model="orderRemark" class="input" :placeholder="t('customer.order.remarkPlaceholder')" />
        </view>
        <button class="cust-btn-primary" :loading="orderSubmitting" @tap="submitOrder">{{ t('customer.order.submitOrder') }}</button>
      </view>
    </view>

    <CustTabBar :active="0" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import {
  getCatalog,
  listMyOrders,
  placeOrder,
  type CatalogProductOut,
  type CustomerOrderListItem,
  type CustomerSkuOut,
} from '@/api/h5/customer'
import CustTabBar from '@/components/customer-ui/CustTabBar.vue'
import { useCustomerLabels } from '@/composables/useCustomerLabels'
import { useCustomerLocale } from '@/composables/useCustomerLocale'
import { usePermission } from '@/composables/usePermission'

const { t } = useI18n()
const { orderStatusLabel } = useCustomerLabels()
const { setNavTitle } = useCustomerLocale()
const { requireCustomer } = usePermission()

const activeTab = ref(0)
const skus = ref<CustomerSkuOut[]>([])
const products = ref<CatalogProductOut[]>([])
const orders = ref<CustomerOrderListItem[]>([])
const catalogLoading = ref(false)
const ordersLoading = ref(false)
const filterProductId = ref<number | null>(null)
const keyword = ref('')
const orderVisible = ref(false)
const orderSku = ref<CustomerSkuOut | null>(null)
const orderQty = ref(1)
const orderRemark = ref('')
const orderSubmitting = ref(false)

const filteredSkus = computed(() => {
  let list = skus.value
  if (filterProductId.value) list = list.filter((s) => s.product_id === filterProductId.value)
  const kw = keyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter(
      (s) =>
        s.code.toLowerCase().includes(kw)
        || s.name.toLowerCase().includes(kw)
        || (s.color || '').toLowerCase().includes(kw)
        || (s.material || '').toLowerCase().includes(kw),
    )
  }
  return list
})

function productLabel(pid: number) {
  const p = products.value.find((x) => x.id === pid)
  return p ? p.display_name || p.name : `#${pid}`
}

function skuLabel(s: CustomerSkuOut) {
  return s.display_name || s.name || s.code
}

function fmtTime(v: string) {
  return v ? v.slice(0, 16).replace('T', ' ') : ''
}

async function loadCatalog() {
  catalogLoading.value = true
  try {
    const res = await getCatalog({ keyword: keyword.value.trim() || undefined })
    skus.value = res?.items ?? []
    products.value = res?.products ?? []
  } finally {
    catalogLoading.value = false
  }
}

async function loadOrders() {
  ordersLoading.value = true
  try {
    const res = await listMyOrders()
    orders.value = res?.items ?? []
  } finally {
    ordersLoading.value = false
  }
}

function openOrder(s: CustomerSkuOut) {
  orderSku.value = s
  orderQty.value = 1
  orderRemark.value = ''
  orderVisible.value = true
}

async function submitOrder() {
  if (!orderSku.value || orderQty.value < 1) return
  orderSubmitting.value = true
  try {
    const result = await placeOrder({
      items: [{ sku_id: orderSku.value.id, qty: orderQty.value, remark: orderRemark.value.trim() || undefined }],
      remark: orderRemark.value.trim() || undefined,
      submit: true,
    })
    orderVisible.value = false
    uni.showModal({
      title: t('customer.order.orderSuccess'),
      content: `${t('customer.order.orderCode')}：${result.code}`,
      confirmText: t('customer.order.viewOrder'),
      success: (r) => {
        if (r.confirm) goDetail(result.id)
      },
    })
    await loadOrders()
  } finally {
    orderSubmitting.value = false
  }
}

function goDetail(id: number) {
  uni.navigateTo({ url: `/pages-customer/order/detail/index?id=${id}` })
}

onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.order.title')
  void Promise.all([loadCatalog(), loadOrders()])
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.search-row {
  padding: 0 24rpx;
}
.search {
  background: #fff;
  border-radius: 12rpx;
  padding: 20rpx 24rpx;
}
.filter-scroll {
  white-space: nowrap;
  padding: 16rpx 24rpx;
}
.filter-tags {
  display: inline-flex;
  gap: 12rpx;
}
.filter-tag {
  padding: 8rpx 20rpx;
  background: #fff;
  border-radius: 999rpx;
  font-size: 24rpx;
  color: #64748b;
}
.filter-tag.on {
  background: #0ea5e9;
  color: #fff;
}
.sku-card .sku-head,
.sku-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
}
.mini-btn {
  background: #0ea5e9;
  color: #fff;
  flex-shrink: 0;
}
.mono {
  font-family: monospace;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 200;
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  background: #fff;
  border-radius: 24rpx 24rpx 0 0;
  padding: 32rpx;
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
}
.sheet-title {
  font-size: 32rpx;
  font-weight: 700;
  display: block;
  margin-bottom: 16rpx;
}
.sheet-sku {
  display: block;
  color: #0369a1;
  margin-bottom: 24rpx;
}
.field {
  margin-bottom: 20rpx;
}
.label {
  display: block;
  font-size: 24rpx;
  color: #64748b;
  margin-bottom: 8rpx;
}
.input {
  background: #f1f5f9;
  border-radius: 12rpx;
  padding: 20rpx;
}
</style>
