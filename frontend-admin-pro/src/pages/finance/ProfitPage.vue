<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { financeApi, type ProfitOut } from '@/api/finance'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const loading = ref(false)
const data = ref<ProfitOut | null>(null)

const query = reactive({
  month: '',
})

function formatMoney(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return '0.00'
  return Number(v).toFixed(2)
}

function formatPercent(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return '0.00%'
  return `${(Number(v) * 100).toFixed(2)}%`
}

const revenue = computed(() => data.value?.revenue ?? 0)
const cost = computed(() => data.value?.cost ?? 0)
const grossProfit = computed(() => data.value?.gross_profit ?? 0)
const grossMargin = computed(() => data.value?.gross_margin ?? 0)

async function loadData() {
  if (!query.month) return
  loading.value = true
  try {
    data.value = await financeApi.getProfit({ month: query.month })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const now = new Date()
  query.month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  loadData()
})
</script>


<template>
  <AdminPage :title="t('finance.profit.title')">
    <el-row :gutter="16" class="mb-4">
      <el-col :span="6">
        <el-card shadow="never">
          <div class="text-sm text-zinc-500">{{ t('finance.profit.revenue') }}</div>
          <div class="mt-1 text-2xl font-bold text-emerald-600">¥{{ formatMoney(revenue) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="text-sm text-zinc-500">{{ t('finance.profit.cost') }}</div>
          <div class="mt-1 text-2xl font-bold text-rose-600">¥{{ formatMoney(cost) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="text-sm text-zinc-500">{{ t('finance.profit.grossProfit') }}</div>
          <div class="mt-1 text-2xl font-bold text-orange-600">¥{{ formatMoney(grossProfit) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="text-sm text-zinc-500">{{ t('finance.profit.grossMargin') }}</div>
          <div class="mt-1 text-2xl font-bold">{{ formatPercent(grossMargin) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="mb-4">
      <div class="flex items-center gap-2 flex-wrap">
        <div class="text-[16px] font-semibold">{{ t('finance.profit.title') }}</div>
        <div class="flex-1" />
        <el-date-picker v-model="query.month" type="month" value-format="YYYY-MM" :placeholder="t('finance.profit.month')" style="width: 160px" />
        <el-button type="primary" :loading="loading" @click="loadData">{{ t('finance.profit.query') }}</el-button>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never">
          <div class="font-medium">{{ t('finance.profit.customerRevenue') }}</div>
          <el-table class="hidden lg:block mt-3 w-full" :data="data?.breakdown.customers || []" v-loading="loading" border>
            <el-table-column prop="customer_id" :label="t('finance.profit.customerId')" width="100" />
            <el-table-column prop="customer_name" :label="t('finance.profit.customer')" min-width="180" />
            <el-table-column :label="t('finance.profit.amount')" width="140" align="right">
              <template #default="{ row }">
                <span class="font-medium text-emerald-600">¥{{ formatMoney(row.amount) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="lg:hidden space-y-3 mt-3">
            <div v-for="row in data?.breakdown.customers || []" :key="row.customer_id" class="admin-mobile-row">
              <dl class="admin-mobile-kv">
                <dt>{{ t('finance.profit.customer') }}</dt>
                <dd>{{ row.customer_name || `ID ${row.customer_id}` }}</dd>
                <dt>{{ t('finance.profit.amount') }}</dt>
                <dd class="text-emerald-600 font-medium">¥{{ formatMoney(row.amount) }}</dd>
              </dl>
            </div>
            <el-empty v-if="!(data?.breakdown.customers?.length)" :description="t('finance.profit.noData')" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <div class="font-medium">{{ t('finance.profit.supplierCost') }}</div>
          <el-table class="hidden lg:block mt-3 w-full" :data="data?.breakdown.suppliers || []" v-loading="loading" border>
            <el-table-column prop="supplier_id" :label="t('finance.profit.supplierId')" width="110" />
            <el-table-column prop="supplier_name" :label="t('finance.profit.supplier')" min-width="180" />
            <el-table-column :label="t('finance.profit.amount')" width="140" align="right">
              <template #default="{ row }">
                <span class="font-medium text-rose-600">¥{{ formatMoney(row.amount) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="lg:hidden space-y-3 mt-3">
            <div v-for="row in data?.breakdown.suppliers || []" :key="row.supplier_id" class="admin-mobile-row">
              <dl class="admin-mobile-kv">
                <dt>{{ t('finance.profit.supplier') }}</dt>
                <dd>{{ row.supplier_name || `ID ${row.supplier_id}` }}</dd>
                <dt>{{ t('finance.profit.amount') }}</dt>
                <dd class="text-rose-600 font-medium">¥{{ formatMoney(row.amount) }}</dd>
              </dl>
            </div>
            <el-empty v-if="!(data?.breakdown.suppliers?.length)" :description="t('finance.profit.noData')" />
          </div>
        </el-card>
      </el-col>
    </el-row>  </AdminPage>
</template>
