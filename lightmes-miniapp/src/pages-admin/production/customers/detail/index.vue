<template>
  <view class="adm-page">
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="detail" class="adm-card">
      <!-- 客户头部 -->
      <view class="cust-head">
        <view class="cust-avatar">
          <text class="avatar-text">{{ (detail.name || '?').charAt(0) }}</text>
        </view>
        <view class="cust-info">
          <text class="title">{{ detail.name }}</text>
          <text class="sub">{{ detail.code }}</text>
        </view>
      </view>

      <!-- 统计卡片 -->
      <view class="stat-grid">
        <view class="stat-item">
          <view class="stat-val">{{ stats.orderCount }}</view>
          <view class="stat-lbl">订单数</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ stats.productCount }}</view>
          <view class="stat-lbl">关联产品</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ stats.oppCount }}</view>
          <view class="stat-lbl">销售机会</view>
        </view>
      </view>

      <!-- 联系信息 -->
      <view class="section">联系信息</view>
      <view class="info-list">
        <view class="info-row">
          <text class="info-label">负责人</text>
          <text class="info-val">{{ detail.owner_name || '—' }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">联系人</text>
          <text class="info-val">{{ detail.contact_name || '—' }}</text>
        </view>
        <view v-if="detail.contact_phone" class="info-row">
          <text class="info-label">电话</text>
          <text class="info-val link" @tap="callPhone(detail.contact_phone!)">{{ detail.contact_phone }}</text>
        </view>
        <view v-if="detail.address" class="info-row">
          <text class="info-label">地址</text>
          <text class="info-val" @longpress="copyText(detail.address!)">{{ detail.address }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">登录账号</text>
          <text class="info-val">{{ detail.login_username || '—' }}</text>
        </view>
      </view>
    </view>
    <view v-else class="loading">未找到客户</view>

    <!-- 最近订单 -->
    <view v-if="recentOrders.length" class="adm-card mt">
      <text class="section-title">最近订单 ({{ recentOrders.length }})</text>
      <view v-for="o in recentOrders" :key="o.id" class="order-card" @tap="goOrder(o.id)">
        <view class="order-head">
          <text class="order-code">{{ o.code || `#${o.id}` }}</text>
          <text class="order-status" :class="orderStatusTone(String(o.status))">{{ orderStatusLabel(String(o.status)) }}</text>
        </view>
        <view class="order-info">
          <text class="order-qty">{{ o.total_qty || 0 }} 件</text>
          <text class="order-date">{{ formatDate(o.created_at) }}</text>
        </view>
      </view>
    </view>

    <!-- 销售机会 -->
    <view v-if="opps.length" class="adm-card mt">
      <text class="section-title">销售机会 ({{ opps.length }})</text>
      <view v-for="o in opps" :key="o.id" class="opp-row">
        <view class="opp-head">
          <text class="opp-title">{{ o.title }}</text>
          <text v-if="o.converted_order_id" class="opp-converted">已转订单</text>
        </view>
        <text class="opp-sub">{{ o.code }} · {{ o.stage }} · {{ o.status }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { adminApi } from '@/api/admin/index'
import { apiGet } from '@/api/request'
import { usePermission } from '@/composables/usePermission'
import { adminOrderStatusLabel, adminOrderStatusTone } from '@/utils/adminStatusLabels'

type CustomerDetail = {
  code: string
  name: string
  owner_name?: string | null
  contact_name?: string | null
  contact_phone?: string | null
  address?: string | null
  login_username?: string | null
  product_count?: number
}
type Opp = { id: number; code: string; title: string; stage: string; status: string; converted_order_id?: number | null }
type OrderRow = { id: number; code?: string; status?: string; total_qty?: number; created_at?: string }

const orderStatusLabel = adminOrderStatusLabel
const orderStatusTone = adminOrderStatusTone

const detail = ref<CustomerDetail | null>(null)
const opps = ref<Opp[]>([])
const recentOrders = ref<OrderRow[]>([])
const loading = ref(true)
const customerId = ref(0)
const { hasPermission } = usePermission()

const stats = computed(() => ({
  orderCount: recentOrders.value.length,
  productCount: detail.value?.product_count ?? 0,
  oppCount: opps.value.length,
}))

function formatDate(d?: string) {
  if (!d) return '—'
  return String(d).slice(0, 10)
}

function callPhone(phone: string) {
  uni.makePhoneCall({ phoneNumber: phone })
}
function copyText(text: string) {
  uni.setClipboardData({ data: text, success: () => uni.showToast({ title: '已复制', icon: 'success' }) })
}
function goOrder(id: number) {
  uni.navigateTo({ url: `/pages-admin/production/orders/detail?id=${id}` })
}

onLoad(async (q) => {
  if (!hasPermission('customer.manage') && !hasPermission('crm.sales')) return
  customerId.value = Number(q?.id || 0)
  if (!customerId.value) {
    loading.value = false
    return
  }
  try {
    detail.value = (await adminApi.getCustomer(customerId.value)) as CustomerDetail
    // 并行加载关联数据
    const [oppRes, orderRes] = await Promise.allSettled([
      apiGet<{ items: Opp[] }>(`/admin/production/customers/${customerId.value}/opportunities`, {}, true),
      adminApi.listOrders({ customer_id: customerId.value, limit: 5 }),
    ])
    if (oppRes.status === 'fulfilled') opps.value = oppRes.value.items || []
    if (orderRes.status === 'fulfilled') recentOrders.value = ((orderRes.value.items || []) as OrderRow[]).slice(0, 5)
  } catch {
    detail.value = null
    opps.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
.loading { padding: 40rpx; text-align: center; color: #94a3b8; }

/* 客户头部 */
.cust-head { display: flex; align-items: center; gap: 20rpx; margin-bottom: 24rpx; }
.cust-avatar {
  width: 80rpx; height: 80rpx; border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  display: flex; align-items: center; justify-content: center;
}
.avatar-text { color: #fff; font-size: 32rpx; font-weight: 700; }
.cust-info { flex: 1; }
.title { display: block; font-size: 32rpx; font-weight: 700; }
.sub { display: block; font-size: 24rpx; color: #94a3b8; margin-top: 4rpx; }

/* 统计 */
.stat-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 16rpx; background: #f8fafc; border-radius: 12rpx; padding: 20rpx 12rpx;
}
.stat-item { text-align: center; }
.stat-val { font-size: 36rpx; font-weight: 700; color: #1e293b; }
.stat-lbl { font-size: 22rpx; color: #94a3b8; margin-top: 4rpx; }

/* 联系信息 */
.section { font-weight: 600; margin: 28rpx 0 12rpx; font-size: 28rpx; color: #334155; }
.info-list { background: #f8fafc; border-radius: 12rpx; padding: 8rpx 20rpx; }
.info-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12rpx 0; border-bottom: 1rpx solid #f1f5f9;
}
.info-row:last-child { border-bottom: none; }
.info-label { font-size: 26rpx; color: #94a3b8; flex-shrink: 0; }
.info-val { font-size: 26rpx; color: #334155; text-align: right; }
.info-val.link { color: #2563eb; }

.mt { margin-top: 24rpx; }
.section-title { display: block; font-size: 28rpx; font-weight: 600; margin-bottom: 16rpx; }

/* 最近订单 */
.order-card { padding: 16rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.order-card:last-child { border-bottom: none; }
.order-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6rpx; }
.order-code { font-size: 26rpx; font-weight: 600; }
.order-status {
  font-size: 22rpx; padding: 2rpx 12rpx; border-radius: 999rpx;
}
.order-status.tone-ok { background: #dcfce7; color: #15803d; }
.order-status.tone-active { background: #dbeafe; color: #1d4ed8; }
.order-status.tone-warn { background: #fef9c3; color: #a16207; }
.order-status.tone-danger { background: #fee2e2; color: #b91c1c; }
.order-info { display: flex; justify-content: space-between; font-size: 24rpx; color: #64748b; }

/* 销售机会 */
.opp-row { padding: 16rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.opp-row:last-child { border-bottom: none; }
.opp-head { display: flex; justify-content: space-between; align-items: center; }
.opp-title { font-size: 26rpx; }
.opp-converted { font-size: 20rpx; color: #15803d; background: #dcfce7; padding: 2rpx 10rpx; border-radius: 999rpx; }
.opp-sub { display: block; font-size: 22rpx; color: #94a3b8; margin-top: 6rpx; }
</style>
