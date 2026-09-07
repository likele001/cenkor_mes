<template>
  <AdminPage :title="t('erp.assets.depreciation')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-date-picker v-model="period" type="month" value-format="YYYY-MM" :placeholder="t('erp.common.period')" @change="reload(true)" />
        <el-button type="primary" :loading="depreciating" @click="depreciate">{{ t('erp.assets.depreciateBatch') }}</el-button>
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table :data="items" border>
        <el-table-column prop="asset_id" :label="t('erp.assets.assetId')" width="90" />
        <el-table-column prop="period" :label="t('erp.common.period')" width="110" />
        <el-table-column prop="depreciation_amount" :label="t('erp.assets.deprAmount')" width="140" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.depreciation_amount) }}</template>
        </el-table-column>
        <el-table-column prop="accumulated_depreciation" :label="t('erp.assets.accumulated')" width="150" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.accumulated_depreciation) }}</template>
        </el-table-column>
        <el-table-column prop="book_value" :label="t('erp.assets.bookValue')" width="140" align="right">
          <template #default="{ row }"><b>¥ {{ formatMoney(row.book_value) }}</b></template>
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
import { erpApi, type DepreciationRecordOut } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const depreciating = ref(false)
const period = ref('')
const items = ref<DepreciationRecordOut[]>([])

function formatMoney(v: number | undefined | null) {
  return (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function reload(_silent = false) {
  loading.value = true
  try {
    const resp = await erpApi.listDepreciation({ period: period.value || undefined, limit: 200 })
    items.value = resp?.items ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function depreciate() {
  if (!period.value) {
    ElMessage.warning(t('erp.common.periodRequired'))
    return
  }
  depreciating.value = true
  try {
    const resp = await erpApi.depreciateBatch(period.value)
    ElMessage.success(t('erp.assets.deprDone') + ': ' + String((resp as any)?.created ?? 0))
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.saveFailed'))
  } finally {
    depreciating.value = false
  }
}

onMounted(() => reload(true))
</script>
