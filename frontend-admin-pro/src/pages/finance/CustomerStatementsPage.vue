<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
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
            <el-option :label="t('finance.statements.partial')" value="partial" />
            <el-option :label="t('finance.statements.paid')" value="paid" />
          </el-select>
          <el-button @click="reload(true)">{{ t('finance.statements.refresh') }}</el-button>
          <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
          <el-button type="warning" plain @click="openAging('ar')">{{ t('finance.statements.aging') }}</el-button>
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
          <el-table-column :label="t('finance.statements.dueDate')" width="120">
            <template #default="{ row }">{{ row.due_date || '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('finance.statements.paidAmount')" width="120" align="right">
            <template #default="{ row }">{{ formatMoney(row.paid_amount) }}</template>
          </el-table-column>
          <el-table-column :label="t('finance.statements.balance')" width="120" align="right">
            <template #default="{ row }"><span class="text-red-500">{{ formatMoney(row.balance) }}</span></template>
          </el-table-column>
          <el-table-column :label="t('finance.statements.status')" width="140">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" :label="t('finance.statements.createdAt')" width="180" />
          <el-table-column :label="t('finance.statements.actions')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="router.push(`/finance/statements/${row.id}`)">{{ t('finance.statements.detail') }}</el-button>
              <el-button v-if="row.status === 'confirmed' || row.status === 'partial'" size="small" type="warning" @click="openSettle(row)">{{ t('finance.statements.settle') }}</el-button>
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
              <dt>{{ t('finance.statements.balance') }}</dt>
              <dd class="text-red-500">{{ formatMoney(row.balance) }}</dd>
              <dt>{{ t('finance.statements.createdAtShort') }}</dt>
              <dd>{{ row.created_at || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" type="primary" @click="router.push(`/finance/statements/${row.id}`)">{{ t('finance.statements.detail') }}</el-button>
              <el-button v-if="row.status === 'confirmed' || row.status === 'partial'" size="small" type="warning" @click="openSettle(row)">{{ t('finance.statements.settle') }}</el-button>
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

    <el-dialog v-model="settleVisible" :title="t('finance.settle.title')" width="520px">
      <div v-if="current">
        <div class="flex justify-between text-sm mb-2"><span>{{ t('finance.settle.totalAmount') }}</span><span class="font-semibold">{{ formatMoney(current.total_amount) }}</span></div>
        <div class="flex justify-between text-sm mb-2"><span>{{ t('finance.settle.alreadyPaid') }}</span><span>{{ formatMoney(current.paid_amount) }}</span></div>
        <div class="flex justify-between text-sm mb-4"><span>{{ t('finance.settle.balance') }}</span><span class="font-semibold text-red-500">{{ formatMoney(current.balance) }}</span></div>
        <el-form label-width="110px">
          <el-form-item :label="t('finance.settle.amount')" required>
            <el-input-number v-model="settleForm.amount" :min="0.01" :max="current.balance" :precision="2" :step="100" style="width: 100%" />
          </el-form-item>
          <el-form-item :label="t('finance.settle.paidDate')">
            <el-date-picker v-model="settleForm.paid_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
          <el-form-item :label="t('finance.settle.method')">
            <el-select v-model="settleForm.method" clearable style="width: 100%">
              <el-option :label="t('finance.settle.methodTransfer')" value="transfer" />
              <el-option :label="t('finance.settle.methodCash')" value="cash" />
              <el-option :label="t('finance.settle.methodAcceptance')" value="acceptance" />
              <el-option :label="t('finance.settle.methodOther')" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('finance.settle.remark')">
            <el-input v-model="settleForm.remark" type="textarea" :rows="2" maxlength="500" />
          </el-form-item>
        </el-form>
        <div class="mt-2">
          <div class="text-sm font-semibold mb-1">{{ t('finance.settle.history') }}</div>
          <el-table :data="payments" size="small" border v-loading="paymentsLoading" max-height="180">
            <el-table-column prop="paid_date" :label="t('finance.settle.paidDate')" width="120" />
            <el-table-column :label="t('finance.settle.amount')" align="right"><template #default="{ row }">{{ formatMoney(row.amount) }}</template></el-table-column>
            <el-table-column :label="t('finance.settle.reverse')" width="90"><template #default="{ row }"><el-button size="small" type="danger" text @click="doReverse(row.id)">{{ t('finance.settle.reverse') }}</el-button></template></el-table-column>
          </el-table>
          <div v-if="!paymentsLoading && !payments.length" class="text-xs text-el-placeholder mt-1">{{ t('finance.settle.noPayments') }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="settleVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="settling" @click="doSettle">{{ t('finance.settle.submit') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="agingVisible" :title="t('finance.aging.title')" width="720px">
      <div v-loading="agingLoading">
        <div class="mb-2">
          <el-radio-group v-model="agingDirection" size="small" @change="loadAging">
            <el-radio-button label="ar">{{ t('finance.aging.ar') }}</el-radio-button>
            <el-radio-button label="ap">{{ t('finance.aging.ap') }}</el-radio-button>
          </el-radio-group>
        </div>
        <div class="text-xs text-el-placeholder mb-3">{{ t('finance.aging.asOf') }} {{ aging.as_of }}</div>
        <div class="grid grid-cols-2 gap-3 mb-4">
          <div class="p-2 rounded bg-gray-50"><div class="text-xs text-el-placeholder">{{ t('finance.aging.totalBalance') }}</div><div class="font-semibold">{{ formatMoney(aging.total_balance) }}</div></div>
          <div class="p-2 rounded bg-gray-50"><div class="text-xs text-el-placeholder">{{ t('finance.aging.overdueBalance') }}</div><div class="font-semibold text-red-500">{{ formatMoney(aging.overdue_balance) }}</div></div>
        </div>
        <el-table :data="aging.buckets" size="small" border class="mb-3">
          <el-table-column :label="t('finance.aging.title')"><template #default="{ row }">{{ bucketLabel(row.bucket) }}</template></el-table-column>
          <el-table-column prop="count" :label="t('finance.aging.count')" width="80" align="right" />
          <el-table-column :label="t('finance.aging.balance')" width="140" align="right"><template #default="{ row }">{{ formatMoney(row.balance) }}</template></el-table-column>
        </el-table>
        <el-table :data="aging.items" size="small" border max-height="240">
          <el-table-column prop="code" :label="t('finance.aging.code')" width="180" />
          <el-table-column :label="t('finance.aging.balance')" width="120" align="right"><template #default="{ row }">{{ formatMoney(row.balance) }}</template></el-table-column>
          <el-table-column prop="due_date" :label="t('finance.aging.dueDate')" width="120" />
          <el-table-column :label="t('finance.aging.daysOverdue')" width="110" align="right"><template #default="{ row }">{{ row.days_overdue }}</template></el-table-column>
        </el-table>
        <div v-if="!agingLoading && !aging.items.length" class="text-xs text-el-placeholder mt-2">{{ t('finance.aging.noData') }}</div>
      </div>
      <template #footer><el-button @click="agingVisible = false">{{ t('finance.aging.close') }}</el-button></template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { financeApi, type CustomerStatementOut, type AgingResp, type StatementPaymentOut } from '@/api/finance'
import { productionApi, type CustomerOut } from '@/api/production'
import { partyOptionLabel } from '@/utils/display'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import { useExport } from '@/composables/useExport'
import { ElMessage, ElMessageBox } from 'element-plus'

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

const settleVisible = ref(false)
const settling = ref(false)
const current = ref<CustomerStatementOut | null>(null)
const payments = ref<StatementPaymentOut[]>([])
const paymentsLoading = ref(false)
const settleForm = reactive({ amount: 0, paid_date: '', method: '', remark: '' })

const agingVisible = ref(false)
const agingLoading = ref(false)
const agingDirection = ref<'ar' | 'ap'>('ar')
const aging = ref<AgingResp>({ direction: 'ar', as_of: '', total_balance: 0, overdue_balance: 0, buckets: [], items: [] })

const BUCKET_LABEL: Record<string, string> = {
  not_due: 'finance.aging.bucketNotDue',
  '1_30': 'finance.aging.bucket1_30',
  '31_60': 'finance.aging.bucket31_60',
  '61_90': 'finance.aging.bucket61_90',
  '90_plus': 'finance.aging.bucket90_plus',
}
function bucketLabel(b: string) { return t(BUCKET_LABEL[b] || 'finance.aging.bucketNotDue') }

async function openSettle(row: CustomerStatementOut) {
  current.value = row
  settleForm.amount = Number(row.balance) || 0
  settleForm.paid_date = new Date().toISOString().slice(0, 10)
  settleForm.method = ''
  settleForm.remark = ''
  settleVisible.value = true
  await loadPayments()
}
async function loadPayments() {
  if (!current.value) return
  paymentsLoading.value = true
  try {
    const res = await financeApi.listCustomerStatementPayments(current.value.id)
    payments.value = res.items
  } finally { paymentsLoading.value = false }
}
async function doSettle() {
  if (!current.value) return
  if (!settleForm.amount || settleForm.amount <= 0) { ElMessage.warning(t('finance.settle.amountRequired')); return }
  settling.value = true
  try {
    await financeApi.createCustomerStatementPayment(current.value.id, {
      amount: settleForm.amount,
      paid_date: settleForm.paid_date || null,
      method: settleForm.method || null,
      remark: settleForm.remark || null,
    })
    ElMessage.success(t('finance.settle.success'))
    settleVisible.value = false
    await reload(false)
  } finally { settling.value = false }
}
async function doReverse(pid: number) {
  await ElMessageBox.confirm(t('finance.settle.reverseConfirm'), { type: 'warning' })
  await financeApi.reversePayment(pid)
  ElMessage.success(t('finance.settle.reversed'))
  await loadPayments()
  await reload(false)
}
function openAging(dir: 'ar' | 'ap') { agingDirection.value = dir; agingVisible.value = true; loadAging() }
async function loadAging() {
  agingLoading.value = true
  try { aging.value = await financeApi.getAging(agingDirection.value) }
  finally { agingLoading.value = false }
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
