<template>
  <view class="cust-page">
    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <template v-else-if="data">
      <view class="cust-card cust-card--brand stmt-hero">
        <view class="hero-head">
          <text class="hero-code mono">{{ data.code }}</text>
          <text class="cust-tag" :class="data.status === 'confirmed' ? 'ok' : 'warn'">{{ statementStatusLabel(data.status) }}</text>
        </view>
        <view class="hero-amount">
          <text class="amount-label">{{ t('customer.statementDetail.totalAmount') }}</text>
          <text class="amount-value">¥{{ data.total_amount }}</text>
        </view>
        <view class="hero-period">{{ periodLabel() }}</view>
      </view>

      <view v-if="data.remark" class="cust-card">
        <text class="cust-section-title">{{ t('customer.statementDetail.remark') }}</text>
        <text class="remark-text">{{ data.remark }}</text>
      </view>

      <view class="cust-card">
        <text class="cust-section-title">{{ t('customer.statementDetail.detail') }}</text>
        <view v-for="(it, idx) in data.items" :key="idx" class="cust-row">
          <text>{{ it.order_code || it.order_id }}</text>
          <text class="amt">¥{{ it.amount }}</text>
        </view>
      </view>

      <view class="actions">
        <button v-if="canAck" class="cust-btn-primary" :loading="acting" @tap="onAck">{{ t('customer.statementDetail.confirmAck') }}</button>
        <button v-if="canPaid" class="cust-btn-primary" :loading="acting" @tap="onPaid">{{ t('customer.statementDetail.markPaid') }}</button>
        <button class="cust-btn-outline" :loading="downloading" @tap="onDownload">{{ t('customer.statementDetail.downloadCsv') }}</button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import { ackMyStatement, buildStatementDownloadUrl, getMyStatementDetail, markMyStatementPaid, type CustomerStatementDetail } from '@/api/h5/customer'
import { getToken } from '@/api/request'
import { useCustomerLabels } from '@/composables/useCustomerLabels'
import { useCustomerLocale } from '@/composables/useCustomerLocale'
import { usePermission } from '@/composables/usePermission'

const { t } = useI18n()
const { statementStatusLabel } = useCustomerLabels()
const { setNavTitle } = useCustomerLocale()
const { requireCustomer } = usePermission()

const statementId = ref(0)
const loading = ref(false)
const acting = ref(false)
const downloading = ref(false)
const data = ref<CustomerStatementDetail | null>(null)

const canAck = computed(() => data.value?.status === 'draft')
const canPaid = computed(() => data.value?.status === 'confirmed')

function periodLabel() {
  const s = data.value?.period_start || '—'
  const e = data.value?.period_end || '—'
  return `${s} ~ ${e}`
}

async function load() {
  if (!statementId.value) return
  loading.value = true
  try { data.value = await getMyStatementDetail(statementId.value) } finally { loading.value = false }
}

async function onAck() {
  uni.showModal({
    title: t('customer.statementDetail.confirmAck'),
    content: t('customer.statementDetail.confirmAckMessage'),
    success: async (r) => {
      if (!r.confirm) return
      acting.value = true
      try {
        await ackMyStatement(statementId.value)
        uni.showToast({ title: t('customer.statementDetail.ackSuccess'), icon: 'success' })
        load()
      } finally { acting.value = false }
    },
  })
}

async function onPaid() {
  uni.showModal({
    title: t('customer.statementDetail.markPaid'),
    content: t('customer.statementDetail.confirmMarkPaid'),
    success: async (r) => {
      if (!r.confirm) return
      acting.value = true
      try {
        await markMyStatementPaid(statementId.value)
        uni.showToast({ title: t('customer.statementDetail.markPaidSuccess'), icon: 'success' })
        load()
      } finally { acting.value = false }
    },
  })
}

function onDownload() {
  downloading.value = true
  const url = buildStatementDownloadUrl(statementId.value)
  const token = getToken()
  uni.downloadFile({
    url,
    header: token ? { Authorization: `Bearer ${token}`, token } : {},
    success: (res) => {
      if (res.statusCode === 200 && res.tempFilePath) {
        uni.openDocument({
          filePath: res.tempFilePath,
          showMenu: true,
          fail: () => uni.showToast({ title: t('customer.statementDetail.downloadFailed'), icon: 'none' }),
        })
      } else {
        uni.showToast({ title: t('customer.statementDetail.downloadFailed'), icon: 'none' })
      }
    },
    fail: () => uni.showToast({ title: t('customer.statementDetail.downloadFailed'), icon: 'none' }),
    complete: () => { downloading.value = false },
  })
}

onLoad((q) => { statementId.value = Number(q?.id || 0) })
onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.statementDetail.title')
  load()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.stmt-hero { padding: 28rpx; border-radius: 24rpx; }
.hero-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20rpx; }
.hero-code { font-family: monospace; font-size: 28rpx; font-weight: 700; color: #fff; }
.hero-amount { text-align: center; margin: 16rpx 0; }
.amount-label { display: block; font-size: 22rpx; color: rgba(255,255,255,0.72); margin-bottom: 4rpx; }
.amount-value { font-size: 56rpx; font-weight: 700; color: #fff; letter-spacing: -1rpx; }
.hero-period { text-align: center; font-size: 22rpx; color: rgba(255,255,255,0.72); }

.remark-text { font-size: 26rpx; color: #64748b; line-height: 1.6; }
.amt { color: #0284c7; font-weight: 600; }

.actions { padding: 24rpx; display: flex; flex-direction: column; gap: 16rpx; }
.cust-btn-outline {
  background: #fff;
  color: #0284c7;
  border: 1rpx solid #bae6fd;
  border-radius: 16rpx;
  height: 76rpx;
  line-height: 76rpx;
  font-size: 28rpx;
  font-weight: 500;
  &::after { border: none; }
  &:active { background: #f0f9ff; }
}
</style>
