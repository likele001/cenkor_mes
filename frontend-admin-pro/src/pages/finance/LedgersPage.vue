<template>
  <AdminPage :title="t('finance.ledgers.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-date-picker
            v-model="query.month"
            type="month"
            value-format="YYYY-MM"
            :placeholder="t('finance.ledgers.month')"
            style="width: 160px"
            @change="reload(true)"
          />
          <el-select v-model="query.direction" clearable :placeholder="t('finance.ledgers.directionFilter')" style="width: 140px" @change="reload(true)">
            <el-option :label="t('finance.ledgers.income')" value="in" />
            <el-option :label="t('finance.ledgers.expense')" value="out" />
          </el-select>
          <el-input v-model="query.category" clearable :placeholder="t('finance.ledgers.categoryPlaceholder')" style="width: 220px" @keyup.enter="reload(true)" />
          <el-select v-model="query.party_type" clearable :placeholder="t('finance.ledgers.partyType')" style="width: 160px" @change="onPartyTypeChange">
            <el-option :label="t('finance.ledgers.customer')" value="customer" />
            <el-option :label="t('finance.ledgers.supplier')" value="supplier" />
            <el-option :label="t('finance.ledgers.other')" value="other" />
          </el-select>
          <el-select
            v-if="query.party_type === 'customer'"
            v-model="query.party_id"
            clearable
            filterable
            :placeholder="t('finance.ledgers.customer')"
            style="width: 240px"
            @change="reload(true)"
          >
            <el-option v-for="c in customers" :key="c.id" :label="partyOptionLabel(c)" :value="c.id" />
          </el-select>
          <el-select
            v-else-if="query.party_type === 'supplier'"
            v-model="query.party_id"
            clearable
            filterable
            :placeholder="t('finance.ledgers.supplier')"
            style="width: 240px"
            @change="reload(true)"
          >
            <el-option v-for="s in suppliers" :key="s.id" :label="partyOptionLabel(s)" :value="s.id" />
          </el-select>
          <el-input-number
            v-else-if="query.party_type === 'other'"
            v-model="query.party_id"
            controls-position="right"
            :placeholder="t('finance.ledgers.partyIdPlaceholder')"
            style="width: 180px"
            @change="reload(true)"
          />
          <el-button @click="reload(true)">{{ t('finance.ledgers.refresh') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="biz_date" :label="t('finance.ledgers.bizDate')" width="120" />
          <el-table-column :label="t('finance.ledgers.direction')" width="100">
            <template #default="{ row }">
              <el-tag :type="row.direction === 'in' ? 'success' : 'danger'">{{ row.direction === 'in' ? t('finance.ledgers.income') : t('finance.ledgers.expense') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="category" :label="t('finance.ledgers.category')" width="160" />
          <el-table-column :label="t('finance.ledgers.party')" min-width="220">
            <template #default="{ row }">
              <span>{{ partyLabel(row.party_type, row.party_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('finance.ledgers.amount')" width="140" align="right">
            <template #default="{ row }">
              <span>{{ formatMoney(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="remark" :label="t('finance.ledgers.remark')" min-width="260" />
          <el-table-column prop="created_at" :label="t('finance.ledgers.createdAt')" width="180" />
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.biz_date }}</div>
                <div class="text-xs text-el-placeholder">{{ row.category || '—' }}</div>
              </div>
              <el-tag :type="row.direction === 'in' ? 'success' : 'danger'" size="small">{{ row.direction === 'in' ? t('finance.ledgers.income') : t('finance.ledgers.expense') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('finance.ledgers.party') }}</dt>
              <dd class="text-left">{{ partyLabel(row.party_type, row.party_id) }}</dd>
              <dt>{{ t('finance.ledgers.amount') }}</dt>
              <dd>{{ formatMoney(row.amount) }}</dd>
              <dt>{{ t('finance.ledgers.remark') }}</dt>
              <dd class="text-left">{{ row.remark || '—' }}</dd>
              <dt>{{ t('finance.ledgers.createdAtShort') }}</dt>
              <dd>{{ row.created_at || '—' }}</dd>
            </dl>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('finance.ledgers.noData')" />
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
import { financeApi, type LedgerOut } from '@/api/finance'
import { productionApi, type CustomerOut } from '@/api/production'
import { materialsApi, type SupplierOut } from '@/api/materials'
import { partyOptionLabel } from '@/utils/display'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const loading = ref(false)
const items = ref<LedgerOut[]>([])
const customers = ref<CustomerOut[]>([])
const suppliers = ref<SupplierOut[]>([])

const query = reactive({
  month: '',
  direction: '',
  category: '',
  party_type: '' as '' | 'customer' | 'supplier' | 'other',
  party_id: null as number | null,
  offset: 0,
  limit: 50,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const customerMap = computed(() => new Map(customers.value.map((x) => [x.id, x])))
const supplierMap = computed(() => new Map(suppliers.value.map((x) => [x.id, x])))

function pad2(n: number) {
  return n < 10 ? `0${n}` : String(n)
}

function monthToDateRange(month: string): { from: string; to: string } | null {
  if (!month) return null
  const [yStr, mStr] = month.split('-')
  const y = Number(yStr)
  const m = Number(mStr)
  if (!y || !m || m < 1 || m > 12) return null
  const lastDay = new Date(y, m, 0).getDate()
  return { from: `${y}-${pad2(m)}-01`, to: `${y}-${pad2(m)}-${pad2(lastDay)}` }
}

function formatMoney(v: number | null) {
  if (v === null || Number.isNaN(v)) return '-'
  return Number(v).toFixed(2)
}

function partyLabel(partyType: string, partyId: number | null) {
  if (!partyType) return '-'
  if (partyType === 'customer') {
    if (!partyId) return t('finance.ledgers.customer')
    const c = customerMap.value.get(partyId)
    return c ? `${t('finance.ledgers.customer')} ${partyOptionLabel(c)}` : `${t('finance.ledgers.customer')} ${partyId}`
  }
  if (partyType === 'supplier') {
    if (!partyId) return t('finance.ledgers.supplier')
    const s = supplierMap.value.get(partyId)
    return s ? `${t('finance.ledgers.supplier')} ${partyOptionLabel(s)}` : `${t('finance.ledgers.supplier')} ${partyId}`
  }
  if (partyType === 'other') return partyId ? `${t('finance.ledgers.other')} ${partyId}` : t('finance.ledgers.other')
  return partyId ? `${partyType} ${partyId}` : partyType
}

async function loadParties() {
  const [cRes, sRes] = await Promise.all([
    productionApi.listCustomers({ keyword: '', offset: 0, limit: 200, include_inactive: true }),
    materialsApi.listSuppliers({ keyword: '', offset: 0, limit: 200, include_inactive: true }),
  ])
  customers.value = cRes.items
  suppliers.value = sRes.items
}

function onPartyTypeChange() {
  query.party_id = null
  reload(true)
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const range = monthToDateRange(query.month)
    const res = await financeApi.listLedgers({
      direction: query.direction || undefined,
      category: query.category || undefined,
      party_type: query.party_type || undefined,
      party_id: query.party_id || undefined,
      biz_date_from: range?.from,
      biz_date_to: range?.to,
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
  await loadParties()
  await reload(true)
})
</script>
