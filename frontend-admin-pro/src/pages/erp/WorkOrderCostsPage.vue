<template>
  <AdminPage :title="t('erp.costs.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-select v-model="status" clearable :placeholder="t('erp.common.status')" style="width:130px" @change="reload(true)">
          <el-option label="draft" value="draft" />
          <el-option label="calculated" value="calculated" />
          <el-option label="closed" value="closed" />
        </el-select>
        <el-input-number v-model="calcWoId" :controls="false" :placeholder="t('erp.costs.woId')" style="width:130px" />
        <el-button type="primary" :loading="calculating" @click="calculate">{{ t('erp.costs.calculate') }}</el-button>
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table :data="items" border>
        <el-table-column prop="work_order_id" :label="t('erp.costs.woId')" width="90" />
        <el-table-column prop="qty" :label="t('erp.costs.qty')" width="70" />
        <el-table-column prop="material_cost" :label="t('erp.costs.material')" width="110" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.material_cost) }}</template>
        </el-table-column>
        <el-table-column prop="labor_cost" :label="t('erp.costs.labor')" width="110" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.labor_cost) }}</template>
        </el-table-column>
        <el-table-column prop="overhead_cost" :label="t('erp.costs.overhead')" width="110" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.overhead_cost) }}</template>
        </el-table-column>
        <el-table-column prop="total_cost" :label="t('erp.costs.total')" width="120" align="right">
          <template #default="{ row }"><b>¥ {{ formatMoney(row.total_cost) }}</b></template>
        </el-table-column>
        <el-table-column prop="quote_amount" :label="t('erp.costs.quote')" width="120" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.quote_amount) }}</template>
        </el-table-column>
        <el-table-column prop="gross_profit" :label="t('erp.costs.profit')" width="120" align="right">
          <template #default="{ row }">
            <span :class="row.gross_profit >= 0 ? 'text-red-500' : 'text-green-600'">¥ {{ formatMoney(row.gross_profit) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('erp.common.actions')" width="90" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">{{ t('erp.common.view') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="drawerVisible" :title="t('erp.costs.detail')" size="520px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('erp.costs.woId')">{{ detail.work_order_id }}</el-descriptions-item>
          <el-descriptions-item :label="t('erp.costs.qty')">{{ detail.qty }}</el-descriptions-item>
          <el-descriptions-item :label="t('erp.costs.total')">¥ {{ formatMoney(detail.total_cost) }}</el-descriptions-item>
          <el-descriptions-item :label="t('erp.costs.unit')">¥ {{ formatMoney(detail.unit_cost) }}</el-descriptions-item>
          <el-descriptions-item :label="t('erp.costs.quote')">¥ {{ formatMoney(detail.quote_amount) }}</el-descriptions-item>
          <el-descriptions-item :label="t('erp.costs.profit')">¥ {{ formatMoney(detail.gross_profit) }}</el-descriptions-item>
        </el-descriptions>
        <el-table :data="detail.items || []" border class="mt-3" size="small">
          <el-table-column prop="cost_type" label="Type" width="90" />
          <el-table-column prop="source_type" label="Source" width="110" />
          <el-table-column prop="ref_code" label="Ref" min-width="90" />
          <el-table-column prop="amount" label="Amount" width="100" align="right">
            <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { erpApi, type WorkOrderCostOut } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const calculating = ref(false)
const items = ref<WorkOrderCostOut[]>([])
const status = ref('')
const calcWoId = ref<number | null>(null)
const drawerVisible = ref(false)
const detail = ref<WorkOrderCostOut | null>(null)

function formatMoney(v: number | undefined | null) {
  return (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function reload(_silent = false) {
  loading.value = true
  try {
    const resp = await erpApi.listCosts({ status: status.value || undefined, limit: 200 })
    items.value = resp?.items ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function calculate() {
  calculating.value = true
  try {
    await erpApi.calculateCost({ work_order_id: calcWoId.value || undefined })
    ElMessage.success(t('erp.common.saved'))
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.saveFailed'))
  } finally {
    calculating.value = false
  }
}

async function openDetail(row: WorkOrderCostOut) {
  detail.value = await erpApi.getCost(row.work_order_id)
  drawerVisible.value = true
}

onMounted(() => reload(true))
</script>
