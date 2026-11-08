<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
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

// ── Cart（多行下单清单，仅存本地，单价一律以服务端价目表为准）──
interface CartLine {
  sku: CustomerSkuOut
  qty: number
}

const cart = ref<CartLine[]>([])
const cartVisible = ref(false)
const orderRemark = ref('')
const orderSubmitting = ref(false)

const activeTab = ref(0)

/**
 * 金额统一用「万分之一」整数运算。
 * 理由：单价是 Numeric(12,4)，用浮点乘加会在多行下单时产生 0.01 级别漂移，
 * 与后端 recalc_order_amount() 的口径对不上，客户会看到「前端 99.99 / 后台 100.00」。
 */
const PRICE_SCALE = 10000

const CURRENCY_SYMBOL: Record<string, string> = {
  CNY: '¥',
  USD: '$',
  EUR: '€',
  KRW: '₩',
  JPY: 'JP¥',
  HKD: 'HK$',
  GBP: '£',
}

/** 零小数币种不显示小数位 */
const ZERO_DECIMAL = new Set(['KRW', 'JPY', 'VND'])

function priceUnits(raw?: string | number | null): number {
  if (raw === undefined || raw === null || raw === '') return 0
  const n = Number(raw)
  if (!Number.isFinite(n) || n < 0) return 0
  return Math.round(n * PRICE_SCALE)
}

interface TierHit {
  min_qty: number
  price: string
}

/** 档位按起点升序；后端已排好序，这里再排一次防止脏数据打乱命中逻辑 */
function sortedTiers(sku: CustomerSkuOut): TierHit[] {
  const list = (sku.tiers ?? []).map((x) => ({ min_qty: Number(x.min_qty), price: String(x.price) }))
  return list.sort((a, b) => a.min_qty - b.min_qty)
}

function hasTiers(sku: CustomerSkuOut): boolean {
  return sortedTiers(sku).length > 0
}

/** 按数量命中档位，与后端 `pick_tier` 同口径：取满足 min_qty 的最大档 */
function hitTier(sku: CustomerSkuOut, qty: number): TierHit | null {
  const tiers = sortedTiers(sku)
  if (!tiers.length) return null
  let hit = tiers[0]
  for (const tier of tiers) {
    if (tier.min_qty <= qty) hit = tier
    else break
  }
  return hit
}

/** 下一档（更高数量、更低单价）；已是最高档返回 null */
function nextTier(sku: CustomerSkuOut, qty: number): TierHit | null {
  for (const tier of sortedTiers(sku)) {
    if (tier.min_qty > qty) return tier
  }
  return null
}

/** 结算单价：有阶梯按数量命中，无阶梯用价目表单价。后端下单会再算一次，前端只做展示 */
function lineUnitPrice(line: CartLine): string | number {
  const tier = hitTier(line.sku, line.qty)
  return tier ? tier.price : line.sku.unit_price
}

function lineUnitPriceText(line: CartLine): string {
  return fmtMoney(priceUnits(lineUnitPrice(line)), line.sku.currency || 'CNY', 4)
}

/** 「再买 N 件，单价降至 X」提示；已是最高档返回空串由 v-if 挡住 */
function tierNextText(sku: CustomerSkuOut, qty: number): string {
  const nxt = nextTier(sku, qty)
  if (!nxt) return ''
  return t('customer.order.tierNext', {
    qty: nxt.min_qty,
    price: fmtMoney(priceUnits(nxt.price), sku.currency || 'CNY', 4),
  })
}

function lineSubtotalUnits(line: CartLine): number {
  return priceUnits(lineUnitPrice(line)) * line.qty
}

const cartTotalUnits = computed(() => cart.value.reduce((sum, l) => sum + lineSubtotalUnits(l), 0))
const cartCount = computed(() => cart.value.length)
const cartQtyTotal = computed(() => cart.value.reduce((sum, l) => sum + l.qty, 0))
const cartCurrency = computed(() => (cart.value[0]?.sku.currency || 'CNY').toUpperCase())

function fmtMoney(units: number, currency: string, maxDigits = 2): string {
  const cur = (currency || 'CNY').toUpperCase()
  const digits = ZERO_DECIMAL.has(cur) ? 0 : maxDigits
  let body = (units / PRICE_SCALE).toFixed(digits)
  if (digits > 2) body = body.replace(/0+$/, '').replace(/\.$/, '')
  const sym = CURRENCY_SYMBOL[cur]
  return sym ? `${sym}${body}` : `${body} ${cur}`
}

/** 单价展示保留 4 位有效小数（客户价目常带分以下精度），并去掉尾随 0 */
function unitPriceText(sku: CustomerSkuOut): string {
  return fmtMoney(priceUnits(sku.unit_price), sku.currency || 'CNY', 4)
}

function lineSubtotalText(line: CartLine): string {
  return fmtMoney(lineSubtotalUnits(line), line.sku.currency || 'CNY', 2)
}

function isPriced(sku: CustomerSkuOut): boolean {
  return sku.priced === true && priceUnits(sku.unit_price) > 0
}

function minQtyOf(sku: CustomerSkuOut): number {
  return Math.max(1, Number(sku.min_qty || 1))
}

function inCart(skuId: number): boolean {
  return cart.value.some((l) => l.sku.id === skuId)
}

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
    pending_confirm: 'warning',
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

// ── Cart 操作 ──
function addToCart(sku: CustomerSkuOut) {
  if (!isPriced(sku)) {
    showToast(t('customer.order.unpriced'))
    return
  }
  if (inCart(sku.id)) {
    showToast(t('customer.order.inCart'))
    return
  }
  // 同一张订单只允许一种币种：混币种会让 orders.amount 失去意义
  if (cart.value.length && cartCurrency.value !== (sku.currency || 'CNY').toUpperCase()) {
    showToast(t('customer.order.currencyMismatch'))
    return
  }
  cart.value.push({ sku, qty: minQtyOf(sku) })
  showToast(t('customer.order.addedToCart'))
}

function removeLine(skuId: number) {
  cart.value = cart.value.filter((l) => l.sku.id !== skuId)
  if (!cart.value.length) {
    cartVisible.value = false
  }
}

async function clearCart() {
  try {
    await showConfirmDialog({
      title: t('customer.order.clearCart'),
      message: t('customer.order.confirmClearCart'),
    })
  } catch {
    return
  }
  cart.value = []
  cartVisible.value = false
}

function openCart() {
  if (!cart.value.length) {
    showToast(t('customer.order.cartEmpty'))
    return
  }
  cartVisible.value = true
}

/** 提交前把每一行都校验一遍：低于起订量、未定价、跨币种都不允许提交 */
function validateCart(): string | null {
  if (!cart.value.length) return t('customer.order.cartEmpty')
  for (const line of cart.value) {
    if (!isPriced(line.sku)) return t('customer.order.unpriced')
    if (line.qty < minQtyOf(line.sku)) {
      return t('customer.order.belowMinQty', { min: minQtyOf(line.sku) })
    }
  }
  return null
}

async function submitOrder() {
  const err = validateCart()
  if (err) {
    showToast(err)
    return
  }
  orderSubmitting.value = true
  showLoadingToast({ message: t('customer.orderDetail.submitting'), duration: 0 })
  try {
    const result = await placeOrder({
      items: cart.value.map((l) => ({ sku_id: l.sku.id, qty: l.qty })),
      remark: orderRemark.value.trim() || undefined,
      submit: true,
    })
    closeToast()
    // 金额用服务端返回值展示：客户看到的就是写进 orders.amount 的数字
    await showDialog({
      title: t('customer.order.orderSuccess'),
      message: [
        `${t('customer.order.orderCode')}：${result.code}`,
        `${t('customer.order.status')}：${statusLabel(result.status)}`,
        `${t('customer.order.amount')}：${fmtMoney(priceUnits(result.amount), result.currency, 2)}`,
      ].join('\n'),
      confirmButtonText: t('customer.order.viewOrder'),
    })
    cart.value = []
    orderRemark.value = ''
    cartVisible.value = false
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
  <div :class="cart.length ? 'pb-32' : ''">
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

              <div class="shrink-0 ml-2 flex flex-col items-end">
                <template v-if="isPriced(s)">
                  <div class="text-base font-semibold text-rose-600">
                    {{ unitPriceText(s) }}
                    <span v-if="hasTiers(s)" class="text-[11px] font-normal text-zinc-400">
                      {{ t('customer.order.tierFrom') }}
                    </span>
                  </div>
                  <div class="mt-0.5 text-[11px] text-zinc-400">
                    {{ t('customer.order.unitPrice') }}
                    <span v-if="minQtyOf(s) > 1"> · {{ t('customer.order.minQty') }} {{ minQtyOf(s) }}</span>
                  </div>
                  <div v-if="nextTier(s, minQtyOf(s))" class="mt-0.5 text-right text-[11px] text-rose-500">
                    {{ tierNextText(s, minQtyOf(s)) }}
                  </div>
                  <van-button
                    size="small"
                    :type="inCart(s.id) ? 'default' : 'primary'"
                    round
                    class="mt-2"
                    @click="addToCart(s)"
                  >{{ inCart(s.id) ? t('customer.order.inCart') : t('customer.order.addToCart') }}</van-button>
                </template>
                <template v-else>
                  <van-tag type="warning" size="medium">{{ t('customer.order.unpriced') }}</van-tag>
                  <div class="mt-1 text-[11px] text-zinc-400">{{ t('customer.order.unpricedHint') }}</div>
                </template>
              </div>
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

    <!-- 购物清单悬浮条：压在客户 tabbar（50px）之上 -->
    <div
      v-if="cart.length && !cartVisible"
      class="cart-bar"
    >
      <div class="flex min-w-0 items-center gap-2">
        <van-icon name="shopping-cart-o" size="22" class="shrink-0" />
        <div class="min-w-0">
          <div class="text-xs text-zinc-400">
            {{ t('customer.order.cartSummary', { lines: cartCount, qty: cartQtyTotal }) }}
          </div>
          <div class="truncate text-sm font-semibold text-rose-600">
            {{ fmtMoney(cartTotalUnits, cartCurrency, 2) }}
          </div>
        </div>
      </div>
      <van-button type="primary" round size="small" class="shrink-0" @click="openCart">
        {{ t('customer.order.checkout') }}
      </van-button>
    </div>

    <!-- 清单弹层 -->
    <van-action-sheet v-model:show="cartVisible" :title="t('customer.order.cart')" closeable>
      <div class="max-h-[70vh] overflow-y-auto px-4 pb-6">
        <div
          v-for="line in cart"
          :key="line.sku.id"
          class="mb-3 rounded-lg bg-zinc-50 p-3"
        >
          <div class="flex items-start justify-between">
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium">{{ skuLabel(line.sku) }}</div>
              <div class="mt-0.5 text-xs text-zinc-500">
                {{ t('customer.order.unitPrice') }} {{ lineUnitPriceText(line) }}
                <span v-if="minQtyOf(line.sku) > 1"> · {{ t('customer.order.minQty') }} {{ minQtyOf(line.sku) }}</span>
              </div>
              <div v-if="tierNextText(line.sku, line.qty)" class="mt-0.5 text-xs text-rose-500">
                {{ tierNextText(line.sku, line.qty) }}
              </div>
            </div>
            <van-icon name="cross" class="ml-2 shrink-0 text-zinc-400" @click="removeLine(line.sku.id)" />
          </div>
          <div class="mt-2 flex items-center justify-between">
            <van-stepper
              v-model="line.qty"
              :min="minQtyOf(line.sku)"
              :max="999999"
              integer
              input-width="52px"
              button-size="26px"
            />
            <div class="text-sm font-semibold text-rose-600">{{ lineSubtotalText(line) }}</div>
          </div>
        </div>

        <div class="mt-3 flex items-center justify-between rounded-lg bg-rose-50 px-3 py-2">
          <span class="text-sm text-zinc-600">{{ t('customer.order.totalAmount') }}</span>
          <span class="text-lg font-bold text-rose-600">{{ fmtMoney(cartTotalUnits, cartCurrency, 2) }}</span>
        </div>

        <van-cell-group inset class="mt-3">
          <van-field
            v-model="orderRemark"
            :label="t('customer.order.remark')"
            type="textarea"
            :placeholder="t('customer.order.remarkPlaceholder')"
            rows="2"
          />
        </van-cell-group>

        <div class="mt-2 px-2 text-center text-[11px] text-zinc-400">{{ t('customer.order.priceHint') }}</div>

        <div class="mt-3 flex gap-2 px-2">
          <van-button block plain round @click="clearCart">{{ t('customer.order.clearCart') }}</van-button>
          <van-button
            block
            type="primary"
            round
            :loading="orderSubmitting"
            @click="submitOrder"
          >{{ t('customer.order.submitOrder') }}</van-button>
        </div>
      </div>
    </van-action-sheet>
  </div>
</template>

<style scoped>
.cart-bar {
  position: fixed;
  left: 0;
  right: 0;
  /* 客户 tabbar 固定 50px 高，清单条压在它上方，避免遮住导航 */
  bottom: calc(50px + env(safe-area-inset-bottom, 0px));
  z-index: 99;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
  box-shadow: 0 -2px 8px rgb(0 0 0 / 6%);
}
</style>
