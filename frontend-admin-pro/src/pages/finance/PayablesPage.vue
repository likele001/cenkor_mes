<template>
  <AdminPage :title="t('finance.payables.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-button @click="reload()">{{ t('finance.payables.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-card shadow="never" class="mb-4">
        <div class="grid grid-cols-3 gap-4">
          <div class="admin-stat">
            <div class="admin-stat__label">{{ t('finance.payables.totalPayable') }}</div>
            <div class="admin-stat__value text-el-primary">{{ formatMoney(summary.total_payable) }}</div>
          </div>
          <div class="admin-stat">
            <div class="admin-stat__label">{{ t('finance.payables.paidAmount') }}</div>
            <div class="admin-stat__value" style="color: var(--el-color-success)">{{ formatMoney(summary.paid_amount) }}</div>
          </div>
          <div class="admin-stat">
            <div class="admin-stat__label">{{ t('finance.payables.unpaidAmount') }}</div>
            <div class="admin-stat__value" style="color: var(--el-color-danger)">{{ formatMoney(summary.unpaid_amount) }}</div>
          </div>
        </div>
      </el-card>

      <el-table :data="items" border>
        <el-table-column prop="supplier_code" :label="t('finance.payables.supplierCode')" width="160" />
        <el-table-column prop="supplier_name" :label="t('finance.payables.supplierName')" min-width="200" />
        <el-table-column :label="t('finance.payables.totalPayable')" width="160" align="right">
          <template #default="{ row }">
            <span>{{ formatMoney(row.total_payable) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('finance.payables.paidAmount')" width="160" align="right">
          <template #default="{ row }">
            <span style="color: var(--el-color-success)">{{ formatMoney(row.paid_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('finance.payables.unpaidAmount')" width="160" align="right">
          <template #default="{ row }">
            <span style="color: var(--el-color-danger)">{{ formatMoney(row.unpaid_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('finance.payables.actions')" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="router.push(`/finance/supplier-statements?supplier_id=${row.supplier_id}`)">
              {{ t('finance.payables.viewStatements') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" :description="t('finance.payables.noData')" class="mt-8" />
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { financeApi, type PayableOut } from '@/api/finance'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const items = ref<PayableOut[]>([])

const summary = computed(() => {
  return items.value.reduce(
    (acc, x) => {
      acc.total_payable += x.total_payable
      acc.paid_amount += x.paid_amount
      acc.unpaid_amount += x.unpaid_amount
      return acc
    },
    { total_payable: 0, paid_amount: 0, unpaid_amount: 0 },
  )
})

function formatMoney(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return Number(v).toFixed(2)
}

async function reload() {
  loading.value = true
  try {
    const res = await financeApi.getSupplierPayables()
    items.value = res.items
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>
