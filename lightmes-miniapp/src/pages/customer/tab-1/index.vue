<template>
  <view class="cust-page">
    <view class="filter-bar">
      <text
        v-for="s in statusFilters"
        :key="s.value"
        class="filter-tag"
        :class="{ on: statusFilter === s.value }"
        @tap="statusFilter = s.value; reload()"
      >{{ s.label }}</text>
    </view>

    <!-- 汇总统计 -->
    <view v-if="!loading && items.length" class="cust-card summary-card">
      <view class="summary-grid">
        <view class="summary-item">
          <text class="summary-val">{{ items.length }}</text>
          <text class="summary-lbl">对账单数</text>
        </view>
        <view class="summary-item">
          <text class="summary-val amount">¥{{ totalAmount }}</text>
          <text class="summary-lbl">总金额</text>
        </view>
        <view class="summary-item">
          <text class="summary-val warn">{{ pendingCount }}</text>
          <text class="summary-lbl">待确认</text>
        </view>
      </view>
    </view>

    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <view v-else-if="!items.length" class="cust-empty">{{ t('customer.statements.noData') }}</view>
    <view v-for="item in items" :key="item.id" class="cust-card list-card" @tap="goDetail(item.id)">
      <view class="cust-list-head">
        <text class="cust-title mono">{{ item.code }}</text>
        <text class="cust-tag" :class="tagTone(item.status)">{{ statementStatusLabel(item.status) }}</text>
      </view>
        <view class="cust-kv-grid">
          <view class="cust-kv-row">
            <text class="cust-kv-k">{{ t('customer.statementDetail.period') }}</text>
            <text class="cust-kv-v">{{ periodLabel(item) }}</text>
          </view>
          <view class="cust-kv-row">
            <text class="cust-kv-k">{{ t('customer.statementDetail.totalAmount') }}</text>
            <text class="cust-kv-v amount">¥{{ item.total_amount }}</text>
          </view>
          <view class="cust-kv-row">
            <text class="cust-kv-k">创建时间</text>
            <text class="cust-kv-v">{{ fmtTime(item.created_at) }}</text>
          </view>
          <view v-if="item.remark" class="cust-kv-row">
            <text class="cust-kv-k">备注</text>
            <text class="cust-kv-v sub">{{ item.remark }}</text>
          </view>
        </view>
    </view>

    <CustTabBar :active="1" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import { listMyStatements, type CustomerStatementListItem } from '@/api/h5/customer'
import CustTabBar from '@/components/customer-ui/CustTabBar.vue'
import { useCustomerLabels } from '@/composables/useCustomerLabels'
import { useCustomerLocale } from '@/composables/useCustomerLocale'
import { usePermission } from '@/composables/usePermission'

const { t } = useI18n()
const { statementStatusLabel } = useCustomerLabels()
const { setNavTitle } = useCustomerLocale()
const { requireCustomer } = usePermission()

const loading = ref(false)
const items = ref<CustomerStatementListItem[]>([])
const statusFilter = ref('')

const totalAmount = computed(() => items.value.reduce((s, i) => s + Number(i.total_amount || 0), 0).toFixed(2))
const pendingCount = computed(() => items.value.filter((i) => i.status === 'draft').length)

const statusFilters = computed(() => [
  { value: '', label: t('customer.statements.allStatus') },
  { value: 'draft', label: t('customer.statements.draft') },
  { value: 'confirmed', label: t('customer.statements.confirmed') },
  { value: 'paid', label: t('customer.statements.paid') },
])

function periodLabel(item: CustomerStatementListItem) {
  const s = item.period_start || '—'
  const e = item.period_end || '—'
  return `${s} ~ ${e}`
}

function fmtTime(v: string) {
  return v ? v.slice(0, 16).replace('T', ' ') : '—'
}

function tagTone(s: string) {
  if (s === 'paid') return 'tone-paid'
  if (s === 'confirmed') return 'tone-confirmed'
  if (s === 'draft') return 'tone-draft'
  return ''
}

async function reload() {
  loading.value = true
  try {
    const res = await listMyStatements(statusFilter.value ? { status: statusFilter.value } : undefined)
    items.value = res?.items ?? []
  } finally {
    loading.value = false
  }
}

function goDetail(id: number) {
  uni.navigateTo({ url: `/pages-customer/statements/detail/index?id=${id}` })
}

onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.statements.title')
  reload()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  padding: 24rpx;
}
.filter-tag {
  padding: 8rpx 20rpx;
  background: #fff;
  border-radius: 999rpx;
  font-size: 24rpx;
  color: #64748b;
}
.filter-tag.on {
  background: #0ea5e9;
  color: #fff;
}
.mono {
  font-family: monospace;
}
.amount {
  font-size: 30rpx;
  font-weight: 700;
  color: #0369a1;
}
.summary-card {
  padding: 20rpx 24rpx;
}
.summary-grid {
  display: flex;
  gap: 16rpx;
}
.summary-item {
  flex: 1;
  text-align: center;
  background: #f0f9ff;
  border-radius: 12rpx;
  padding: 16rpx 8rpx;
}
.summary-val {
  display: block;
  font-size: 32rpx;
  font-weight: 700;
  color: #1e293b;
}
.summary-val.amount {
  color: #0369a1;
  font-size: 28rpx;
}
.summary-val.warn {
  color: #b45309;
}
.summary-lbl {
  display: block;
  font-size: 22rpx;
  color: #64748b;
  margin-top: 4rpx;
}
.tone-paid { background: #dcfce7; color: #15803d; }
.tone-confirmed { background: #dbeafe; color: #2563eb; }
.tone-draft { background: #fef3c7; color: #b45309; }
.sub {
  font-size: 22rpx;
  color: #94a3b8;
}
</style>
