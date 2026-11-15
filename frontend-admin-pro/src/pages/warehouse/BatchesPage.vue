<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
  批次库存与效期预警。

  两个页签共用一份后端数据源（stock_batch），区别只是筛选口径：
  - 批次明细：按仓库/批次号/状态翻页查，点「流水」看这个批次的全部出入库
  - 效期预警：按 T-7 / T-30 / T-90 / 已过期四档统计，直接复用核心 fifo.expiry_alerts
  本页只读，改数量请走盘点或在库存页做出入库。
-->
<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { http } from '@/utils/http'

const { t } = useI18n()

interface WarehouseOpt {
  id: number
  code: string
  name: string
}

interface BatchRow {
  id: number
  batch_no: string
  supplier_batch_no: string | null
  warehouse_id: number
  location_id: number | null
  location_code: string | null
  sku_id: number
  sku_code: string
  sku_name: string
  qty_on_hand: number
  qty_reserved: number
  available: number
  status: string
  status_label: string
  mfg_date: string | null
  expiry_date: string | null
  days_to_expiry: number | null
  tier: string
}

interface AlertTier {
  tier: string
  count: number
  qty: number
}

interface AlertItem {
  batch_id: number
  batch_no: string
  warehouse_code?: string
  sku_code: string
  sku_name: string
  location_code: string | null
  expiry_date: string
  days_to_expiry: number
  tier: string
  qty_on_hand: number
  available: number
}

interface FlowRow {
  id: number
  qty_delta: number
  biz_type: string
  ref_type: string | null
  ref_id: number | null
  location_code: string | null
  occurred_at: string
  remark: string | null
}

const STATUSES = ['qualified', 'held', 'rejected', 'expired'] as const

const TIER_KEY: Record<string, string> = {
  q7: 'warehouse.batches.tierT7',
  q30: 'warehouse.batches.tierT30',
  q90: 'warehouse.batches.tierT90',
  expired: 'warehouse.batches.tierExpired',
}

const tab = ref('batches')
const loading = ref(false)
const warehouses = ref<WarehouseOpt[]>([])
const rows = ref<BatchRow[]>([])
const total = ref(0)

const filter = reactive({
  warehouse_id: null as number | null,
  batch_no: '',
  status: '' as string,
  expiring_days: null as number | null,
  page: 1,
  size: 20,
})

const alerts = reactive({
  loading: false,
  days: 90,
  summary: { t7: 0, t30: 0, t90: 0, expired: 0, total: 0 },
  tiers: [] as AlertTier[],
  items: [] as AlertItem[],
})

const flowDrawer = reactive({
  open: false,
  loading: false,
  batch: null as BatchRow | null,
  items: [] as FlowRow[],
})

const summaryCards = computed(() => [
  { key: 't7', label: t('warehouse.batches.tierT7'), value: alerts.summary.t7, color: 'danger' },
  { key: 't30', label: t('warehouse.batches.tierT30'), value: alerts.summary.t30, color: 'warning' },
  { key: 't90', label: t('warehouse.batches.tierT90'), value: alerts.summary.t90, color: 'primary' },
  { key: 'expired', label: t('warehouse.batches.tierExpired'), value: alerts.summary.expired, color: 'info' },
])

async function loadWarehouses() {
  const res = await http.request<{ items: WarehouseOpt[] }>({
    url: '/admin/warehouse/warehouses',
    method: 'GET',
  })
  warehouses.value = res.items ?? []
}

async function loadBatches() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      offset: (filter.page - 1) * filter.size,
      limit: filter.size,
    }
    if (filter.warehouse_id) params.warehouse_id = filter.warehouse_id
    if (filter.batch_no.trim()) params.batch_no = filter.batch_no.trim()
    if (filter.status) params.status = filter.status
    if (filter.expiring_days !== null && filter.expiring_days !== undefined) {
      params.expiring_days = filter.expiring_days
    }
    const res = await http.request<{ total: number; items: BatchRow[] }>({
      url: '/admin/warehouse/batches',
      method: 'GET',
      params,
    })
    rows.value = res.items ?? []
    total.value = res.total ?? 0
  } finally {
    loading.value = false
  }
}

async function loadAlerts() {
  alerts.loading = true
  try {
    const params: Record<string, unknown> = { days: alerts.days }
    if (filter.warehouse_id) params.warehouse_id = filter.warehouse_id
    const res = await http.request<{
      summary: { t7: number; t30: number; t90: number; expired: number; total: number }
      tiers: AlertTier[]
      items: AlertItem[]
    }>({ url: '/admin/warehouse/batches/expiry-alerts', method: 'GET', params })
    alerts.summary = res.summary ?? alerts.summary
    alerts.tiers = res.tiers ?? []
    alerts.items = (res.items ?? []) as AlertItem[]
  } finally {
    alerts.loading = false
  }
}

async function openFlows(row: BatchRow) {
  flowDrawer.open = true
  flowDrawer.loading = true
  flowDrawer.batch = row
  try {
    const res = await http.request<{ items: FlowRow[] }>({
      url: `/admin/warehouse/batches/${row.id}/flows`,
      method: 'GET',
    })
    flowDrawer.items = res.items ?? []
  } finally {
    flowDrawer.loading = false
  }
}

function search() {
  filter.page = 1
  void loadBatches()
}

function reset() {
  filter.warehouse_id = null
  filter.batch_no = ''
  filter.status = ''
  filter.expiring_days = null
  filter.page = 1
  void loadBatches()
}

function tierLabel(tier: string) {
  const key = TIER_KEY[tier]
  return key ? t(key) : '—'
}

function tierType(tier: string) {
  if (tier === 'expired') return 'danger'
  if (tier === 'q7') return 'danger'
  if (tier === 'q30') return 'warning'
  if (tier === 'q90') return 'primary'
  return 'info'
}

onMounted(async () => {
  await loadWarehouses()
  await Promise.all([loadBatches(), loadAlerts()])
})
</script>

<template>
  <AdminPage :title="t('warehouse.batches.title')">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center gap-3 flex-wrap">
          <span class="font-medium">{{ t('warehouse.batches.title') }}</span>
          <el-select
            v-model="filter.warehouse_id"
            :placeholder="t('warehouse.stocks.warehouse')"
            clearable
            style="width: 200px"
            @change="search"
          >
            <el-option v-for="w in warehouses" :key="w.id" :label="`${w.code} ${w.name}`" :value="w.id" />
          </el-select>
        </div>
      </template>

      <el-tabs v-model="tab">
        <el-tab-pane :label="t('warehouse.batches.tabBatches')" name="batches">
          <div class="flex items-center gap-2 flex-wrap mb-3">
            <el-input
              v-model="filter.batch_no"
              :placeholder="t('warehouse.batches.batchNoPlaceholder')"
              style="width: 220px"
              clearable
              @keyup.enter="search"
            />
            <el-select v-model="filter.status" clearable :placeholder="t('warehouse.batches.status')" style="width: 150px">
              <el-option v-for="s in STATUSES" :key="s" :label="t(`warehouse.batches.status${s.charAt(0).toUpperCase()}${s.slice(1)}`)" :value="s" />
            </el-select>
            <el-input-number
              v-model="filter.expiring_days"
              :placeholder="t('warehouse.batches.expiringDays')"
              :min="-3650"
              :max="3650"
              :controls="false"
              style="width: 160px"
            />
            <el-button type="primary" @click="search">{{ t('warehouse.warehouses.search') }}</el-button>
            <el-button @click="reset">{{ t('common.reset') }}</el-button>
          </div>

          <el-table v-loading="loading" :data="rows" stripe style="width: 100%" @row-dblclick="openFlows">
            <el-table-column prop="batch_no" :label="t('warehouse.batches.batchNo')" width="170" />
            <el-table-column :label="t('warehouse.batches.supplierBatchNo')" width="150">
              <template #default="{ row }">{{ row.supplier_batch_no || '—' }}</template>
            </el-table-column>
            <el-table-column prop="sku_code" :label="t('warehouse.stocks.skuCode')" width="150" />
            <el-table-column prop="sku_name" :label="t('warehouse.stocks.skuName')" min-width="150" />
            <el-table-column :label="t('warehouse.batches.location')" width="120">
              <template #default="{ row }">{{ row.location_code || '—' }}</template>
            </el-table-column>
            <el-table-column prop="qty_on_hand" :label="t('warehouse.batches.qtyOnHand')" width="100" align="right" />
            <el-table-column prop="qty_reserved" :label="t('warehouse.batches.qtyReserved')" width="100" align="right" />
            <el-table-column prop="available" :label="t('warehouse.batches.available')" width="100" align="right" />
            <el-table-column :label="t('warehouse.batches.status')" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'qualified' ? 'success' : 'info'">{{ row.status_label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('warehouse.batches.expiryDate')" width="130">
              <template #default="{ row }">{{ row.expiry_date || t('warehouse.batches.noExpiry') }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.batches.daysToExpiry')" width="120" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.days_to_expiry !== null" size="small" :type="tierType(row.tier)">
                  {{ row.days_to_expiry }} · {{ tierLabel(row.tier) }}
                </el-tag>
                <span v-else class="text-el-placeholder">—</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('warehouse.warehouses.actions')" width="110" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openFlows(row)">{{ t('warehouse.batches.flowsTitle') }}</el-button>
              </template>
            </el-table-column>
            <template #empty><el-empty :description="t('warehouse.batches.empty')" /></template>
          </el-table>

          <div class="mt-3 flex justify-end">
            <el-pagination
              v-model:current-page="filter.page"
              v-model:page-size="filter.size"
              :total="total"
              :page-sizes="[20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              @current-change="loadBatches"
              @size-change="search"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane :label="t('warehouse.batches.tabExpiry')" name="expiry">
          <div class="flex items-center gap-2 flex-wrap mb-3">
            <span class="text-sm">{{ t('warehouse.batches.expiringDays') }}</span>
            <el-input-number v-model="alerts.days" :min="1" :max="3650" style="width: 130px" />
            <el-button type="primary" @click="loadAlerts">{{ t('common.refresh') }}</el-button>
          </div>

          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <el-card v-for="c in summaryCards" :key="c.key" shadow="never" body-style="padding:12px">
              <div class="text-xs text-el-placeholder">{{ c.label }}</div>
              <div class="text-2xl font-semibold mt-1">{{ c.value }}</div>
            </el-card>
          </div>

          <el-table v-loading="alerts.loading" :data="alerts.items" stripe style="width: 100%">
            <el-table-column prop="batch_no" :label="t('warehouse.batches.batchNo')" width="170" />
            <el-table-column prop="sku_code" :label="t('warehouse.stocks.skuCode')" width="150" />
            <el-table-column prop="sku_name" :label="t('warehouse.stocks.skuName')" min-width="150" />
            <el-table-column :label="t('warehouse.batches.location')" width="120">
              <template #default="{ row }">{{ row.location_code || '—' }}</template>
            </el-table-column>
            <el-table-column prop="expiry_date" :label="t('warehouse.batches.expiryDate')" width="130" />
            <el-table-column :label="t('warehouse.batches.daysToExpiry')" width="100" align="right">
              <template #default="{ row }">{{ row.days_to_expiry }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.batches.status')" width="130">
              <template #default="{ row }">
                <el-tag size="small" :type="tierType(row.tier)">{{ tierLabel(row.tier) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="qty_on_hand" :label="t('warehouse.batches.qtyOnHand')" width="110" align="right" />
            <el-table-column prop="available" :label="t('warehouse.batches.available')" width="110" align="right" />
            <template #empty><el-empty :description="t('warehouse.batches.emptyExpiry')" /></template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-drawer v-model="flowDrawer.open" :title="t('warehouse.batches.flowsTitle')" size="65%">
      <div v-loading="flowDrawer.loading">
        <div v-if="flowDrawer.batch" class="mb-3 text-sm">
          <span class="font-medium">{{ flowDrawer.batch.batch_no }}</span>
          <span class="ml-2 text-el-placeholder">
            {{ flowDrawer.batch.sku_code }} · {{ flowDrawer.batch.qty_on_hand }}
          </span>
        </div>
        <el-table :data="flowDrawer.items" stripe>
          <el-table-column prop="occurred_at" :label="t('warehouse.stocks.time')" width="180" />
          <el-table-column prop="biz_type" :label="t('warehouse.stocks.bizType')" width="150" />
          <el-table-column :label="t('warehouse.stocks.changeQty')" width="110" align="right">
            <template #default="{ row }">
              <span :class="row.qty_delta >= 0 ? 'text-emerald-600' : 'text-red-600'">
                {{ row.qty_delta > 0 ? '+' : '' }}{{ row.qty_delta }}
              </span>
            </template>
          </el-table-column>
          <el-table-column :label="t('warehouse.batches.location')" width="120">
            <template #default="{ row }">{{ row.location_code || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('warehouse.stocks.remark')" min-width="180">
            <template #default="{ row }">{{ row.remark || '—' }}</template>
          </el-table-column>
          <template #empty><el-empty :description="t('warehouse.locations.empty')" /></template>
        </el-table>
      </div>
    </el-drawer>
  </AdminPage>
</template>
