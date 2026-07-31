<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索订单号" @confirm="reload" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新建</button>
    </view>

    <MListLayout :items="items" :loading="loading" empty-text="暂无订单" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.code || item.id }}</text>
          <text class="adm-list-badge" :class="orderStatusTone(String(item.status))">
            {{ orderStatusLabel(String(item.status)) }}
          </text>
        </view>
        <AdminKvGrid :rows="orderKvRows(item)" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button v-if="canConfirm(item)" class="adm-card-btn success" :loading="confirmingId === item.id" @tap="confirmOrderRow(item)">
            通过
          </button>
          <button v-if="canReject(item)" class="adm-card-btn danger" @tap="rejectOrderRow(item)">驳回</button>
          <button v-if="canEdit(item)" class="adm-card-btn edit" @tap="openEdit(item)">编辑</button>
          <button v-if="item.can_delete" class="adm-card-btn danger" @tap="confirmDelete(item)">删除</button>
          <button class="adm-card-btn primary" @tap="goDetail(item)">详情</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="formVisible" class="mask" @tap="formVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">{{ formMode === 'create' ? '新建订单' : '编辑订单' }}</text></view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">客户*</text>
            <picker :range="customerLabels" @change="onCustomerPick">
              <view class="input picker">{{ customerLabels[customerIndex] || '请选择客户' }}</view>
            </picker>
          </view>
          <view class="field"><text class="label">订单号</text><input v-model="form.code" class="input" placeholder="留空自动生成" /></view>
          <view class="field"><text class="label">交期</text><input v-model="form.due_date" class="input" placeholder="YYYY-MM-DD" /></view>
          <view class="field"><text class="label">备注</text><textarea v-model="form.remark" class="input area" /></view>
          <view class="lines-head">
            <text class="label">明细*</text>
            <text class="link" @tap="addLine">+ 添加行</text>
          </view>
          <view v-for="(line, idx) in lines" :key="idx" class="line-card">
            <picker :range="skuLabels" @change="(e) => onSkuPick(idx, e)">
              <view class="input picker">{{ skuLabels[line.skuIndex ?? 0] || '选型号' }}</view>
            </picker>
            <input v-model="line.qty" class="input qty" type="number" placeholder="数量" />
            <text class="del" @tap="removeLine(idx)">删</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button v-if="formMode === 'edit' && canConfirmStatus(currentStatus)" class="btn ghost" :loading="confirmingId === editingId" @tap="confirmOrder">审核通过</button>
          <button v-if="formMode === 'edit' && canRejectStatus(currentStatus)" class="btn ghost" @tap="rejectOrder">驳回</button>
          <button class="btn primary" :loading="saving" @tap="submit">保存</button>
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
import { adminApi } from '@/api/admin/index'
import { apiGet, apiPost, apiPut } from '@/api/request'
import { usePermission } from '@/composables/usePermission'
import { formatAutomationFeedback } from '@/utils/automationFeedback'
import { adminOrderStatusLabel, adminOrderStatusTone } from '@/utils/adminStatusLabels'
import { formatDateTime } from '@/utils/taskDisplay'

const orderStatusLabel = adminOrderStatusLabel
const orderStatusTone = adminOrderStatusTone
const confirmingId = ref<number | null>(null)

const EDITABLE_STATUSES = ['draft', 'confirmed', 'producing']

function canConfirmStatus(status: string) {
  return status === 'draft' || status === 'pending_confirm'
}

function canRejectStatus(status: string) {
  return status === 'pending_confirm'
}

function canConfirm(item: Record<string, unknown>) {
  return canConfirmStatus(String(item.status || ''))
}

function canReject(item: Record<string, unknown>) {
  return canRejectStatus(String(item.status || ''))
}

function canEdit(item: Record<string, unknown>) {
  return EDITABLE_STATUSES.includes(String(item.status || ''))
}

function orderKvRows(item: Record<string, unknown>) {
  const cust = item.customer as { name?: string } | null | undefined
  return [
    { label: '客户名称', value: cust?.name || '—' },
    { label: '订单数量', value: String(item.total_qty ?? 0) },
    { label: '产品型号', value: (item.sku_summary as string) || '—' },
    { label: '交货日期', value: item.due_date ? String(item.due_date).slice(0, 10) : '未设置' },
    { label: '创建时间', value: formatDateTime(String(item.created_at || '')) },
  ]
}

function confirmDelete(row: Record<string, unknown>) {
  const id = Number(row.id)
  if (!id) return
  uni.showModal({
    title: '删除订单',
    content: `确认删除订单 ${row.code || id}？此操作不可恢复。`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        await adminApi.deleteOrder(id)
        uni.showToast({ title: '已删除', icon: 'success' })
        await reload()
      } catch (e: unknown) {
        uni.showToast({ title: (e as Error).message || '删除失败', icon: 'none' })
      }
    },
  })
}

function goDetail(row: Record<string, unknown>) {
  const id = Number(row.id)
  if (!id) return
  uni.navigateTo({ url: `/pages-admin/production/orders/detail/index?id=${id}` })
}

type Line = { skuIndex?: number; sku_id?: number; qty: string; line_no?: number; id?: number }

const { requirePermission } = usePermission()
const items = ref<Record<string, unknown>[]>([])
const loading = ref(false)
const keyword = ref('')
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const editingId = ref<number | null>(null)
const currentStatus = ref('')
const customers = ref<{ id: number; name: string; code?: string }[]>([])
const skus = ref<{ id: number; display_label?: string; name?: string; code?: string }[]>([])
const customerIndex = ref(0)
const form = reactive({ code: '', due_date: '', remark: '' })
const lines = ref<Line[]>([{ qty: '1', skuIndex: 0 }])

const customerLabels = computed(() => customers.value.map((c) => `${c.name}(${c.code || c.id})`))
const skuLabels = computed(() => skus.value.map((s) => s.display_label || s.name || s.code || String(s.id)))

onShow(async () => {
  if (!requirePermission('order.manage')) return
  await loadOptions()
  await reload()
})

async function loadOptions() {
  try {
    const opt = await apiGet<{ customers?: typeof customers.value; skus?: typeof skus.value }>(
      '/admin/production/orders/meta/form-options',
      undefined,
      true,
    )
    customers.value = opt.customers || []
    skus.value = opt.skus || []
  } catch {
    customers.value = []
    skus.value = []
  }
}

async function reload() {
  loading.value = true
  try {
    const r = await adminApi.listOrders({ limit: 50, keyword: keyword.value.trim() || undefined })
    items.value = (r.items || []) as Record<string, unknown>[]
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  currentStatus.value = 'draft'
  form.code = ''
  form.due_date = ''
  form.remark = ''
  customerIndex.value = 0
  lines.value = [{ qty: '1', skuIndex: 0 }]
  formVisible.value = true
}

async function openEdit(row: Record<string, unknown>) {
  formMode.value = 'edit'
  editingId.value = Number(row.id)
  currentStatus.value = String(row.status || '')
  try {
    const d = await adminApi.getOrder(editingId.value)
    form.code = String(d.code || '')
    form.due_date = String(d.due_date || '').slice(0, 10)
    form.remark = String(d.remark || '')
    const cid = Number(d.customer_id)
    customerIndex.value = Math.max(0, customers.value.findIndex((c) => c.id === cid))
    const its = (d.items as Line[]) || []
    lines.value = its.length
      ? its.map((it, i) => ({
          id: it.id,
          line_no: it.line_no || i + 1,
          sku_id: it.sku_id,
          skuIndex: Math.max(0, skus.value.findIndex((s) => s.id === it.sku_id)),
          qty: String(it.qty ?? 1),
        }))
      : [{ qty: '1', skuIndex: 0 }]
    formVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function onCustomerPick(e: { detail: { value: number } }) {
  customerIndex.value = Number(e.detail.value)
}
function onSkuPick(idx: number, e: { detail: { value: number } }) {
  lines.value[idx].skuIndex = Number(e.detail.value)
  lines.value[idx].sku_id = skus.value[lines.value[idx].skuIndex!]?.id
}
function addLine() {
  lines.value.push({ qty: '1', skuIndex: 0 })
}
function removeLine(idx: number) {
  if (lines.value.length <= 1) return
  lines.value.splice(idx, 1)
}

function buildPayload() {
  const customer = customers.value[customerIndex.value]
  if (!customer) throw new Error('请选择客户')
  const mapped = lines.value.map((ln, i) => {
    const sku = skus.value[ln.skuIndex ?? 0]
    if (!sku) throw new Error('请选择型号')
    const qty = Number(ln.qty)
    if (!qty || qty < 1) throw new Error('数量须≥1')
    return {
      id: ln.id,
      line_no: ln.line_no || i + 1,
      sku_id: sku.id,
      qty,
      remark: null,
    }
  })
  return {
    customer_id: customer.id,
    code: form.code.trim() || null,
    due_date: form.due_date.trim() || null,
    remark: form.remark.trim() || null,
    items: mapped,
  }
}

async function submit() {
  saving.value = true
  try {
    const payload = buildPayload()
    if (formMode.value === 'create') {
      await apiPost('/admin/production/orders', payload, true)
      uni.showToast({ title: '创建成功', icon: 'success' })
    } else if (editingId.value) {
      await apiPut(`/admin/production/orders/${editingId.value}`, payload, true)
      uni.showToast({ title: '保存成功', icon: 'success' })
    }
    formVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function doConfirmOrder(id: number) {
  confirmingId.value = id
  try {
    const res = await adminApi.confirmOrder(id)
    const extra = formatAutomationFeedback(res || {})
    uni.showToast({
      title: extra ? `已审核，${extra}` : '已审核通过',
      icon: 'success',
      duration: extra ? 3500 : 1500,
    })
    formVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '审核失败', icon: 'none' })
  } finally {
    confirmingId.value = null
  }
}

function confirmOrderRow(row: Record<string, unknown>) {
  const id = Number(row.id)
  if (!id) return
  uni.showModal({
    title: '审核订单',
    content: `确认审核通过订单 ${row.code || id}？通过后可创建生产计划并排产下发。`,
    success: (res) => {
      if (!res.confirm) return
      void doConfirmOrder(id)
    },
  })
}

async function confirmOrder() {
  if (!editingId.value) return
  await doConfirmOrder(editingId.value)
}

function rejectOrderRow(row: Record<string, unknown>) {
  const id = Number(row.id)
  if (!id) return
  doRejectOrder(id, String(row.code || id))
}

function rejectOrder() {
  if (!editingId.value) return
  doRejectOrder(editingId.value, String(form.code || editingId.value))
}

function doRejectOrder(id: number, label: string) {
  uni.showModal({
    title: '驳回订单',
    content: `订单 ${label}`,
    editable: true,
    placeholderText: '请输入驳回原因',
    success: async (res) => {
      if (!res.confirm) return
      const reason = (res.content || '').trim()
      if (!reason) {
        uni.showToast({ title: '请填写驳回原因', icon: 'none' })
        return
      }
      try {
        await adminApi.rejectOrder(id, reason)
        uni.showToast({ title: '已驳回', icon: 'success' })
        formVisible.value = false
        await reload()
      } catch (e: unknown) {
        uni.showToast({ title: (e as Error).message || '驳回失败', icon: 'none' })
      }
    },
  })
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.add-btn { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 58vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.area { min-height: 120rpx; width: 100%; }
.picker { color: #334155; }
.lines-head { display: flex; justify-content: space-between; align-items: center; margin: 12rpx 0; }
.link { color: #4338ca; font-size: 26rpx; }
.line-card { display: flex; gap: 8rpx; align-items: center; margin-bottom: 12rpx; }
.qty { width: 140rpx; flex-shrink: 0; }
.del { color: #ef4444; font-size: 24rpx; padding: 8rpx; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
</style>
