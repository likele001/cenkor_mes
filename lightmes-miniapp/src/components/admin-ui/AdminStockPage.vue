<template>
  <view class="adm-page">
    <view class="toolbar">
      <picker :range="warehouseLabels" @change="onWarehouseFilter">
        <view class="filter">{{ warehouseLabels[warehouseFilterIndex] || '全部仓库' }}</view>
      </picker>
      <input v-model="keyword" class="search" placeholder="SKU编码/名称" @confirm="reload" />
    </view>

    <!-- 库存概览 -->
    <view v-if="!loading && items.length" class="adm-card overview">
      <view class="adm-stat-grid">
        <view class="stat-item">
          <text class="stat-val">{{ items.length }}</text>
          <text class="stat-lbl">SKU数</text>
        </view>
        <view class="stat-item">
          <text class="stat-val">{{ totalQty }}</text>
          <text class="stat-lbl">总库存量</text>
        </view>
        <view class="stat-item">
          <text class="stat-val">{{ zeroStockCount }}</text>
          <text class="stat-lbl">零库存</text>
        </view>
      </view>
    </view>

    <MListLayout :items="filtered" :loading="loading" empty-text="暂无库存" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.sku_name || item.sku_code }}</text>
          <text class="adm-list-badge" :class="item.qty <= 0 ? 'tone-danger' : 'tone-active'">{{ item.qty }} {{ item.unit || '' }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: 'SKU编码', value: item.sku_code || '—' },
          { label: '仓库', value: item.warehouse_name || '—' },
          { label: '库存数量', value: String(item.qty ?? 0) },
          { label: '最后更新', value: item.updated_at ? item.updated_at.slice(0, 16).replace('T', ' ') : '—' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn edit" @tap="openAdjust(item)">调整</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="adjustVisible" class="mask" @tap="adjustVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">库存调整</text></view>
        <scroll-view scroll-y class="body">
          <view class="kv"><text class="k">SKU</text><text class="v">{{ current?.sku_code }} {{ current?.sku_name }}</text></view>
          <view class="kv"><text class="k">仓库</text><text class="v">{{ current?.warehouse_name }}</text></view>
          <view class="kv"><text class="k">当前</text><text class="v">{{ current?.qty ?? 0 }}</text></view>
          <view class="field">
            <text class="label">变动数量*</text>
            <input v-model="changeQty" class="input" type="number" placeholder="正数入库，负数出库" />
          </view>
          <view class="field"><text class="label">备注</text><input v-model="remark" class="input" placeholder="调整原因" /></view>
        </scroll-view>
        <view class="foot">
          <button class="btn primary" :loading="saving" @tap="submitAdjust">确认调整</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { warehouseAdminApi, type StockRow } from '@/api/admin/warehouse'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<StockRow[]>([])
const warehouses = ref<{ id: number; name: string; code: string }[]>([])
const loading = ref(false)
const keyword = ref('')
const warehouseFilterIndex = ref(0)
const adjustVisible = ref(false)
const current = ref<StockRow | null>(null)
const changeQty = ref('')
const remark = ref('')
const saving = ref(false)

const warehouseLabels = computed(() => ['全部仓库', ...warehouses.value.map((w) => `${w.name}(${w.code})`)])
const totalQty = computed(() => items.value.reduce((s, x) => s + (x.qty ?? 0), 0))
const zeroStockCount = computed(() => items.value.filter((x) => !x.qty || x.qty <= 0).length)

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter((x) => {
    return (x.sku_code || '').toLowerCase().includes(kw) || (x.sku_name || '').toLowerCase().includes(kw)
  })
})

onShow(async () => {
  if (!requirePermission('warehouse.manage')) return
  await loadWarehouses()
  await reload()
})

async function loadWarehouses() {
  try {
    const r = await warehouseAdminApi.listWarehouses()
    warehouses.value = r.items || []
  } catch {
    warehouses.value = []
  }
}

async function reload() {
  loading.value = true
  try {
    const whId = warehouseFilterIndex.value > 0 ? warehouses.value[warehouseFilterIndex.value - 1]?.id : undefined
    const r = await warehouseAdminApi.listStocks({ warehouse_id: whId })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onWarehouseFilter(e: { detail: { value: number } }) {
  warehouseFilterIndex.value = Number(e.detail.value)
  reload()
}

function openAdjust(row: StockRow) {
  current.value = row
  changeQty.value = ''
  remark.value = ''
  adjustVisible.value = true
}

async function submitAdjust() {
  if (!current.value) return
  const qty = Number(changeQty.value)
  if (!qty || qty === 0) {
    uni.showToast({ title: '请输入非零变动数量', icon: 'none' })
    return
  }
  saving.value = true
  try {
    await warehouseAdminApi.adjustStock({
      warehouse_id: current.value.warehouse_id,
      sku_id: current.value.sku_id,
      change_qty: qty,
      remark: remark.value.trim() || undefined,
    })
    uni.showToast({ title: '调整成功', icon: 'success' })
    adjustVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '调整失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.filter { background: #fff; border-radius: 999rpx; padding: 16rpx 24rpx; font-size: 24rpx; max-width: 220rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.overview { padding: 20rpx 24rpx; }
.adm-stat-grid { display: flex; gap: 12rpx; }
.stat-item { flex: 1; text-align: center; background: #f8fafc; border-radius: 12rpx; padding: 16rpx 8rpx; }
.stat-val { display: block; font-size: 32rpx; font-weight: 700; color: #1e293b; }
.stat-lbl { display: block; font-size: 22rpx; color: #64748b; margin-top: 4rpx; }
.tone-danger { background: #fee2e2 !important; color: #b91c1c !important; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 75vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 50vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.kv { display: flex; gap: 16rpx; margin-bottom: 12rpx; font-size: 26rpx; }
.k { color: #64748b; width: 120rpx; }
.v { color: #334155; flex: 1; }
.foot { padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { border-radius: 12rpx; font-size: 28rpx; }
.primary { background: linear-gradient(135deg, #0ea5e9, #0284c7); color: #fff; }
</style>
