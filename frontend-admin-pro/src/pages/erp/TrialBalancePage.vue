<template>
  <AdminPage :title="t('erp.reports.trialBalance')">
    <template #actions>
      <div class="flex items-center gap-2">
        <el-date-picker v-model="period" type="month" value-format="YYYY-MM" :placeholder="t('erp.common.period')" @change="reload(true)" />
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table :data="items" border>
        <el-table-column prop="code" :label="t('erp.accounts.code')" width="120" />
        <el-table-column prop="name" :label="t('erp.accounts.name')" min-width="160" />
        <el-table-column prop="opening_balance" :label="t('erp.reports.opening')" width="130" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.opening_balance) }}</template>
        </el-table-column>
        <el-table-column prop="debit_amount" :label="t('erp.vouchers.debit')" width="130" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.debit_amount) }}</template>
        </el-table-column>
        <el-table-column prop="credit_amount" :label="t('erp.vouchers.credit')" width="130" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.credit_amount) }}</template>
        </el-table-column>
        <el-table-column prop="ending_balance" :label="t('erp.reports.ending')" width="130" align="right">
          <template #default="{ row }">
            <span :class="row.ending_balance >= 0 ? 'text-red-500' : 'text-green-600'">¥ {{ formatMoney(row.ending_balance) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" :description="t('erp.common.empty')" />
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { erpApi, type TrialBalanceRow } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const period = ref('')
const items = ref<TrialBalanceRow[]>([])

function formatMoney(v: number | undefined | null) {
  return (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function reload(_silent = false) {
  if (!period.value) { items.value = []; return }
  loading.value = true
  try {
    const resp = await erpApi.trialBalance(period.value)
    items.value = resp?.items ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(() => reload(true))
</script>
