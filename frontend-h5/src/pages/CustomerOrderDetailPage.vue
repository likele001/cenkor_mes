<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast, showConfirmDialog, showLoadingToast, closeToast } from 'vant'
import type { TagType } from 'vant/es/tag/types'
import { getMyOrderDetail, getOrderShipments, getOrderAfterSales, createAfterSale, type CustomerOrderDetail, type ShipmentOut, type AfterSaleOut } from '@/api/customer'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const data = ref<CustomerOrderDetail | null>(null)
const shipments = ref<ShipmentOut[]>([])
const afterSales = ref<AfterSaleOut[]>([])
const extraLoading = ref(false)

const orderId = computed(() => Number(route.params.id))

function toPercent(v: number | null) {
  if (typeof v !== 'number') return 0
  const p = Math.round(v * 10000) / 100
  if (p < 0) return 0
  if (p > 100) return 100
  return p
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: t('customer.status.draft'),
    confirmed: t('customer.status.confirmed'),
    producing: t('customer.status.producing'),
    done: t('customer.status.done'),
    shipped: t('customer.status.shipped'),
    cancelled: t('customer.status.cancelled'),
  }
  return map[s] || s || '—'
}

function statusTagType(s: string): TagType {
  const map: Record<string, TagType> = {
    draft: 'warning',
    confirmed: 'primary',
    producing: 'default',
    done: 'success',
    shipped: 'primary',
    cancelled: 'danger',
  }
  return map[s] || 'default'
}

function saleTypeLabel(s: string) {
  const map: Record<string, string> = {
    return: t('customer.afterSale.returnGoods'),
    exchange: t('customer.afterSale.exchange'),
    repair: t('customer.afterSale.repair'),
    other: t('customer.afterSale.other'),
  }
  return map[s] || s
}

function saleStatusLabel(s: string) {
  const map: Record<string, string> = {
    pending: t('customer.afterSale.pending'),
    processing: t('customer.afterSale.processing'),
    done: t('customer.afterSale.done'),
    rejected: t('customer.afterSale.rejected'),
  }
  return map[s] || s
}

async function loadAll() {
  const id = orderId.value
  if (!id) return
  loading.value = true
  extraLoading.value = true
  try {
    const [order, shipResp, asResp] = await Promise.all([
      getMyOrderDetail(id),
      getOrderShipments(id),
      getOrderAfterSales(id),
    ])
    data.value = order
    shipments.value = shipResp?.items ?? []
    afterSales.value = asResp?.items ?? []
  } finally {
    loading.value = false
    extraLoading.value = false
  }
}

const afterSaleSheetShow = ref(false)

const afterSaleSheetActions = [
  { name: t('customer.afterSale.returnGoods') },
  { name: t('customer.afterSale.exchange') },
  { name: t('customer.afterSale.repair') },
  { name: t('customer.afterSale.other') },
]

const saleTypeByActionName: Record<string, 'return' | 'exchange' | 'repair' | 'other'> = {
}

function initSaleTypeMap() {
  saleTypeByActionName[t('customer.afterSale.returnGoods')] = 'return'
  saleTypeByActionName[t('customer.afterSale.exchange')] = 'exchange'
  saleTypeByActionName[t('customer.afterSale.repair')] = 'repair'
  saleTypeByActionName[t('customer.afterSale.other')] = 'other'
}
initSaleTypeMap()

function openAfterSaleCreate() {
  afterSaleSheetShow.value = true
}

async function onAfterSaleSheetSelect(action: { name?: string }) {
  afterSaleSheetShow.value = false
  const saleType = action.name ? saleTypeByActionName[action.name] : undefined
  if (!saleType) return

  try {
    await showConfirmDialog({ title: `${t('customer.orderDetail.applyAfterSale')} - ${saleTypeLabel(saleType)}`, message: t('customer.orderDetail.confirmApply') })
  } catch {
    return
  }

  showLoadingToast({ message: t('customer.orderDetail.submitting'), duration: 0 })
  try {
    await createAfterSale(orderId.value, { sale_type: saleType })
    closeToast()
    showToast(t('customer.orderDetail.applySuccess'))
    await loadAll()
  } catch {
    closeToast()
  }
}

watch(orderId, loadAll, { immediate: true })
</script>

<template>
  <div>
    <van-loading v-if="loading" class="mx-auto" />

    <template v-if="data">
      <div class="rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 p-4 text-white">
        <div class="flex items-center justify-between">
          <div class="text-sm opacity-80">{{ t('customer.orderDetail.orderNo') }}</div>
          <van-tag :type="statusTagType(data.status)" plain size="medium">{{ statusLabel(data.status) }}</van-tag>
        </div>
        <div class="mt-1 font-mono text-lg">{{ data.code }}</div>
      </div>

      <div class="mx-4 -mt-3 rounded-xl bg-white p-3 shadow-sm">
        <div class="flex items-center justify-between text-sm">
          <span class="text-zinc-500">{{ t('customer.orderDetail.progress') }}</span>
          <span>{{ data.done_qty }}/{{ data.total_qty }}</span>
        </div>
        <van-progress :percentage="toPercent(data.progress)" class="mt-2" />
      </div>

      <van-cell-group inset class="mt-3">
        <van-cell :title="t('customer.orderDetail.status')" :value="statusLabel(data.status)" />
        <van-cell :title="t('customer.orderDetail.dueDate')" :value="data.due_date || '—'" />
        <van-cell :title="t('customer.orderDetail.quantity')" :value="`${data.done_qty ?? 0}/${data.total_qty ?? 0}`" />
        <van-cell :title="t('customer.orderDetail.remark')" :value="data.remark || '—'" />
      </van-cell-group>

      <div class="mx-4 mt-4">
        <div class="mb-2 text-sm font-medium text-zinc-700">{{ t('customer.orderDetail.orderItems') }}</div>
        <van-cell-group inset>
          <van-cell v-for="it in data.items" :key="it.id">
            <template #title>
              <span v-if="it.sku">{{ it.sku.display_name || it.sku.name }}</span>
              <span v-else>型号#{{ it.sku_id ?? it.line_no }}</span>
            </template>
            <template #label>{{ it.remark || '' }}</template>
            <template #value>x{{ it.qty }}</template>
          </van-cell>
        </van-cell-group>
      </div>

      <div v-if="shipments.length" class="mx-4 mt-4">
        <div class="mb-2 text-sm font-medium text-zinc-700">{{ t('customer.orderDetail.shipmentInfo') }}</div>
        <van-cell-group inset>
          <van-cell v-for="s in shipments" :key="s.id">
            <template #title>
              <div class="flex items-center gap-2">
                <span>{{ t('customer.orderDetail.shipment') }} {{ s.code }}</span>
                <van-tag v-if="s.status === 'shipped'" type="primary" size="medium">{{ t('customer.orderDetail.shipped') }}</van-tag>
                <van-tag v-else-if="s.status === 'signed'" type="success" size="medium">{{ t('customer.orderDetail.signed') }}</van-tag>
              </div>
            </template>
            <template #label>
              <div v-if="s.logistics_company || s.logistics_no" class="text-xs text-zinc-400 mt-1">
                <span v-if="s.logistics_company">{{ s.logistics_company }}</span>
                <span v-if="s.logistics_no" class="ml-2 font-mono">{{ s.logistics_no }}</span>
              </div>
              <div v-if="s.shipped_at" class="text-xs text-zinc-400">{{ t('customer.orderDetail.shipTime') }}{{ s.shipped_at?.slice(0, 10) }}</div>
            </template>
          </van-cell>
        </van-cell-group>
      </div>

      <div v-if="afterSales.length" class="mx-4 mt-4">
        <div class="mb-2 text-sm font-medium text-zinc-700">{{ t('customer.orderDetail.afterSale') }}</div>
        <van-cell-group inset>
          <van-cell v-for="a in afterSales" :key="a.id">
            <template #title>
              <div class="flex items-center gap-2">
                <span>{{ saleTypeLabel(a.sale_type) }}</span>
                <van-tag size="medium" plain>{{ saleStatusLabel(a.status) }}</van-tag>
              </div>
            </template>
            <template #label>
              <div class="text-xs text-zinc-400 mt-1">
                <div v-if="a.reason">{{ t('customer.orderDetail.reason') }}{{ a.reason }}</div>
                <div v-if="a.solution">{{ t('customer.orderDetail.solution') }}{{ a.solution }}</div>
                <div>{{ t('customer.orderDetail.applyTime') }}{{ a.created_at?.slice(0, 16).replace('T', ' ') }}</div>
              </div>
            </template>
          </van-cell>
        </van-cell-group>
      </div>

      <div class="mt-6 space-y-3 px-3">
        <van-button block type="primary" @click="router.push({ name: 'customerOrderProgress', params: { id: orderId } })">{{ t('customer.orderDetail.viewProgress') }}</van-button>
        <van-button block plain @click="openAfterSaleCreate">{{ t('customer.orderDetail.applyAfterSale') }}</van-button>
        <van-button block @click="router.push({ name: 'customerOrder' })">{{ t('customer.orderDetail.returnList') }}</van-button>
      </div>
    </template>

    <van-action-sheet
      v-model:show="afterSaleSheetShow"
      :title="t('customer.orderDetail.selectAfterSaleType')"
      :cancel-text="t('common.cancel')"
      :actions="afterSaleSheetActions"
      @select="onAfterSaleSheetSelect"
      @cancel="afterSaleSheetShow = false"
    />

    <div class="h-8" />
  </div>
</template>
