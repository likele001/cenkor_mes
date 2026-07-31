<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast, showConfirmDialog, showDialog, showLoadingToast, closeToast } from 'vant'
import type { TagType } from 'vant/es/tag/types'
import { getCatalog, placeOrder, listMyOrders, type CustomerSkuOut, type CatalogProductOut, type CustomerOrderListItem } from '@/api/customer'

const { t } = useI18n()
const router = useRouter()

// ── Catalog ──
const skus = ref<CustomerSkuOut[]>([])
const products = ref<CatalogProductOut[]>([])
const catalogHint = ref('')
const catalogLoading = ref(false)
const filterProductId = ref<number | null>(null)
const searchKeyword = ref('')

// ── Orders ──
const orders = ref<CustomerOrderListItem[]>([])
const ordersLoading = ref(false)

// ── Place order dialog ──
const orderDlgVisible = ref(false)
const orderSku = ref<CustomerSkuOut | null>(null)
const orderQty = ref(1)
const orderRemark = ref('')
const orderSubmitting = ref(false)

const activeTab = ref(0)

function productLabel(pid: number) {
  const p = products.value.find((x) => x.id === pid)
  return p ? (p.display_name || p.name) : `产品#${pid}`
}

function skuLabel(s: CustomerSkuOut) {
  return s.display_name || s.name || s.code
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: t('customer.status.draft'),
    pending_confirm: t('customer.status.pendingConfirm'),
    confirmed: t('customer.status.confirmed'),
    producing: t('customer.status.producing'),
    done: t('customer.status.done'),
    shipped: t('customer.status.shipped'),
    cancelled: t('customer.status.cancelled'),
  }
  return map[s] || s
}

function statusTag(s: string): TagType {
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

const filteredSkus = computed(() => {
  let list = skus.value
  if (filterProductId.value) {
    list = list.filter((s) => s.product_id === filterProductId.value)
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    list = list.filter((s) =>
      s.code.toLowerCase().includes(kw) ||
      s.name.toLowerCase().includes(kw) ||
      (s.color || '').toLowerCase().includes(kw) ||
      (s.material || '').toLowerCase().includes(kw)
    )
  }
  return list
})

async function loadCatalog() {
  catalogLoading.value = true
  try {
    const resp = await getCatalog()
    skus.value = resp?.items ?? []
    products.value = resp?.products ?? []
    catalogHint.value = resp?.hint ?? ''
    if (catalogHint.value) {
      showToast(catalogHint.value)
    }
  } finally {
    catalogLoading.value = false
  }
}

async function loadOrders() {
  ordersLoading.value = true
  try {
    const resp = await listMyOrders()
    orders.value = resp?.items ?? []
  } finally {
    ordersLoading.value = false
  }
}

function openPlaceOrder(sku: CustomerSkuOut) {
  orderSku.value = sku
  orderQty.value = 1
  orderRemark.value = ''
  orderDlgVisible.value = true
}

async function submitOrder() {
  if (!orderSku.value || orderQty.value < 1) return
  orderSubmitting.value = true
  showLoadingToast({ message: t('customer.orderDetail.submitting'), duration: 0 })
  try {
    const result = await placeOrder({
      items: [
        {
          sku_id: orderSku.value.id,
          qty: orderQty.value,
          remark: orderRemark.value.trim() || undefined,
        },
      ],
      remark: orderRemark.value.trim() || undefined,
      submit: true,
    })
    closeToast()
    await showDialog({
      title: t('customer.order.orderSuccess'),
      message: `${t('customer.order.orderCode')}：${result.code}\n${t('customer.order.status')}：${statusLabel(result.status)}`,
      confirmButtonText: t('customer.order.viewOrder'),
    })
    orderDlgVisible.value = false
    router.push({ name: 'customerOrderDetail', params: { id: result.id } })
    loadOrders()
  } catch {
    closeToast()
  } finally {
    orderSubmitting.value = false
  }
}

function goOrderDetail(id: number) {
  router.push({ name: 'customerOrderDetail', params: { id } })
}

function goStatements() {
  router.push({ name: 'customerStatements' })
}

onMounted(() => {
  void Promise.all([loadCatalog(), loadOrders()]).catch(() => {})
})
</script>

<template>
  <div>
    <van-tabs v-model:active="activeTab" sticky>
      <van-tab :title="t('customer.order.tabBrowse')">
        <div class="px-3 pt-3">
          <van-search
            v-model="searchKeyword"
            :placeholder="t('customer.order.searchPlaceholder')"
            shape="round"
            @search="loadCatalog"
            @clear="searchKeyword = ''"
          />
        </div>

        <div class="flex gap-2 overflow-x-auto px-3 pb-2">
          <van-tag
            :type="filterProductId === null ? 'primary' : 'default'"
            round
            size="medium"
            style="cursor:pointer;flex-shrink:0;"
            @click="filterProductId = null"
          >{{ t('customer.order.all') }}</van-tag>
          <van-tag
            v-for="p in products"
            :key="p.id"
            :type="filterProductId === p.id ? 'primary' : 'default'"
            round
            size="medium"
            style="cursor:pointer;flex-shrink:0;"
            @click="filterProductId = p.id"
          >{{ p.display_name || p.name }}</van-tag>
        </div>

        <!-- SKU 卡片列表 -->
        <div class="px-3">
          <div
            v-for="s in filteredSkus"
            :key="s.id"
            class="mb-3 rounded-xl bg-white p-3 shadow-sm"
          >
            <div class="flex items-start justify-between">
              <div class="min-w-0 flex-1">
                <div class="font-semibold">{{ skuLabel(s) }}</div>
                <div class="mt-1.5 space-y-0.5 text-xs text-zinc-500">
                  <div v-if="s.color">{{ t('customer.order.color') }}{{ s.color }}</div>
                  <div v-if="s.material">{{ t('customer.order.material') }}{{ s.material }}</div>
                  <div v-if="s.spec">{{ t('customer.order.spec') }}{{ s.spec }}</div>
                  <div>{{ t('customer.order.product') }}<span class="text-zinc-700">{{ productLabel(s.product_id) }}</span></div>
                  <div v-if="s.remark" class="mt-1 text-zinc-400">{{ s.remark }}</div>
                </div>
              </div>
              <van-button
                size="small"
                type="primary"
                round
                class="shrink-0 ml-2"
                @click="openPlaceOrder(s)"
              >{{ t('customer.order.orderNow') }}</van-button>
            </div>
          </div>
          <van-empty v-if="!filteredSkus.length && !catalogLoading" :description="t('customer.order.noProduct')" />
        </div>
      </van-tab>

      <van-tab :title="t('customer.order.tabOrders')">
        <div class="px-3 pt-3">
          <van-loading v-if="ordersLoading" class="mx-auto" />
          <div v-else-if="orders.length">
            <div
              v-for="o in orders"
              :key="o.id"
              class="mb-3 cursor-pointer rounded-xl bg-white p-3 shadow-sm"
              @click="goOrderDetail(o.id)"
            >
              <div class="flex items-center justify-between">
                <div class="font-mono text-sm font-medium">{{ o.code }}</div>
                <van-tag :type="statusTag(o.status)" size="medium">{{ statusLabel(o.status) }}</van-tag>
              </div>
              <div class="mt-1.5 text-xs text-zinc-400">
                <span>{{ t('customer.order.createdAt') }} {{ o.created_at?.slice(0, 16).replace('T', ' ') }}</span>
                <span v-if="o.due_date" class="ml-3">{{ t('customer.order.dueDate') }}{{ o.due_date }}</span>
              </div>
            </div>
          </div>
          <van-empty v-else :description="t('customer.order.noOrder')" />
        </div>
      </van-tab>

      <van-tab :title="t('customer.order.tabStatements')">
        <div class="px-4 pt-6">
          <van-button block plain round @click="router.push({ name: 'profile' })">{{ t('customer.order.goPersonal') }}</van-button>
          <van-button block type="primary" round class="mt-2" @click="goStatements">{{ t('customer.order.viewStatements') }}</van-button>
          <div class="mt-4 text-center text-xs text-zinc-400">{{ t('customer.order.viewStatementsHint') }}</div>
        </div>
      </van-tab>
    </van-tabs>

    <van-action-sheet v-model:show="orderDlgVisible" :title="t('customer.order.confirmOrder')" closeable>
      <div class="px-4 pb-6">
        <div v-if="orderSku" class="mb-4 rounded-lg bg-blue-50 p-3 text-sm">
          <div class="font-semibold">{{ skuLabel(orderSku) }}</div>
          <div class="mt-1 text-xs text-zinc-600" v-if="orderSku.color || orderSku.material || orderSku.spec">
            <span v-if="orderSku.color">颜色：{{ orderSku.color }}　</span>
            <span v-if="orderSku.material">材料：{{ orderSku.material }}　</span>
            <span v-if="orderSku.spec">规格：{{ orderSku.spec }}</span>
          </div>
        </div>

          <van-cell-group inset>
          <van-field
            v-model.number="orderQty"
            :label="t('customer.order.quantity')"
            type="number"
            :min="1"
            :placeholder="t('customer.order.quantityPlaceholder')"
          />
          <van-field
            v-model="orderRemark"
            :label="t('customer.order.remark')"
            type="textarea"
            :placeholder="t('customer.order.remarkPlaceholder')"
            rows="2"
          />
        </van-cell-group>

        <div class="mt-4 px-2">
          <van-button
            block
            type="primary"
            round
            size="large"
            :loading="orderSubmitting"
            :disabled="orderQty < 1"
            @click="submitOrder"
          >
            {{ t('customer.order.submitOrder') }}
          </van-button>
        </div>
      </div>
    </van-action-sheet>
  </div>
</template>
