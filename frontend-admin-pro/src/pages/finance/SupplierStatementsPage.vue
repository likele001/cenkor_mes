<template>
  <AdminPage :title="t('finance.supplierStatements.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-select v-model="query.supplier_id" clearable filterable :placeholder="t('finance.supplierStatements.supplier')" style="width: 240px" @change="reload(true)">
          <el-option v-for="s in suppliers" :key="s.id" :label="supplierLabel(s)" :value="s.id" />
        </el-select>
        <el-select v-model="query.status" clearable :placeholder="t('finance.supplierStatements.statusFilter')" style="width: 160px" @change="reload(true)">
          <el-option :label="t('finance.supplierStatements.draft')" value="draft" />
          <el-option :label="t('finance.supplierStatements.confirmed')" value="confirmed" />
          <el-option :label="t('finance.supplierStatements.paid')" value="paid" />
        </el-select>
        <el-button @click="reload(true)">{{ t('finance.supplierStatements.refresh') }}</el-button>
        <el-button type="primary" @click="createVisible = true">{{ t('finance.supplierStatements.create') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table class="hidden lg:block w-full" :data="items" border>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="code" :label="t('finance.supplierStatements.code')" width="220" />
        <el-table-column :label="t('finance.supplierStatements.supplier')" min-width="200">
          <template #default="{ row }">
            <span>{{ row.supplier_name || row.supplier_id }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('finance.supplierStatements.period')" width="260">
          <template #default="{ row }">
            <span v-if="row.period_start || row.period_end">{{ row.period_start || '-' }} 至 {{ row.period_end || '-' }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('finance.supplierStatements.amount')" width="140" align="right">
          <template #default="{ row }">
            <span>{{ formatMoney(row.total_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('finance.supplierStatements.status')" width="140">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('finance.supplierStatements.createdAt')" width="180" />
        <el-table-column :label="t('finance.supplierStatements.actions')" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="router.push(`/finance/supplier-statements/${row.id}`)">{{ t('finance.supplierStatements.detail') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="lg:hidden space-y-3">
        <div v-for="row in items" :key="row.id" class="admin-mobile-row">
          <div class="admin-mobile-row__head">
            <div class="min-w-0">
              <div class="font-semibold text-el-primary">{{ row.code }}</div>
              <div class="text-xs text-el-placeholder">{{ row.supplier_name || row.supplier_id }}</div>
            </div>
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </div>
          <dl class="admin-mobile-kv">
            <dt>{{ t('finance.supplierStatements.period') }}</dt>
            <dd class="text-left">
              <span v-if="row.period_start || row.period_end">{{ row.period_start || '-' }} 至 {{ row.period_end || '-' }}</span>
              <span v-else>—</span>
            </dd>
            <dt>{{ t('finance.supplierStatements.amount') }}</dt>
            <dd>{{ formatMoney(row.total_amount) }}</dd>
            <dt>{{ t('finance.supplierStatements.createdAtShort') }}</dt>
            <dd>{{ row.created_at || '—' }}</dd>
          </dl>
          <div class="admin-mobile-actions">
            <el-button size="small" type="primary" @click="router.push(`/finance/supplier-statements/${row.id}`)">{{ t('finance.supplierStatements.detail') }}</el-button>
          </div>
        </div>
        <el-empty v-if="!loading && !items.length" :description="t('finance.supplierStatements.noData')" />
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

    <!-- 创建对账单对话框 -->
    <el-dialog v-model="createVisible" :title="t('finance.supplierStatements.create')" width="560px">
      <el-form label-width="100px">
        <el-form-item :label="t('finance.supplierStatements.supplier')" required>
          <el-select v-model="createForm.supplier_id" filterable style="width: 100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="supplierLabel(s)" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('finance.supplierStatements.orders')" required>
          <el-select
            v-model="createForm.order_ids"
            multiple
            filterable
            style="width: 100%"
            :placeholder="t('finance.supplierStatements.selectOrders')"
            :disabled="!createForm.supplier_id"
          >
            <el-option
              v-for="o in orders"
              :key="o.id"
              :label="`${o.code} (${o.supplier_name || ''}) ${formatMoney(o.total_amount)}`"
              :value="o.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('finance.supplierStatements.period')">
          <el-date-picker
            v-model="createForm.period"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="~"
            :start-placeholder="t('finance.supplierStatements.startDate')"
            :end-placeholder="t('finance.supplierStatements.endDate')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="t('finance.supplierStatements.remark')">
          <el-input v-model="createForm.remark" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { financeApi, type SupplierStatementOut } from '@/api/finance'
import { purchaseApi } from '@/api/purchase'
import { materialsApi, type SupplierOut } from '@/api/materials'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const creating = ref(false)
const items = ref<SupplierStatementOut[]>([])
const suppliers = ref<SupplierOut[]>([])
const orders = ref<any[]>([])

const query = reactive({
  supplier_id: null as number | null,
  status: '',
  offset: 0,
  limit: 50,
})

const createVisible = ref(false)
const createForm = reactive({
  supplier_id: null as number | null,
  order_ids: [] as number[],
  period: null as [string, string] | null,
  remark: '',
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

function supplierLabel(s: SupplierOut) {
  return `${s.code} ${s.name}`
}

function formatMoney(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return Number(v).toFixed(2)
}

const { label: statusLabel, type: statusTagType } = useStatus('purchase_statement')

async function loadSuppliers() {
  const res = await materialsApi.listSuppliers({ offset: 0, limit: 200, include_inactive: true })
  suppliers.value = res.items
}

async function loadOrders() {
  if (!createForm.supplier_id) {
    orders.value = []
    return
  }
  const res = await purchaseApi.listOrders({ supplier_id: createForm.supplier_id, status: 'confirmed', offset: 0, limit: 200 })
  orders.value = res.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await financeApi.listSupplierStatements({
      supplier_id: query.supplier_id || undefined,
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

async function doCreate() {
  if (!createForm.supplier_id) {
    ElMessage.warning(t('finance.supplierStatements.selectSupplier'))
    return
  }
  if (!createForm.order_ids.length) {
    ElMessage.warning(t('finance.supplierStatements.selectOrders'))
    return
  }
  creating.value = true
  try {
    const res = await financeApi.createSupplierStatement({
      supplier_id: createForm.supplier_id,
      order_ids: createForm.order_ids,
      period_start: createForm.period?.[0] ?? null,
      period_end: createForm.period?.[1] ?? null,
      remark: createForm.remark || null,
    })
    ElMessage.success(t('finance.supplierStatements.created'))
    createVisible.value = false
    createForm.supplier_id = null
    createForm.order_ids = []
    createForm.period = null
    createForm.remark = ''
    router.push(`/finance/supplier-statements/${res.id}`)
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  await loadSuppliers()
  await reload(true)
})
</script>
