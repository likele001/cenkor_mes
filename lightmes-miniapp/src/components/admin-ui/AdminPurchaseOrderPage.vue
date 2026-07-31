<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索单号/备注" @confirm="reload" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新建</button>
    </view>

    <MListLayout :items="items" :loading="loading" empty-text="暂无采购单" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.code || item.id }}</text>
          <text class="adm-list-badge tone-active">{{ statusLabel(String(item.status)) }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '供应商', value: item.supplier_name || '—' },
          { label: '金额', value: item.total_amount != null ? `¥${item.total_amount}` : '—' },
          { label: '创建时间', value: item.created_at?.slice(0, 16) || '—' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="openDetail(item)">详情</button>
        </view>
      </template>
    </MListLayout>

    <!-- 新建 -->
    <view v-if="createVisible" class="mask" @tap="createVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">新建采购单</text></view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">供应商*</text>
            <picker :range="supplierLabels" @change="onSupplierPick">
              <view class="input picker">{{ supplierLabels[supplierIndex] || '请选择供应商' }}</view>
            </picker>
          </view>
          <view class="field"><text class="label">单号</text><input v-model="form.code" class="input" placeholder="留空自动生成" /></view>
          <view class="field"><text class="label">备注</text><textarea v-model="form.remark" class="input area" /></view>
          <view class="lines-head">
            <text class="label">明细*</text>
            <text class="link" @tap="addLine">+ 添加行</text>
          </view>
          <view v-for="(line, idx) in lines" :key="idx" class="line-card">
            <picker :range="materialLabels" @change="(e) => onMaterialPick(idx, e)">
              <view class="input picker flex1">{{ materialLabels[line.materialIndex ?? 0] || '选物料' }}</view>
            </picker>
            <input v-model="line.qty" class="input qty" type="digit" placeholder="数量" />
            <text class="del" @tap="removeLine(idx)">删</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button class="btn primary" :loading="saving" @tap="submitCreate">创建</button>
        </view>
      </view>
    </view>

    <!-- 详情 / 操作 -->
    <view v-if="detailVisible" class="mask" @tap="detailVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">{{ detail?.code || '采购单' }}</text>
          <text class="tag">{{ statusLabel(String(detail?.status || '')) }}</text>
        </view>
        <scroll-view scroll-y class="body">
          <view class="kv"><text class="k">供应商</text><text class="v">{{ detail?.supplier_name || '—' }}</text></view>
          <view class="kv"><text class="k">备注</text><text class="v">{{ detail?.remark || '—' }}</text></view>
          <view class="section-title">明细</view>
          <view v-for="(it, idx) in detail?.items || []" :key="idx" class="line-info">
            <text class="mat">{{ it.material_code }} {{ it.material_name }}</text>
            <text class="nums">采购 {{ it.qty }} · 已入 {{ it.received_qty ?? 0 }} · 剩余 {{ remainQty(it) }}</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button v-if="canConfirm" class="btn warn" :loading="acting" @tap="onConfirm">确认</button>
          <button v-if="canReceive" class="btn primary" @tap="openReceive">入库</button>
          <button v-if="canCancel" class="btn ghost danger" :loading="acting" @tap="onCancel">作废</button>
        </view>
      </view>
    </view>

    <!-- 入库 -->
    <view v-if="receiveVisible" class="mask" @tap="receiveVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">采购入库</text></view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">仓库*</text>
            <picker :range="warehouseLabels" @change="onWarehousePick">
              <view class="input picker">{{ warehouseLabels[warehouseIndex] || '请选择仓库' }}</view>
            </picker>
          </view>
          <view v-for="(it, idx) in receiveLines" :key="idx" class="recv-card">
            <text class="mat">{{ it.material_code }} {{ it.material_name }}</text>
            <text class="nums">剩余 {{ it.remain }}</text>
            <input
              v-model="it.receive_qty"
              class="input qty"
              type="number"
              placeholder="本次入库"
              :disabled="it.remain <= 0"
            />
          </view>
        </scroll-view>
        <view class="foot">
          <button class="btn primary" :loading="acting" @tap="submitReceive">提交入库</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { purchaseAdminApi, type PurchaseOrder, type PurchaseOrderItem } from '@/api/admin/purchase'
import { usePermission } from '@/composables/usePermission'

type Line = { materialIndex?: number; material_id?: number; qty: string }
type RecvLine = PurchaseOrderItem & { remain: number; receive_qty: string }

const { requirePermission } = usePermission()
const items = ref<PurchaseOrder[]>([])
const loading = ref(false)
const keyword = ref('')
const saving = ref(false)
const acting = ref(false)
const createVisible = ref(false)
const detailVisible = ref(false)
const receiveVisible = ref(false)
const detail = ref<PurchaseOrder | null>(null)
const suppliers = ref<{ id: number; name: string; code?: string }[]>([])
const materials = ref<{ id: number; name: string; code?: string }[]>([])
const warehouses = ref<{ id: number; name: string; code: string }[]>([])
const supplierIndex = ref(0)
const warehouseIndex = ref(0)
const form = reactive({ code: '', remark: '' })
const lines = ref<Line[]>([{ qty: '1', materialIndex: 0 }])
const receiveLines = ref<RecvLine[]>([])

const supplierLabels = computed(() => suppliers.value.map((s) => `${s.name}(${s.code || s.id})`))
const materialLabels = computed(() => materials.value.map((m) => `${m.name}(${m.code || m.id})`))
const warehouseLabels = computed(() => warehouses.value.map((w) => `${w.name}(${w.code})`))

const canConfirm = computed(() => detail.value?.status === 'draft')
const canReceive = computed(() => ['confirmed', 'partial_received'].includes(String(detail.value?.status)))
const canCancel = computed(() => ['draft', 'confirmed', 'partial_received'].includes(String(detail.value?.status)))

onShow(async () => {
  if (!requirePermission('purchase.manage')) return
  await loadOptions()
  await reload()
})

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    confirmed: '已确认',
    partial_received: '部分入库',
    received: '已入库',
    canceled: '已作废',
  }
  return map[s] || s || '-'
}

function remainQty(it: PurchaseOrderItem) {
  return Math.max(0, Number(it.qty || 0) - Number(it.received_qty || 0))
}

async function loadOptions() {
  try {
    const [sup, mat, wh] = await Promise.all([
      purchaseAdminApi.listSuppliers(),
      purchaseAdminApi.listMaterials(),
      purchaseAdminApi.listWarehouses(),
    ])
    suppliers.value = sup.items || []
    materials.value = mat.items || []
    warehouses.value = wh.items || []
  } catch {
    suppliers.value = []
    materials.value = []
    warehouses.value = []
  }
}

async function reload() {
  loading.value = true
  try {
    const r = await purchaseAdminApi.list({ limit: 50, keyword: keyword.value.trim() || undefined })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.code = ''
  form.remark = ''
  supplierIndex.value = 0
  lines.value = [{ qty: '1', materialIndex: 0 }]
  createVisible.value = true
}

function onSupplierPick(e: { detail: { value: number } }) {
  supplierIndex.value = Number(e.detail.value)
}
function onWarehousePick(e: { detail: { value: number } }) {
  warehouseIndex.value = Number(e.detail.value)
}
function onMaterialPick(idx: number, e: { detail: { value: number } }) {
  lines.value[idx].materialIndex = Number(e.detail.value)
  lines.value[idx].material_id = materials.value[lines.value[idx].materialIndex!]?.id
}
function addLine() {
  lines.value.push({ qty: '1', materialIndex: 0 })
}
function removeLine(idx: number) {
  if (lines.value.length <= 1) return
  lines.value.splice(idx, 1)
}

function buildCreatePayload() {
  const supplier = suppliers.value[supplierIndex.value]
  if (!supplier) throw new Error('请选择供应商')
  const mapped = lines.value.map((ln) => {
    const mat = materials.value[ln.materialIndex ?? 0]
    if (!mat) throw new Error('请选择物料')
    const qty = Number(ln.qty)
    if (!qty || qty < 1) throw new Error('数量须≥1')
    return { material_id: mat.id, qty, unit_price: null, remark: null }
  })
  if (!mapped.length) throw new Error('请添加明细')
  return {
    supplier_id: supplier.id,
    code: form.code.trim() || null,
    remark: form.remark.trim() || null,
    items: mapped,
  }
}

async function submitCreate() {
  saving.value = true
  try {
    await purchaseAdminApi.create(buildCreatePayload())
    uni.showToast({ title: '创建成功', icon: 'success' })
    createVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '创建失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function openDetail(row: PurchaseOrder) {
  try {
    detail.value = await purchaseAdminApi.get(row.id)
    detailVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

async function onConfirm() {
  if (!detail.value) return
  acting.value = true
  try {
    detail.value = await purchaseAdminApi.confirm(detail.value.id)
    uni.showToast({ title: '已确认', icon: 'success' })
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '确认失败', icon: 'none' })
  } finally {
    acting.value = false
  }
}

function openReceive() {
  if (!detail.value) return
  warehouseIndex.value = 0
  receiveLines.value = (detail.value.items || []).map((it) => ({
    ...it,
    remain: remainQty(it),
    receive_qty: String(remainQty(it) > 0 ? remainQty(it) : 0),
  }))
  receiveVisible.value = true
}

async function submitReceive() {
  if (!detail.value) return
  const wh = warehouses.value[warehouseIndex.value]
  if (!wh) {
    uni.showToast({ title: '请选择仓库', icon: 'none' })
    return
  }
  const itemsPayload = receiveLines.value
    .filter((x) => Number(x.receive_qty) > 0)
    .map((x) => ({ item_id: x.id!, receive_qty: Number(x.receive_qty) }))
  if (!itemsPayload.length) {
    uni.showToast({ title: '请填写入库数量', icon: 'none' })
    return
  }
  acting.value = true
  try {
    detail.value = await purchaseAdminApi.receive(detail.value.id, {
      warehouse_id: wh.id,
      items: itemsPayload,
    })
    uni.showToast({ title: '入库成功', icon: 'success' })
    receiveVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '入库失败', icon: 'none' })
  } finally {
    acting.value = false
  }
}

function onCancel() {
  if (!detail.value) return
  uni.showModal({
    title: '作废采购单',
    content: '确认作废该采购单？',
    success: async (res) => {
      if (!res.confirm || !detail.value) return
      acting.value = true
      try {
        detail.value = await purchaseAdminApi.cancel(detail.value.id)
        uni.showToast({ title: '已作废', icon: 'success' })
        detailVisible.value = false
        await reload()
      } catch (e: unknown) {
        uni.showToast({ title: (e as Error).message || '作废失败', icon: 'none' })
      } finally {
        acting.value = false
      }
    },
  })
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.add-btn { background: linear-gradient(135deg, #f97316, #ea580c); color: #fff; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; display: flex; align-items: center; justify-content: space-between; }
.title { font-size: 32rpx; font-weight: 700; }
.tag { font-size: 24rpx; color: #ea580c; background: #ffedd5; padding: 6rpx 16rpx; border-radius: 999rpx; }
.body { max-height: 58vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.area { min-height: 120rpx; width: 100%; }
.picker { color: #334155; }
.flex1 { flex: 1; }
.lines-head { display: flex; justify-content: space-between; align-items: center; margin: 12rpx 0; }
.link { color: #ea580c; font-size: 26rpx; }
.line-card { display: flex; gap: 8rpx; align-items: center; margin-bottom: 12rpx; }
.qty { width: 160rpx; flex-shrink: 0; }
.del { color: #ef4444; font-size: 24rpx; padding: 8rpx; }
.kv { display: flex; gap: 16rpx; margin-bottom: 12rpx; font-size: 26rpx; }
.k { color: #64748b; width: 120rpx; flex-shrink: 0; }
.v { color: #334155; flex: 1; }
.section-title { font-size: 28rpx; font-weight: 600; margin: 20rpx 0 12rpx; }
.line-info, .recv-card { background: #f8fafc; border-radius: 12rpx; padding: 16rpx; margin-bottom: 12rpx; }
.mat { display: block; font-size: 28rpx; font-weight: 600; }
.nums { display: block; font-size: 24rpx; color: #64748b; margin-top: 6rpx; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #f97316, #ea580c); color: #fff; }
.warn { background: #fbbf24; color: #78350f; }
.danger { color: #ef4444; }
</style>
