<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showConfirmDialog, showToast } from 'vant'
import {
  ackMyStatement,
  downloadMyStatementCsv,
  getMyStatementDetail,
  markMyStatementPaid,
  type CustomerStatementDetail,
} from '@/api/customer'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const downloading = ref(false)
const actionLoading = ref(false)
const data = ref<CustomerStatementDetail | null>(null)

const statementId = computed(() => Number(route.params.id))
const canAck = computed(() => data.value?.status === 'draft')
const canMarkPaid = computed(() => data.value?.status === 'confirmed')

function periodLabel() {
  const s = data.value?.period_start || '—'
  const e = data.value?.period_end || '—'
  return `${s} ~ ${e}`
}

async function load() {
  const id = statementId.value
  if (!id) return
  loading.value = true
  try {
    data.value = await getMyStatementDetail(id)
  } finally {
    loading.value = false
  }
}

async function onAck() {
  const id = statementId.value
  if (!id || actionLoading.value) return
  try {
    await showConfirmDialog({ title: t('customer.statementDetail.confirmAck'), message: t('customer.statementDetail.confirmAckMessage') })
  } catch {
    return
  }
  actionLoading.value = true
  try {
    await ackMyStatement(id)
    showToast(t('customer.statementDetail.ackSuccess'))
    await load()
  } finally {
    actionLoading.value = false
  }
}

async function onMarkPaid() {
  const id = statementId.value
  if (!id || actionLoading.value) return
  try {
    await showConfirmDialog({ title: t('customer.statementDetail.markPaid'), message: t('customer.statementDetail.confirmMarkPaid') })
  } catch {
    return
  }
  actionLoading.value = true
  try {
    await markMyStatementPaid(id)
    showToast(t('customer.statementDetail.markPaidSuccess'))
    await load()
  } finally {
    actionLoading.value = false
  }
}

async function onDownload() {
  const id = statementId.value
  if (!id || downloading.value) return
  downloading.value = true
  try {
    const blob = await downloadMyStatementCsv(id)
    const name = `${data.value?.code || 'statement'}.csv`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    showToast(t('customer.statementDetail.downloadFailed'))
  } finally {
    downloading.value = false
  }
}

watch(statementId, load, { immediate: true })
</script>

<template>
  <div>
    <div class="mt-2">
      <van-loading v-if="loading" class="mx-auto" />
    </div>

    <template v-if="data">
      <van-cell-group inset>
        <van-cell :title="t('customer.statementDetail.statementNo')" :value="data.code" />
        <van-cell :title="t('customer.statementDetail.period')" :value="periodLabel()" />
        <van-cell :title="t('customer.statementDetail.status')" :value="data.status || '—'" />
        <van-cell :title="t('customer.statementDetail.totalAmount')" :value="`¥${data.total_amount}`" />
        <van-cell :title="t('customer.statementDetail.remark')" :value="data.remark || '—'" />
      </van-cell-group>

      <div class="mt-4 px-4">
        <van-button block type="primary" :loading="actionLoading" :disabled="!canAck" @click="onAck">{{ t('customer.statementDetail.confirmAck') }}</van-button>
      </div>

      <div class="mt-3 px-4">
        <van-button block type="warning" :loading="actionLoading" :disabled="!canMarkPaid" @click="onMarkPaid">
          {{ t('customer.statementDetail.markPaid') }}
        </van-button>
      </div>

      <div class="mt-4 px-3 text-[14px] font-semibold text-zinc-700">{{ t('customer.statementDetail.detail') }}</div>
      <van-cell-group inset class="mt-2">
        <van-cell v-for="it in data.items" :key="it.order_id" :title="it.order_code || `订单#${it.order_id}`" :value="`¥${it.amount}`" />
      </van-cell-group>

      <div class="mt-6 px-4">
        <van-button block type="primary" :loading="downloading" @click="onDownload">{{ t('customer.statementDetail.downloadCsv') }}</van-button>
      </div>

      <div class="mt-3 px-4">
        <van-button block @click="router.push({ name: 'customerStatements' })">{{ t('customer.statementDetail.returnList') }}</van-button>
      </div>
    </template>
  </div>
</template>
