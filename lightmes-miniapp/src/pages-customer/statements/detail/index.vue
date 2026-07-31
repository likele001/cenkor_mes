<template>
  <view class="cust-page">
    <view v-if="loading" class="cust-empty">{{ t('common.loading') }}</view>
    <template v-else-if="data">
      <view class="cust-card">
        <text class="mono cust-title">{{ data.code }}</text>
        <view class="kv"><text class="k">{{ t('customer.statementDetail.period') }}</text><text class="v">{{ periodLabel() }}</text></view>
        <view class="kv"><text class="k">{{ t('customer.statementDetail.status') }}</text><text class="v">{{ statementStatusLabel(data.status) }}</text></view>
        <view class="kv"><text class="k">{{ t('customer.statementDetail.totalAmount') }}</text><text class="v">¥{{ data.total_amount }}</text></view>
        <view v-if="data.remark" class="kv"><text class="k">{{ t('customer.statementDetail.remark') }}</text><text class="v">{{ data.remark }}</text></view>
      </view>

      <view class="cust-card">
        <text class="section">{{ t('customer.statementDetail.detail') }}</text>
        <view v-for="(it, idx) in data.items" :key="idx" class="line">
          <text>{{ it.order_code || it.order_id }} · ¥{{ it.amount }}</text>
        </view>
      </view>

      <view class="actions">
        <button v-if="canAck" class="cust-btn-primary" :loading="acting" @tap="onAck">{{ t('customer.statementDetail.confirmAck') }}</button>
        <button v-if="canPaid" class="cust-btn-primary" :loading="acting" @tap="onPaid">{{ t('customer.statementDetail.markPaid') }}</button>
        <button class="btn-plain" :loading="downloading" @tap="onDownload">{{ t('customer.statementDetail.downloadCsv') }}</button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import {
  ackMyStatement,
  buildStatementDownloadUrl,
  getMyStatementDetail,
  markMyStatementPaid,
  type CustomerStatementDetail,
} from '@/api/h5/customer'
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
  try {
    data.value = await getMyStatementDetail(statementId.value)
  } finally {
    loading.value = false
  }
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
      } finally {
        acting.value = false
      }
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
      } finally {
        acting.value = false
      }
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
    complete: () => {
      downloading.value = false
    },
  })
}

onLoad((q) => {
  statementId.value = Number(q?.id || 0)
})

onShow(() => {
  if (!requireCustomer()) return
  setNavTitle('customer.statementDetail.title')
  load()
})
</script>

<style scoped lang="scss">
@use '@/styles/customer-theme.scss';
.kv {
  display: flex;
  justify-content: space-between;
  padding: 10rpx 0;
  font-size: 26rpx;
}
.k {
  color: #64748b;
}
.mono {
  font-family: monospace;
  display: block;
  margin-bottom: 12rpx;
}
.section {
  font-weight: 600;
  display: block;
  margin-bottom: 12rpx;
}
.line {
  padding: 10rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
  font-size: 26rpx;
}
.actions {
  padding: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.btn-plain {
  background: #fff;
  color: #0284c7;
  border: 1rpx solid #bae6fd;
  border-radius: 12rpx;
}
</style>
