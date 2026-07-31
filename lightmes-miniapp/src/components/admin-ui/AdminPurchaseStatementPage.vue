<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索对账单号" @confirm="reload" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新建</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无对账单" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.code }}</text>
          <text class="adm-list-badge tone-active">{{ statusLabel(String(item.status)) }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '供应商', value: item.supplier_name || '—' },
          { label: '金额', value: `¥${item.amount}` },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="openDetail(item)">详情</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="createVisible" class="mask" @tap="createVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">新建采购对账</text></view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">供应商*</text>
            <picker :range="supplierLabels" @change="onSupplierPick">
              <view class="input picker">{{ supplierLabels[supplierIndex] || '请选择' }}</view>
            </picker>
          </view>
          <view class="field"><text class="label">期间起</text><input v-model="form.period_from" class="input" placeholder="YYYY-MM-DD" /></view>
          <view class="field"><text class="label">期间止</text><input v-model="form.period_to" class="input" placeholder="YYYY-MM-DD" /></view>
        </scroll-view>
        <view class="foot"><button class="btn primary" :loading="saving" @tap="submitCreate">创建</button></view>
      </view>
    </view>

    <view v-if="detailVisible" class="mask" @tap="detailVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">{{ detail?.code }}</text></view>
        <scroll-view scroll-y class="body">
          <view class="kv"><text class="k">供应商</text><text class="v">{{ detail?.supplier_name }}</text></view>
          <view class="kv"><text class="k">金额</text><text class="v">¥{{ detail?.amount }}</text></view>
          <view class="kv"><text class="k">状态</text><text class="v">{{ statusLabel(String(detail?.status)) }}</text></view>
          <view v-for="(it, idx) in detailItems" :key="idx" class="line-info">
            <text>{{ it.purchase_order_code || it.purchase_order_id }} · 入库 {{ it.received_qty }} · ¥{{ it.amount }}</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button v-if="detail?.status === 'draft'" class="btn warn" @tap="confirmStmt">确认</button>
          <button v-if="detail?.status === 'confirmed'" class="btn primary" @tap="markPaid">标记已付</button>
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
import { purchaseAdminApi } from '@/api/admin/purchase'
import { usePermission } from '@/composables/usePermission'

type Stmt = { id: number; code: string; supplier_id?: number; supplier_name?: string; amount?: number; status: string; period_from?: string; period_to?: string }
type StmtItem = { purchase_order_id: number; purchase_order_code?: string; received_qty: number; amount: number }

const { requirePermission } = usePermission()
const items = ref<Stmt[]>([])
const suppliers = ref<{ id: number; name: string; code?: string }[]>([])
const loading = ref(false)
const keyword = ref('')
const createVisible = ref(false)
const detailVisible = ref(false)
const saving = ref(false)
const detail = ref<Stmt | null>(null)
const detailItems = ref<StmtItem[]>([])
const supplierIndex = ref(0)
const form = reactive({ period_from: '', period_to: '' })
const supplierLabels = computed(() => suppliers.value.map((s) => `${s.name}(${s.code || s.id})`))

onShow(async () => {
  if (!requirePermission('purchase.manage')) return
  const r = await purchaseAdminApi.listSuppliers()
  suppliers.value = r.items || []
  await reload()
})

function statusLabel(s: string) {
  return ({ draft: '草稿', confirmed: '已确认', paid: '已付款' } as Record<string, string>)[s] || s
}

async function reload() {
  loading.value = true
  try {
    const r = await purchaseAdminApi.listStatements({ limit: 50, keyword: keyword.value.trim() || undefined })
    items.value = (r.items || []) as Stmt[]
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onSupplierPick(e: { detail: { value: number } }) { supplierIndex.value = Number(e.detail.value) }
function openCreate() {
  form.period_from = ''
  form.period_to = ''
  supplierIndex.value = 0
  createVisible.value = true
}

async function submitCreate() {
  const sup = suppliers.value[supplierIndex.value]
  if (!sup) {
    uni.showToast({ title: '请选择供应商', icon: 'none' })
    return
  }
  saving.value = true
  try {
    await purchaseAdminApi.createStatement({
      supplier_id: sup.id,
      period_from: form.period_from.trim() || null,
      period_to: form.period_to.trim() || null,
    })
    uni.showToast({ title: '创建成功', icon: 'success' })
    createVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '创建失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function openDetail(row: Stmt) {
  try {
    const d = await purchaseAdminApi.getStatement(row.id) as Stmt & { items?: StmtItem[] }
    detail.value = d
    detailItems.value = d.items || []
    detailVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

async function confirmStmt() {
  if (!detail.value) return
  await purchaseAdminApi.confirmStatement(detail.value.id)
  uni.showToast({ title: '已确认', icon: 'success' })
  detailVisible.value = false
  await reload()
}

async function markPaid() {
  if (!detail.value) return
  await purchaseAdminApi.markStatementPaid(detail.value.id)
  uni.showToast({ title: '已标记付款', icon: 'success' })
  detailVisible.value = false
  await reload()
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.add-btn { background: linear-gradient(135deg, #f97316, #ea580c); color: #fff; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 80vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 55vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.picker { color: #334155; }
.kv { display: flex; gap: 16rpx; margin-bottom: 12rpx; font-size: 26rpx; }
.k { color: #64748b; width: 120rpx; }
.v { flex: 1; }
.line-info { font-size: 26rpx; padding: 12rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.primary { background: linear-gradient(135deg, #f97316, #ea580c); color: #fff; }
.warn { background: #fbbf24; color: #78350f; }
</style>
