<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="month" class="search" placeholder="月份 YYYY-MM" @confirm="reload" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 记一笔</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无流水" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.biz_date }}</text>
          <text :class="['adm-list-badge', item.direction === 'in' ? 'tone-success' : 'tone-danger']">
            {{ item.direction === 'in' ? '收入' : '支出' }}
          </text>
        </view>
        <AdminKvGrid :rows="[
          { label: '类别', value: item.category || '—' },
          { label: '往来', value: partyLabel(item) },
          { label: '金额', value: `¥${fmt(item.amount)}` },
          { label: '备注', value: item.remark || '—' },
        ]" />
      </template>
    </MListLayout>

    <view v-if="formVisible" class="mask" @tap="formVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">新增流水</text></view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">方向*</text>
            <picker :range="directionLabels" @change="onDirectionPick">
              <view class="input picker">{{ directionLabels[directionIndex] }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="label">类别*</text>
            <picker :range="categoryLabels" @change="onCategoryPick">
              <view class="input picker">{{ categoryLabels[categoryIndex] }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="label">往来类型*</text>
            <picker :range="partyTypeLabels" @change="onPartyTypePick">
              <view class="input picker">{{ partyTypeLabels[partyTypeIndex] }}</view>
            </picker>
          </view>
          <view v-if="form.party_type === 'customer'" class="field">
            <text class="label">客户*</text>
            <picker :range="customerLabels" @change="onCustomerPick">
              <view class="input picker">{{ customerLabels[customerIndex] || '请选择' }}</view>
            </picker>
          </view>
          <view v-if="form.party_type === 'supplier'" class="field">
            <text class="label">供应商*</text>
            <picker :range="supplierLabels" @change="onSupplierPick">
              <view class="input picker">{{ supplierLabels[supplierIndex] || '请选择' }}</view>
            </picker>
          </view>
          <view class="field"><text class="label">金额*</text><input v-model="form.amount" class="input" type="digit" placeholder=">0" /></view>
          <view class="field"><text class="label">业务日期*</text><input v-model="form.biz_date" class="input" placeholder="YYYY-MM-DD" /></view>
          <view class="field"><text class="label">备注</text><input v-model="form.remark" class="input" /></view>
        </scroll-view>
        <view class="foot"><button class="btn primary" :loading="saving" @tap="submit">保存</button></view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { financeAdminApi, type LedgerRow } from '@/api/admin/finance'
import { usePermission } from '@/composables/usePermission'

const directions = [
  { value: 'in', label: '收入' },
  { value: 'out', label: '支出' },
]
const categories = [
  { value: 'receipt', label: '收款 receipt' },
  { value: 'payment', label: '付款 payment' },
  { value: 'ar', label: '应收 ar' },
  { value: 'ap', label: '应付 ap' },
  { value: 'adjust', label: '调整 adjust' },
]
const partyTypes = [
  { value: 'customer', label: '客户' },
  { value: 'supplier', label: '供应商' },
  { value: 'other', label: '其他' },
]

const { requirePermission } = usePermission()
const items = ref<LedgerRow[]>([])
const customers = ref<{ id: number; name: string; code?: string }[]>([])
const suppliers = ref<{ id: number; name: string; code?: string }[]>([])
const loading = ref(false)
const saving = ref(false)
const month = ref('')
const formVisible = ref(false)
const directionIndex = ref(0)
const categoryIndex = ref(0)
const partyTypeIndex = ref(0)
const customerIndex = ref(0)
const supplierIndex = ref(0)
const form = reactive({ party_type: 'customer', amount: '', biz_date: '', remark: '' })

const directionLabels = directions.map((x) => x.label)
const categoryLabels = categories.map((x) => x.label)
const partyTypeLabels = partyTypes.map((x) => x.label)
const customerLabels = computed(() => customers.value.map((c) => `${c.name}(${c.code || c.id})`))
const supplierLabels = computed(() => suppliers.value.map((s) => `${s.name}(${s.code || s.id})`))

onShow(async () => {
  if (!requirePermission('finance.manage')) return
  const d = new Date()
  month.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  form.biz_date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const [c, s] = await Promise.all([financeAdminApi.listCustomers(), financeAdminApi.listSuppliers()])
  customers.value = c.items || []
  suppliers.value = s.items || []
  await reload()
})

function fmt(v?: number) {
  return Number(v || 0).toFixed(2)
}
function monthRange(m: string) {
  const [y, mo] = m.split('-').map(Number)
  if (!y || !mo) return null
  const last = new Date(y, mo, 0).getDate()
  return { from: `${y}-${String(mo).padStart(2, '0')}-01`, to: `${y}-${String(mo).padStart(2, '0')}-${String(last).padStart(2, '0')}` }
}
function partyLabel(row: LedgerRow) {
  if (row.party_type === 'customer') {
    const c = customers.value.find((x) => x.id === row.party_id)
    return c ? c.name : `客户#${row.party_id}`
  }
  if (row.party_type === 'supplier') {
    const s = suppliers.value.find((x) => x.id === row.party_id)
    return s ? s.name : `供应商#${row.party_id}`
  }
  return row.party_type
}

async function reload() {
  loading.value = true
  try {
    const range = monthRange(month.value.trim())
    const r = await financeAdminApi.listLedgers({
      limit: 50,
      biz_date_from: range?.from,
      biz_date_to: range?.to,
    })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onDirectionPick(e: { detail: { value: number } }) { directionIndex.value = Number(e.detail.value) }
function onCategoryPick(e: { detail: { value: number } }) { categoryIndex.value = Number(e.detail.value) }
function onPartyTypePick(e: { detail: { value: number } }) {
  partyTypeIndex.value = Number(e.detail.value)
  form.party_type = partyTypes[partyTypeIndex.value]?.value || 'customer'
}
function onCustomerPick(e: { detail: { value: number } }) { customerIndex.value = Number(e.detail.value) }
function onSupplierPick(e: { detail: { value: number } }) { supplierIndex.value = Number(e.detail.value) }

function openCreate() {
  directionIndex.value = 0
  categoryIndex.value = 0
  partyTypeIndex.value = 0
  form.party_type = 'customer'
  form.amount = ''
  form.remark = ''
  formVisible.value = true
}

async function submit() {
  const amount = Number(form.amount)
  if (!(amount > 0)) {
    uni.showToast({ title: '金额须大于0', icon: 'none' })
    return
  }
  if (!form.biz_date.trim()) {
    uni.showToast({ title: '请填写业务日期', icon: 'none' })
    return
  }
  let party_id: number | null = null
  if (form.party_type === 'customer') {
    party_id = customers.value[customerIndex.value]?.id ?? null
    if (!party_id) {
      uni.showToast({ title: '请选择客户', icon: 'none' })
      return
    }
  } else if (form.party_type === 'supplier') {
    party_id = suppliers.value[supplierIndex.value]?.id ?? null
    if (!party_id) {
      uni.showToast({ title: '请选择供应商', icon: 'none' })
      return
    }
  }
  saving.value = true
  try {
    await financeAdminApi.createLedger({
      direction: directions[directionIndex.value].value,
      category: categories[categoryIndex.value].value,
      party_type: form.party_type,
      party_id,
      amount,
      biz_date: form.biz_date.trim(),
      remark: form.remark.trim() || null,
    })
    uni.showToast({ title: '已保存', icon: 'success' })
    formVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.add-btn { background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff; border-radius: 999rpx; }
.row-head { display: flex; justify-content: space-between; align-items: center; }
.tag { font-size: 22rpx; padding: 4rpx 12rpx; border-radius: 999rpx; }
.tag.in { background: #dcfce7; color: #15803d; }
.tag.out { background: #fee2e2; color: #b91c1c; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 58vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.picker { color: #334155; }
.foot { padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { border-radius: 12rpx; font-size: 28rpx; }
.primary { background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff; }
</style>
