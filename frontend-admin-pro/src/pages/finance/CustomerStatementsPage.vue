<template>
  <AdminPage :title="t('finance.statements.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-select v-model="query.customer_id" clearable filterable :placeholder="t('finance.statements.customer')" style="width: 240px" @change="reload(true)">
            <el-option v-for="c in customers" :key="c.id" :label="partyOptionLabel(c)" :value="c.id" />
          </el-select>
          <el-select v-model="query.status" clearable :placeholder="t('finance.statements.statusFilter')" style="width: 160px" @change="reload(true)">
            <el-option :label="t('finance.statements.draft')" value="draft" />
            <el-option :label="t('finance.statements.confirmed')" value="confirmed" />
            <el-option :label="t('finance.statements.paid')" value="paid" />
          </el-select>
          <el-button @click="reload(true)">{{ t('finance.statements.refresh') }}</el-button>
          <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="code" :label="t('finance.statements.code')" width="220" />
          <el-table-column :label="t('finance.statements.customer')" min-width="240">
            <template #default="{ row }">
              <span>{{ customerLabel(row.customer_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('finance.statements.period')" width="260">
            <template #default="{ row }">
              <span v-if="row.period_start || row.period_end">{{ row.period_start || '-' }} 至 {{ row.period_end || '-' }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('finance.statements.amount')" width="140" align="right">
            <template #default="{ row }">
              <span>{{ formatMoney(row.total_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('finance.statements.status')" width="140">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" :label="t('finance.statements.createdAt')" width="180" />
          <el-table-column :label="t('finance.statements.actions')" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="router.push(`/finance/statements/${row.id}`)">{{ t('finance.statements.detail') }}</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.code }}</div>
                <div class="text-xs text-el-placeholder">{{ customerLabel(row.customer_id) }}</div>
              </div>
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('finance.statements.period') }}</dt>
              <dd class="text-left">
                <span v-if="row.period_start || row.period_end">{{ row.period_start || '-' }} 至 {{ row.period_end || '-' }}</span>
                <span v-else>—</span>
              </dd>
              <dt>{{ t('finance.statements.amount') }}</dt>
              <dd>{{ formatMoney(row.total_amount) }}</dd>
              <dt>{{ t('finance.statements.createdAtShort') }}</dt>
              <dd>{{ row.created_at || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" type="primary" @click="router.push(`/finance/statements/${row.id}`)">{{ t('finance.statements.detail') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('finance.statements.noData')" />
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :page-size="query.limit"
          :total="fakeTotal"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { financeApi, type CustomerStatementOut } from '@/api/finance'
import { productionApi, type CustomerOut } from '@/api/production'
import { partyOptionLabel } from '@/utils/display'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import { useExport } from '@/composables/useExport'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const items = ref<CustomerStatementOut[]>([])

const { exporting, doExport } = useExport()
const customers = ref<CustomerOut[]>([])

const query = reactive({
  customer_id: null as number | null,
  status: '',
  offset: 0,
  limit: 50,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const customerMap = computed(() => new Map(customers.value.map((x) => [x.id, x])))

function customerLabel(customerId: number) {
  const c = customerMap.value.get(customerId)
  if (!c) return String(customerId)
  return partyOptionLabel(c)
}

const { label: statusLabel, type: statusTagType } = useStatus('customer_statement')

function formatMoney(v: number | null) {
  if (v === null || Number.isNaN(v)) return '-'
  return Number(v).toFixed(2)
}

async function loadCustomers() {
  const res = await productionApi.listCustomers({ keyword: '', offset: 0, limit: 200, include_inactive: true })
  customers.value = res.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await financeApi.listCustomerStatements({
      customer_id: query.customer_id || undefined,
      status: query.status || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

onMounted(async () => {
  await loadCustomers()
  await reload(true)
})

async function exportExcel() {
  await doExport(
    () => financeApi.exportStatementsExcel({
      customer_id: query.customer_id || undefined,
      status: query.status || undefined,
    }),
    `statements_${new Date().toISOString().slice(0, 10)}.xlsx`,
  )
}
</script>
