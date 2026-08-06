<template>
  <AdminPage :title="t('finance.statementDetail.title')" :description="item?.code || ''">
    <el-card v-loading="loading">
          <template #actions>
      <div class="flex items-center gap-2">
          <el-button @click="router.back()">{{ t('finance.statementDetail.back') }}</el-button>
          <el-button v-if="item" type="primary" @click="onPrint">{{ t('finance.statementDetail.print') }}</el-button>
          <el-button v-if="item" type="warning" @click="onExportPdf">{{ t('finance.statementDetail.exportPdf') }}</el-button>
          <el-button v-if="canConfirm" type="warning" :loading="confirming" @click="onConfirm">{{ t('finance.statementDetail.confirm') }}</el-button>
          <el-button v-if="canMarkPaid" type="success" :loading="paying" @click="onMarkPaid">{{ t('finance.statementDetail.markPaid') }}</el-button>
        </div>
    </template>


      <el-descriptions class="mt-4" :column="3" border v-if="item">
        <el-descriptions-item :label="t('finance.statementDetail.code')">{{ item.code }}</el-descriptions-item>
        <el-descriptions-item :label="t('finance.statementDetail.customer')">{{ item.customer ? partyOptionLabel(item.customer) : item.customer_id }}</el-descriptions-item>
        <el-descriptions-item :label="t('finance.statementDetail.status')">
          <el-tag :type="statusTagType(item.status)">{{ statusLabel(item.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('finance.statementDetail.period')" :span="3">
          <span v-if="item.period_start || item.period_end">{{ item.period_start || '-' }} 至 {{ item.period_end || '-' }}</span>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('finance.statementDetail.amount')">{{ formatMoney(item.total_amount) }}</el-descriptions-item>
        <el-descriptions-item :label="t('finance.statementDetail.remark')">{{ item.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('finance.statementDetail.updatedAt')">{{ item.updated_at }}</el-descriptions-item>
        <el-descriptions-item :label="t('finance.statementDetail.createdAt')" :span="3">{{ item.created_at }}</el-descriptions-item>
      </el-descriptions>

      <div class="mt-4 font-medium">{{ t('finance.statementDetail.detailByOrder') }}</div>
      <el-table class="hidden lg:block mt-2 w-full" :data="item?.items || []" border>
        <el-table-column prop="order_id" :label="t('finance.statementDetail.orderId')" width="120" />
        <el-table-column :label="t('finance.statementDetail.orderCode')" min-width="220">
          <template #default="{ row }">
            <span>{{ row.order_code || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('finance.statementDetail.amount')" width="140" align="right">
          <template #default="{ row }">
            <span>{{ formatMoney(row.amount) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="lg:hidden space-y-3 mt-2">
        <div v-for="(row, idx) in item?.items || []" :key="idx" class="admin-mobile-row">
          <div class="font-medium text-sm">{{ row.order_code || `${t('finance.statementDetail.order')} #${row.order_id}` }}</div>
          <dl class="admin-mobile-kv mt-2">
            <dt>{{ t('finance.statementDetail.amount') }}</dt>
            <dd>{{ formatMoney(row.amount) }}</dd>
          </dl>
        </div>
      </div>
    </el-card>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { financeApi, type CustomerStatementDetailOut } from '@/api/finance'
import { http } from '@/utils/http'
import { openPrintWindow } from '@/utils/print'
import { partyOptionLabel } from '@/utils/display'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const item = ref<CustomerStatementDetailOut | null>(null)
const confirming = ref(false)
const paying = ref(false)

const id = computed(() => Number(route.params.id))

const { label: statusLabel, type: statusTagType } = useStatus('customer_statement')

function formatMoney(v: number | null) {
  if (v === null || Number.isNaN(v)) return '-'
  return Number(v).toFixed(2)
}

const canConfirm = computed(() => item.value?.status === 'draft')
const canMarkPaid = computed(() => item.value?.status === 'confirmed')

async function reload() {
  loading.value = true
  try {
    item.value = await financeApi.getCustomerStatement(id.value)
  } finally {
    loading.value = false
  }
}

async function onConfirm() {
  if (!item.value) return
  confirming.value = true
  try {
    const res = await financeApi.confirmCustomerStatement(item.value.id)
    item.value = { ...item.value, status: res.status }
    ElMessage.success(t('finance.statementDetail.confirmSuccess'))
  } finally {
    confirming.value = false
  }
}

async function onMarkPaid() {
  if (!item.value) return
  paying.value = true
  try {
    const res = await financeApi.markCustomerStatementPaid(item.value.id)
    item.value = { ...item.value, status: res.status, updated_at: res.updated_at }
    ElMessage.success(t('finance.statementDetail.markPaidSuccess'))
  } finally {
    paying.value = false
  }
}

async function onPrint() {
  if (!item.value) return
  const resp = await financeApi.printCustomerStatement(item.value.id, { template_code: 'customer_statement' })
  const html = resp?.html || ''
  if (!html) return
  openPrintWindow(html, { title: `customer_statement_${item.value.id}`, autoPrint: true })
}

async function onExportPdf() {
  if (!item.value) return
  const res = await financeApi.exportCustomerStatementPdf(item.value.id, { template_code: 'customer_statement' })
  const blob = await http.request<Blob>({ url: `/files/${res.attachment_id}`, method: 'GET', params: { download: true }, responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = res.filename || `customer_statement_${item.value.id}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

onMounted(reload)
</script>
