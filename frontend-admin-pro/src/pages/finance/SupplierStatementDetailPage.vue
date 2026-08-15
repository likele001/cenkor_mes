<template>
  <AdminPage :title="t('finance.supplierStatements.detail')">
    <div v-loading="loading" class="space-y-4">
      <!-- 基本信息 -->
      <el-card shadow="never">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="flex items-center gap-3">
              <span class="text-lg font-semibold text-el-primary">{{ data?.code }}</span>
              <el-tag v-if="data" :type="statusTagType(data.status)">{{ statusLabel(data.status) }}</el-tag>
            </div>
            <div class="mt-2 space-y-1 text-sm text-el-placeholder">
              <div>{{ t('finance.supplierStatements.supplier') }}：{{ data?.supplier_name || data?.supplier_id }}</div>
              <div v-if="data?.period_start || data?.period_end">
                {{ t('finance.supplierStatements.period') }}：{{ data?.period_start || '-' }} 至 {{ data?.period_end || '-' }}
              </div>
              <div v-if="data?.remark">{{ t('finance.supplierStatements.remark') }}：{{ data.remark }}</div>
            </div>
          </div>
          <div class="flex gap-2">
            <el-button v-if="data?.status === 'draft'" type="primary" :loading="confirming" @click="doConfirm">
              {{ t('finance.supplierStatements.confirm') }}
            </el-button>
            <el-button v-if="data?.status === 'confirmed'" type="success" :loading="paying" @click="doMarkPaid">
              {{ t('finance.supplierStatements.markPaid') }}
            </el-button>
            <el-button @click="router.back()">{{ t('common.back') }}</el-button>
          </div>
        </div>
      </el-card>

      <!-- 金额汇总 -->
      <el-card shadow="never">
        <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div class="admin-stat">
            <div class="admin-stat__label">{{ t('finance.supplierStatements.totalAmount') }}</div>
            <div class="admin-stat__value text-el-primary">{{ formatMoney(data?.total_amount) }}</div>
          </div>
          <div class="admin-stat">
            <div class="admin-stat__label">{{ t('finance.supplierStatements.status') }}</div>
            <div class="admin-stat__value">
              <el-tag v-if="data" :type="statusTagType(data.status)">{{ statusLabel(data.status) }}</el-tag>
            </div>
          </div>
          <div class="admin-stat">
            <div class="admin-stat__label">{{ t('finance.supplierStatements.orderCount') }}</div>
            <div class="admin-stat__value">{{ data?.items?.length || 0 }}</div>
          </div>
          <div class="admin-stat">
            <div class="admin-stat__label">{{ t('finance.supplierStatements.createdAt') }}</div>
            <div class="admin-stat__value text-sm">{{ data?.created_at || '—' }}</div>
          </div>
        </div>
      </el-card>

      <!-- 明细 -->
      <el-card shadow="never">
        <template #header>
          <span>{{ t('finance.supplierStatements.items') }}</span>
        </template>
        <el-table :data="data?.items || []" border>
          <el-table-column prop="purchase_order_code" :label="t('finance.supplierStatements.orderCode')" min-width="220" />
          <el-table-column prop="purchase_order_id" label="ID" width="90" />
          <el-table-column :label="t('finance.supplierStatements.amount')" width="160" align="right">
            <template #default="{ row }">
              <span>{{ formatMoney(row.amount) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { financeApi, type SupplierStatementDetailOut } from '@/api/finance'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const confirming = ref(false)
const paying = ref(false)
const data = ref<SupplierStatementDetailOut | null>(null)

const { label: statusLabel, type: statusTagType } = useStatus('purchase_statement')

function formatMoney(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return Number(v).toFixed(2)
}

async function reload() {
  loading.value = true
  try {
    const id = Number(route.params.id)
    data.value = await financeApi.getSupplierStatement(id)
  } finally {
    loading.value = false
  }
}

async function doConfirm() {
  if (!data.value) return
  confirming.value = true
  try {
    await financeApi.confirmSupplierStatement(data.value.id)
    ElMessage.success(t('finance.supplierStatements.confirmed'))
    await reload()
  } finally {
    confirming.value = false
  }
}

async function doMarkPaid() {
  if (!data.value) return
  paying.value = true
  try {
    await financeApi.markSupplierStatementPaid(data.value.id)
    ElMessage.success(t('finance.supplierStatements.markedPaid'))
    await reload()
  } finally {
    paying.value = false
  }
}

onMounted(reload)
</script>
