<template>
  <view class="adm-page">
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="detail" class="adm-card">
      <view class="adm-list-head">
        <text class="title">{{ detail.code }}</text>
        <text class="adm-list-badge" :class="orderStatusTone(String(detail.status))">
          {{ orderStatusLabel(String(detail.status)) }}
        </text>
      </view>
      <AdminKvGrid :rows="detailRows" />

      <!-- 客户联系信息 -->
      <view v-if="detail.customer" class="section">客户信息</view>
      <view v-if="detail.customer" class="contact-card">
        <view class="contact-row">
          <text class="contact-name">{{ detail.customer.name || '—' }}</text>
          <text class="contact-code">{{ detail.customer.code }}</text>
        </view>
        <view v-if="detail.customer.contact_name" class="contact-row small">
          <text class="contact-label">联系人</text>
          <text class="contact-val">{{ detail.customer.contact_name }}</text>
        </view>
        <view v-if="detail.customer.contact_phone" class="contact-row small">
          <text class="contact-label">电话</text>
          <text class="contact-val link" @tap="callPhone(detail.customer.contact_phone!)">{{ detail.customer.contact_phone }}</text>
        </view>
        <view v-if="detail.customer.address" class="contact-row small">
          <text class="contact-label">地址</text>
          <text class="contact-val" @longpress="copyText(detail.customer.address!)">{{ detail.customer.address }}</text>
        </view>
      </view>

      <!-- 订单状态时间线 -->
      <view class="section">订单进度</view>
      <view class="timeline">
        <view v-for="(node, idx) in timelineNodes" :key="idx" class="timeline-item" :class="{ active: node.done, current: node.current }">
          <view class="timeline-dot" />
          <view v-if="idx < timelineNodes.length - 1" class="timeline-line" />
          <view class="timeline-content">
            <text class="timeline-label">{{ node.label }}</text>
            <text v-if="node.time" class="timeline-time">{{ node.time }}</text>
            <text v-else class="timeline-time placeholder">{{ node.current ? '进行中' : '待触发' }}</text>
          </view>
        </view>
      </view>

      <!-- 明细 -->
      <view class="section">订单明细</view>
      <view v-for="(it, idx) in items" :key="idx" class="line">
        <text class="mat">{{ skuLabel(it) }}</text>
        <text class="nums">数量 {{ it.qty }}</text>
      </view>

      <!-- 关联工单 -->
      <view v-if="workOrders.length" class="section">关联工单 ({{ workOrders.length }})</view>
      <view v-for="wo in workOrders" :key="wo.id" class="wo-card" @tap="goWorkOrder(wo.id)">
        <view class="wo-head">
          <text class="wo-code">{{ wo.code || `工单#${wo.id}` }}</text>
          <text class="wo-status" :class="woStatusTone(wo.status)">{{ woStatusLabel(wo.status) }}</text>
        </view>
        <view class="wo-info">
          <text class="wo-sku">{{ wo.sku_label || wo.product_name || '—' }}</text>
          <text class="wo-qty">{{ wo.completed_qty ?? 0 }}/{{ wo.qty }} 件</text>
        </view>
        <view v-if="wo.qty" class="wo-progress">
          <view class="wo-progress-bar" :style="{ width: Math.min(100, Math.round(((wo.completed_qty || 0) / wo.qty) * 100)) + '%' }" />
        </view>
      </view>

      <view v-if="showAuditActions" class="foot-btns">
        <button class="adm-card-btn success" :loading="confirming" @tap="onConfirm">审核通过</button>
        <button v-if="canReject" class="adm-card-btn danger" @tap="onReject">驳回</button>
      </view>
    </view>
    <view v-else class="loading">未找到订单</view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import { adminApi } from '@/api/admin/index'
import { usePermission } from '@/composables/usePermission'
import { formatAutomationFeedback } from '@/utils/automationFeedback'
import { adminOrderStatusLabel, adminOrderStatusTone } from '@/utils/adminStatusLabels'
import { formatDateTime } from '@/utils/taskDisplay'

type OrderItem = { qty: number; sku?: { code?: string; name?: string; display_label?: string; product_name?: string } }
type CustomerInfo = {
  name?: string
  code?: string
  contact_name?: string | null
  contact_phone?: string | null
  address?: string | null
}
type OrderDetail = {
  id?: number
  code: string
  status: string
  due_date?: string | null
  remark?: string | null
  created_at?: string
  confirmed_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  customer?: CustomerInfo | null
  items?: OrderItem[]
}
type WorkOrderRow = {
  id: number
  code?: string
  status?: string
  qty?: number
  completed_qty?: number
  sku_label?: string
  product_name?: string
}

const orderStatusLabel = adminOrderStatusLabel
const orderStatusTone = adminOrderStatusTone

const detail = ref<OrderDetail | null>(null)
const workOrders = ref<WorkOrderRow[]>([])
const loading = ref(true)
const confirming = ref(false)
const orderId = ref(0)
const { requirePermission } = usePermission()

const items = computed(() => detail.value?.items || [])
const canConfirm = computed(() => {
  const s = String(detail.value?.status || '')
  return s === 'draft' || s === 'pending_confirm'
})
const canReject = computed(() => String(detail.value?.status || '') === 'pending_confirm')
const showAuditActions = computed(() => canConfirm.value || canReject.value)

const detailRows = computed(() => {
  const d = detail.value
  const cust = d?.customer
  const totalQty = (d?.items || []).reduce((sum, it) => sum + Number(it.qty || 0), 0)
  return [
    { label: '客户', value: cust ? `${cust.name || ''}(${cust.code || ''})` : '—' },
    { label: '订单数量', value: String(totalQty) },
    { label: '交期', value: d?.due_date ? String(d.due_date).slice(0, 10) : '未设置' },
    { label: '备注', value: d?.remark || '—' },
    { label: '创建时间', value: formatDateTime(String(d?.created_at || '')) },
  ]
})

const STATUS_FLOW = [
  { key: 'draft', label: '草稿' },
  { key: 'pending_confirm', label: '待确认' },
  { key: 'confirmed', label: '已确认' },
  { key: 'in_production', label: '生产中' },
  { key: 'completed', label: '已完成' },
]

const timelineNodes = computed(() => {
  const d = detail.value
  if (!d) return []
  const currentStatus = String(d.status)
  const timeMap: Record<string, string | null | undefined> = {
    draft: d.created_at,
    pending_confirm: d.created_at,
    confirmed: d.confirmed_at,
    in_production: d.started_at,
    completed: d.completed_at,
  }
  const currentIdx = STATUS_FLOW.findIndex((s) => s.key === currentStatus)
  return STATUS_FLOW.map((s, idx) => ({
    label: s.label,
    done: idx <= currentIdx,
    current: idx === currentIdx,
    time: timeMap[s.key] ? formatDateTime(String(timeMap[s.key])) : '',
  }))
})

function woStatusLabel(s?: string) {
  const map: Record<string, string> = { pending: '待开始', working: '进行中', done: '已完成', paused: '已暂停' }
  return map[s || ''] || s || '—'
}
function woStatusTone(s?: string) {
  const map: Record<string, string> = { done: 'tone-ok', working: 'tone-active', pending: 'tone-warn', paused: 'tone-danger' }
  return map[s || ''] || ''
}

function skuLabel(it: OrderItem) {
  const s = it.sku
  return s?.display_label || `${s?.product_name || ''} ${s?.name || s?.code || ''}`.trim() || '型号'
}

function callPhone(phone: string) {
  uni.makePhoneCall({ phoneNumber: phone })
}
function copyText(text: string) {
  uni.setClipboardData({ data: text, success: () => uni.showToast({ title: '已复制', icon: 'success' }) })
}
function goWorkOrder(woId: number) {
  uni.navigateTo({ url: `/pages-admin/production/work-orders/detail?id=${woId}` })
}

async function loadDetail() {
  if (!orderId.value) return
  loading.value = true
  try {
    detail.value = (await adminApi.getOrder(orderId.value)) as OrderDetail
    // 加载关联工单
    try {
      const r = await adminApi.listWorkOrders({ order_id: orderId.value, limit: 20 })
      workOrders.value = ((r.items || []) as WorkOrderRow[]).slice(0, 10)
    } catch {
      workOrders.value = []
    }
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function onConfirm() {
  if (!orderId.value) return
  uni.showModal({
    title: '审核订单',
    content: '确认审核通过该订单？通过后可创建生产计划并排产下发。',
    success: async (res) => {
      if (!res.confirm) return
      confirming.value = true
      try {
        const r = await adminApi.confirmOrder(orderId.value)
        const extra = formatAutomationFeedback(r || {})
        uni.showToast({ title: extra ? `已审核，${extra}` : '已审核通过', icon: 'success', duration: extra ? 3500 : 1500 })
        await loadDetail()
      } catch (e: unknown) {
        uni.showToast({ title: (e as Error).message || '审核失败', icon: 'none' })
      } finally {
        confirming.value = false
      }
    },
  })
}

function onReject() {
  if (!orderId.value) return
  uni.showModal({
    title: '驳回订单',
    content: `订单 ${detail.value?.code || orderId.value}`,
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
        await adminApi.rejectOrder(orderId.value, reason)
        uni.showToast({ title: '已驳回', icon: 'success' })
        await loadDetail()
      } catch (e: unknown) {
        uni.showToast({ title: (e as Error).message || '驳回失败', icon: 'none' })
      }
    },
  })
}

onLoad(async (q) => {
  requirePermission('order.manage')
  orderId.value = Number(q?.id || 0)
  if (!orderId.value) {
    loading.value = false
    return
  }
  await loadDetail()
})
</script>

<style scoped lang="scss">
.loading { padding: 40rpx; text-align: center; color: #94a3b8; }
.title { font-size: 32rpx; font-weight: 700; }
.section { font-weight: 600; margin: 28rpx 0 12rpx; font-size: 28rpx; color: #334155; }

/* 客户联系卡片 */
.contact-card { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; margin-top: 8rpx; }
.contact-row { display: flex; justify-content: space-between; align-items: center; padding: 6rpx 0; }
.contact-name { font-size: 28rpx; font-weight: 600; }
.contact-code { font-size: 22rpx; color: #94a3b8; }
.contact-row.small { padding: 4rpx 0; }
.contact-label { font-size: 24rpx; color: #94a3b8; flex-shrink: 0; }
.contact-val { font-size: 24rpx; color: #334155; text-align: right; }
.contact-val.link { color: #2563eb; }

/* 时间线 */
.timeline { padding: 8rpx 0 8rpx 8rpx; }
.timeline-item { position: relative; padding-left: 36rpx; padding-bottom: 28rpx; }
.timeline-item:last-child { padding-bottom: 0; }
.timeline-dot {
  position: absolute; left: 0; top: 6rpx;
  width: 16rpx; height: 16rpx; border-radius: 50%;
  background: #cbd5e1; border: 3rpx solid #e2e8f0;
}
.timeline-item.active .timeline-dot { background: #2563eb; border-color: #93c5fd; }
.timeline-item.current .timeline-dot { background: #2563eb; border-color: #2563eb; box-shadow: 0 0 0 4rpx rgba(37,99,235,.15); }
.timeline-line {
  position: absolute; left: 7rpx; top: 24rpx; bottom: -4rpx;
  width: 2rpx; background: #e2e8f0;
}
.timeline-item.active .timeline-line { background: #93c5fd; }
.timeline-content { display: flex; justify-content: space-between; align-items: center; }
.timeline-label { font-size: 26rpx; color: #334155; }
.timeline-item.active .timeline-label { font-weight: 600; color: #1e293b; }
.timeline-time { font-size: 22rpx; color: #64748b; }
.timeline-time.placeholder { color: #cbd5e1; font-style: italic; }

/* 明细 */
.line { padding: 12rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.mat { display: block; font-size: 26rpx; }
.nums { font-size: 24rpx; color: #64748b; }

/* 关联工单 */
.wo-card { background: #f8fafc; border-radius: 12rpx; padding: 16rpx 20rpx; margin-bottom: 12rpx; }
.wo-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8rpx; }
.wo-code { font-size: 26rpx; font-weight: 600; }
.wo-status { font-size: 22rpx; padding: 2rpx 12rpx; border-radius: 999rpx; }
.wo-status.tone-ok { background: #dcfce7; color: #15803d; }
.wo-status.tone-active { background: #dbeafe; color: #1d4ed8; }
.wo-status.tone-warn { background: #fef9c3; color: #a16207; }
.wo-status.tone-danger { background: #fee2e2; color: #b91c1c; }
.wo-info { display: flex; justify-content: space-between; font-size: 24rpx; color: #64748b; }
.wo-progress { height: 6rpx; background: #e2e8f0; border-radius: 3rpx; margin-top: 10rpx; overflow: hidden; }
.wo-progress-bar { height: 100%; background: linear-gradient(90deg, #3b82f6, #2563eb); border-radius: 3rpx; transition: width .3s; }

.foot-btns {
  display: flex; gap: 16rpx; margin-top: 28rpx;
  padding-top: 24rpx; border-top: 1rpx solid #f1f5f9;
}
.foot-btns .adm-card-btn { flex: 1; }
</style>
