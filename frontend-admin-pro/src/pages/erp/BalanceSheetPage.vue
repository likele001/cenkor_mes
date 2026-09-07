<template>
  <AdminPage :title="t('erp.reports.balanceSheet')">
    <template #actions>
      <div class="flex items-center gap-2">
        <el-date-picker v-model="period" type="month" value-format="YYYY-MM" :placeholder="t('erp.common.period')" @change="reload(true)" />
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <template v-if="data">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <el-card shadow="never">
            <div class="text-sm text-gray-500">{{ t('erp.reports.assets') }}</div>
            <div class="text-2xl font-bold text-red-500 mt-1">¥ {{ formatMoney(data.assets) }}</div>
          </el-card>
          <el-card shadow="never">
            <div class="text-sm text-gray-500">{{ t('erp.reports.liabilities') }}</div>
            <div class="text-2xl font-bold text-orange-500 mt-1">¥ {{ formatMoney(data.liabilities) }}</div>
          </el-card>
          <el-card shadow="never">
            <div class="text-sm text-gray-500">{{ t('erp.reports.equity') }}</div>
            <div class="text-2xl font-bold text-green-600 mt-1">¥ {{ formatMoney(data.equity) }}</div>
          </el-card>
        </div>
        <el-alert class="mt-4" :title="t('erp.reports.balanceHint') + ': ' + (data.balance === 0 ? '✓' : '✗ ' + formatMoney(data.balance))"
                  :type="data.balance === 0 ? 'success' : 'warning'" :closable="false" />
      </template>
      <el-empty v-if="!loading && !data" :description="t('erp.common.empty')" />
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { erpApi } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const period = ref('')
const data = ref<{ assets: number; liabilities: number; equity: number; balance: number } | null>(null)

function formatMoney(v: number | undefined | null) {
  return (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function reload(_silent = false) {
  if (!period.value) { data.value = null; return }
  loading.value = true
  try {
    data.value = await erpApi.balanceSheet(period.value)
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(() => reload(true))
</script>
