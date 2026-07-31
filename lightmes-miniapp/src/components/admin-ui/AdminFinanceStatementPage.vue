<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="对账单号" @confirm="reload" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新建</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无客户对账单" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.code }}</text>
          <text class="adm-list-badge tone-active">{{ statusLabel(String(item.status)) }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '客户', value: customerName(item.customer_id) },
          { label: '金额', value: `¥${fmt(item.total_amount)}` },
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
        <view class="head"><text class="title">新建客户对账</text></view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">客户*</text>
            <picker :range="customerLabels" @change="onCustomerPick">
              <view class="input picker">{{ customerLabels[customerIndex] || '请选择' }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="label">订单ID*</text>
            <input v-model="form.order_ids" class="input" placeholder="多个用逗号分隔，如 1,2,3" />
          </view>
          <view class="field"><text class="label">期间起</text><input v-model="form.period_start" class="input" placeholder="YYYY-MM-DD" /></view>
          <view class="field"><text class="label">期间止</text><input v-model="form.period_end" class="input" placeholder="YYYY-MM-DD" /></view>
          <view class="field"><text class="label">备注</text><textarea v-model="form.remark" class="input area" /></view>
        </scroll-view>
        <view class="foot"><button class="btn primary" :loading="saving" @tap="submitCreate">创建</button></view>
      </view>
    </view>

    <view v-if="detailVisible" class="mask" @tap="detailVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">{{ detail?.code }}</text></view>
        <scroll-view scroll-y class="body">
          <view class="kv"><text class="k">客户</text><text class="v">{{ detail?.customer?.name || customerName(detail?.customer_id) }}</text></view>
          <view class="kv"><text class="k">金额</text><text class="v">¥{{ fmt(detail?.total_amount) }}</text></view>
          <view class="kv"><text class="k">状态</text><text class="v">{{ statusLabel(String(detail?.status)) }}</text></view>
          <view class="section-title">订单明细</view>
          <view v-for="(it, idx) in detail?.items || []" :key="idx" class="line-info">
            <text>{{ it.order_code || `#${it.order_id}` }} · ¥{{ fmt(it.amount) }}</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button v-if="detail?.status === 'draft'" class="btn warn" @tap="confirmStmt">确认</button>
          <button v-if="detail?.status === 'confirmed'" class="btn primary" @tap="markPaid">标记已收款</button>
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
import { financeAdminApi, type CustomerStatement } from '@/api/admin/finance'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<CustomerStatement[]>([])
const customers = ref<{ id: number; name: string; code?: string }[]>([])
const loading = ref(false)
const keyword = ref('')
const createVisible = ref(false)
const detailVisible = ref(false)
const saving = ref(false)
const detail = ref<CustomerStatement | null>(null)
const customerIndex = ref(0)
const form = reactive({ order_ids: '', period_start: '', period_end: '', remark: '' })

const customerLabels = computed(() => customers.value.map((c) => `${c.name}(${c.code || c.id})`))
const customerMap = computed(() => new Map(customers.value.map((c) => [c.id, c])))

onShow(async () => {
  if (!requirePermission('finance.manage')) return
  const r = await financeAdminApi.listCustomers()
  customers.value = r.items || []
  await reload()
})

function fmt(v?: number | null) {
  if (v == null || Number.isNaN(v)) return '0.00'
  return Number(v).toFixed(2)
}
function statusLabel(s: string) {
  return ({ draft: '草稿', confirmed: '已确认', paid: '已收款' } as Record<string, string>)[s] || s
}
function customerName(id?: number) {
  if (!id) return '—'
  const c = customerMap.value.get(id)
  return c ? `${c.name}(${c.code || c.id})` : `#${id}`
}

async function reload() {
  loading.value = true
  try {
    const r = await financeAdminApi.listStatements({ limit: 50 })
    let list = r.items || []
    const kw = keyword.value.trim().toLowerCase()
    if (kw) list = list.filter((x) => x.code.toLowerCase().includes(kw))
    items.value = list
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onCustomerPick(e: { detail: { value: number } }) { customerIndex.value = Number(e.detail.value) }
function openCreate() {
  form.order_ids = ''
  form.period_start = ''
  form.period_end = ''
  form.remark = ''
  customerIndex.value = 0
  createVisible.value = true
}

async function submitCreate() {
  const c = customers.value[customerIndex.value]
  if (!c) {
    uni.showToast({ title: '请选择客户', icon: 'none' })
    return
  }
  if (!form.order_ids.trim()) {
    uni.showToast({ title: '请填写订单ID', icon: 'none' })
    return
  }
  saving.value = true
  try {
    await financeAdminApi.createStatement({
      customer_id: c.id,
      order_ids: form.order_ids.trim(),
      period_start: form.period_start.trim() || null,
      period_end: form.period_end.trim() || null,
      remark: form.remark.trim() || null,
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

async function openDetail(row: CustomerStatement) {
  try {
    detail.value = await financeAdminApi.getStatement(row.id)
    detailVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

async function confirmStmt() {
  if (!detail.value) return
  await financeAdminApi.confirmStatement(detail.value.id)
  uni.showToast({ title: '已确认', icon: 'success' })
  detailVisible.value = false
  await reload()
}

async function markPaid() {
  if (!detail.value) return
  await financeAdminApi.markStatementPaid(detail.value.id)
  uni.showToast({ title: '已标记收款', icon: 'success' })
  detailVisible.value = false
  await reload()
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.add-btn { background: linear-gradient(135deg, #10b981, #059669); color: #fff; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 80vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 55vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.area { min-height: 100rpx; width: 100%; }
.picker { color: #334155; }
.kv { display: flex; gap: 16rpx; margin-bottom: 12rpx; font-size: 26rpx; }
.k { color: #64748b; width: 120rpx; }
.v { flex: 1; }
.section-title { font-size: 28rpx; font-weight: 600; margin: 16rpx 0 8rpx; }
.line-info { font-size: 26rpx; padding: 12rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.primary { background: linear-gradient(135deg, #10b981, #059669); color: #fff; }
.warn { background: #fbbf24; color: #78350f; }
</style>
