<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
  库间调拨：建单 → 审核 → 执行，可在未完成前取消。

  执行时后端会整单预检（含冻结批次扣减），任何一行库存不足就整单拒绝，
  不会留下「扣了一半」的单据。前端只负责把失败原因原样弹出来。
-->
<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/utils/http'

const { t } = useI18n()

interface WarehouseOpt {
  id: number
  code: string
  name: string
}

interface LocationOpt {
  id: number
  warehouse_id: number
  code: string
  name: string
}

interface SkuOpt {
  id: number
  code: string
  name: string
  spec: string | null
}

interface TransferRow {
  id: number
  transfer_no: string
  from_warehouse_id: number
  from_warehouse_name: string | null
  from_location_id: number | null
  to_warehouse_id: number
  to_warehouse_name: string | null
  to_location_id: number | null
  status: string
  status_label: string
  reason: string | null
  remark: string | null
  item_count: number
  created_at: string
  approved_at: string | null
  done_at: string | null
}

interface TransferItemRow {
  id: number
  sku_id: number
  sku_code: string
  sku_name: string
  qty: number
  batch_no: string | null
  from_batch_id: number | null
  to_batch_id: number | null
  remark: string | null
}

interface TransferDetail extends TransferRow {
  from_location_code: string | null
  to_location_code: string | null
  items: TransferItemRow[]
}

interface DraftItem {
  sku_id: number | null
  qty: number
  batch_no: string
}

const STATUSES = ['pending', 'approved', 'done', 'cancelled'] as const
const STATUS_TAG: Record<string, string> = {
  draft: 'info',
  pending: 'warning',
  approved: 'primary',
  done: 'success',
  cancelled: 'info',
}

const loading = ref(false)
const rows = ref<TransferRow[]>([])
const total = ref(0)
const statusFilter = ref('')
const page = ref(1)
const size = ref(20)

const warehouses = ref<WarehouseOpt[]>([])
const locations = ref<LocationOpt[]>([])
const skus = ref<SkuOpt[]>([])

const detail = reactive({
  open: false,
  loading: false,
  data: null as TransferDetail | null,
})

const dlg = reactive({
  open: false,
  saving: false,
  form: {
    from_warehouse_id: null as number | null,
    to_warehouse_id: null as number | null,
    from_location_id: null as number | null,
    to_location_id: null as number | null,
    reason: '',
    remark: '',
    items: [] as DraftItem[],
  },
})

const fromLocations = computed(() =>
  locations.value.filter((l) => l.warehouse_id === dlg.form.from_warehouse_id),
)
const toLocations = computed(() => locations.value.filter((l) => l.warehouse_id === dlg.form.to_warehouse_id))
const canSubmit = computed(() => {
  const f = dlg.form
  return !!(f.from_warehouse_id && f.to_warehouse_id && f.items.length && f.items.every((i) => i.sku_id && i.qty > 0))
})

async function loadList() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { offset: (page.value - 1) * size.value, limit: size.value }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await http.request<{ total: number; items: TransferRow[] }>({
      url: '/admin/warehouse/transfers',
      method: 'GET',
      params,
    })
    rows.value = res.items ?? []
    total.value = res.total ?? 0
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [whRes, locRes, skuRes] = await Promise.all([
    http.request<{ items: WarehouseOpt[] }>({ url: '/admin/warehouse/warehouses', method: 'GET' }),
    http.request<{ items: LocationOpt[] }>({ url: '/admin/warehouse/locations', method: 'GET' }),
    http.request<{ items: SkuOpt[] }>({
      url: '/admin/warehouse/stocktake-sku-options',
      method: 'GET',
      params: { limit: 100 },
    }),
  ])
  warehouses.value = whRes.items ?? []
  locations.value = locRes.items ?? []
  skus.value = skuRes.items ?? []
}

function openCreate() {
  dlg.form = {
    from_warehouse_id: null,
    to_warehouse_id: null,
    from_location_id: null,
    to_location_id: null,
    reason: '',
    remark: '',
    items: [{ sku_id: null, qty: 1, batch_no: '' }],
  }
  dlg.open = true
}

function addItem() {
  dlg.form.items.push({ sku_id: null, qty: 1, batch_no: '' })
}

function removeItem(idx: number) {
  dlg.form.items.splice(idx, 1)
}

async function submitCreate() {
  if (!canSubmit.value) {
    ElMessage.warning(t('warehouse.transfers.needItems'))
    return
  }
  const f = dlg.form
  if (f.from_warehouse_id === f.to_warehouse_id && f.from_location_id === f.to_location_id) {
    ElMessage.warning(t('warehouse.transfers.locationSame'))
    return
  }
  dlg.saving = true
  try {
    await http.request({
      url: '/admin/warehouse/transfers',
      method: 'POST',
      data: {
        from_warehouse_id: f.from_warehouse_id,
        to_warehouse_id: f.to_warehouse_id,
        from_location_id: f.from_location_id,
        to_location_id: f.to_location_id,
        reason: f.reason || null,
        remark: f.remark || null,
        items: f.items.map((i) => ({
          sku_id: i.sku_id,
          qty: i.qty,
          batch_no: i.batch_no.trim() || null,
        })),
      },
    })
    ElMessage.success(t('warehouse.transfers.createSuccess'))
    dlg.open = false
    await loadList()
  } finally {
    dlg.saving = false
  }
}

async function openDetail(row: TransferRow) {
  detail.open = true
  detail.loading = true
  try {
    const res = await http.request<TransferDetail>({
      url: `/admin/warehouse/transfers/${row.id}`,
      method: 'GET',
    })
    detail.data = res
  } finally {
    detail.loading = false
  }
}

async function act(row: { id: number }, action: 'approve' | 'execute' | 'cancel') {
  if (action === 'cancel') {
    try {
      await ElMessageBox.confirm(t('warehouse.transfers.cancelConfirm'), t('warehouse.transfers.title'), {
        type: 'warning',
      })
    } catch {
      return
    }
  }
  await http.request({ url: `/admin/warehouse/transfers/${row.id}/${action}`, method: 'POST' })
  const msgKey =
    action === 'approve'
      ? 'warehouse.transfers.approveSuccess'
      : action === 'execute'
        ? 'warehouse.transfers.executeSuccess'
        : 'warehouse.transfers.cancelDoc'
  ElMessage.success(t(msgKey))
  await loadList()
  if (detail.open && detail.data && detail.data.id === row.id) {
    await openDetail(row as TransferRow)
  }
}

function statusKey(status: string) {
  return `warehouse.transfers.status${status.charAt(0).toUpperCase()}${status.slice(1)}`
}

onMounted(async () => {
  await loadOptions()
  await loadList()
})
</script>

<template>
  <AdminPage :title="t('warehouse.transfers.title')">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center gap-2 flex-wrap">
          <span class="font-medium">{{ t('warehouse.transfers.title') }}</span>
        </div>
      </template>

      <div class="flex items-center gap-2 flex-wrap mb-3">
        <el-select v-model="statusFilter" clearable :placeholder="t('warehouse.transfers.status')" style="width: 160px" @change="loadList">
          <el-option v-for="s in STATUSES" :key="s" :label="t(statusKey(s))" :value="s" />
        </el-select>
        <el-button type="primary" @click="openCreate">{{ t('warehouse.transfers.createNew') }}</el-button>
        <el-button @click="loadList">{{ t('common.refresh') }}</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" stripe style="width: 100%">
        <el-table-column prop="transfer_no" :label="t('warehouse.transfers.transferNo')" width="180" />
        <el-table-column :label="t('warehouse.transfers.fromWarehouse')" min-width="140">
          <template #default="{ row }">{{ row.from_warehouse_name || row.from_warehouse_id }}</template>
        </el-table-column>
        <el-table-column :label="t('warehouse.transfers.toWarehouse')" min-width="140">
          <template #default="{ row }">{{ row.to_warehouse_name || row.to_warehouse_id }}</template>
        </el-table-column>
        <el-table-column :label="t('warehouse.transfers.status')" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="STATUS_TAG[row.status] || 'info'">{{ t(statusKey(row.status)) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="item_count" :label="t('warehouse.transfers.items')" width="90" align="right" />
        <el-table-column :label="t('warehouse.transfers.reason')" min-width="140">
          <template #default="{ row }">{{ row.reason || '—' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('warehouse.stocktakes.createdAt')" width="170" />
        <el-table-column :label="t('warehouse.warehouses.actions')" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">{{ t('warehouse.transfers.detail') }}</el-button>
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="primary"
              @click="act(row, 'approve')"
            >
              {{ t('warehouse.transfers.approve') }}
            </el-button>
            <el-button
              v-if="row.status === 'approved'"
              size="small"
              type="success"
              @click="act(row, 'execute')"
            >
              {{ t('warehouse.transfers.execute') }}
            </el-button>
            <el-button
              v-if="row.status === 'pending' || row.status === 'approved'"
              size="small"
              type="danger"
              @click="act(row, 'cancel')"
            >
              {{ t('warehouse.transfers.cancelDoc') }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty :description="t('warehouse.transfers.empty')" /></template>
      </el-table>

      <div class="mt-3 flex justify-end">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadList"
          @size-change="loadList"
        />
      </div>
    </el-card>

    <!-- 新建调拨单 -->
    <el-dialog v-model="dlg.open" :title="t('warehouse.transfers.createTitle')" width="780px" destroy-on-close>
      <el-form :model="dlg.form" label-width="110px">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-x-4">
          <el-form-item :label="t('warehouse.transfers.fromWarehouse')" required>
            <el-select v-model="dlg.form.from_warehouse_id" style="width: 100%" @change="dlg.form.from_location_id = null">
              <el-option v-for="w in warehouses" :key="w.id" :label="`${w.code} ${w.name}`" :value="w.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('warehouse.transfers.toWarehouse')" required>
            <el-select v-model="dlg.form.to_warehouse_id" style="width: 100%" @change="dlg.form.to_location_id = null">
              <el-option v-for="w in warehouses" :key="w.id" :label="`${w.code} ${w.name}`" :value="w.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('warehouse.transfers.fromLocation')">
            <el-select v-model="dlg.form.from_location_id" clearable style="width: 100%">
              <el-option v-for="l in fromLocations" :key="l.id" :label="`${l.code} ${l.name}`" :value="l.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('warehouse.transfers.toLocation')">
            <el-select v-model="dlg.form.to_location_id" clearable style="width: 100%">
              <el-option v-for="l in toLocations" :key="l.id" :label="`${l.code} ${l.name}`" :value="l.id" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item :label="t('warehouse.transfers.reason')">
          <el-input v-model="dlg.form.reason" maxlength="255" />
        </el-form-item>

        <el-divider content-position="left">{{ t('warehouse.transfers.items') }}</el-divider>
        <div v-for="(it, idx) in dlg.form.items" :key="idx" class="flex items-end gap-2 mb-2 flex-wrap">
          <el-select v-model="it.sku_id" filterable :placeholder="t('warehouse.stocks.skuCode')" style="width: 300px">
            <el-option v-for="s in skus" :key="s.id" :label="`${s.code} ${s.name}`" :value="s.id" />
          </el-select>
          <el-input-number v-model="it.qty" :min="1" :precision="0" :controls="false" style="width: 120px" />
          <el-input v-model="it.batch_no" :placeholder="t('warehouse.transfers.batchNoOptional')" style="width: 240px" />
          <el-button type="danger" plain :disabled="dlg.form.items.length <= 1" @click="removeItem(idx)">
            {{ t('warehouse.stocktakes.remove') }}
          </el-button>
        </div>
        <el-button plain @click="addItem">{{ t('warehouse.transfers.addItem') }}</el-button>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('warehouse.warehouses.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" :disabled="!canSubmit" @click="submitCreate">
          {{ t('warehouse.warehouses.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-drawer v-model="detail.open" :title="t('warehouse.transfers.detailTitle')" size="65%">
      <div v-loading="detail.loading">
        <template v-if="detail.data">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item :label="t('warehouse.transfers.transferNo')">
              {{ detail.data.transfer_no }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.transfers.status')">
              <el-tag size="small" :type="STATUS_TAG[detail.data.status] || 'info'">
                {{ t(statusKey(detail.data.status)) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.transfers.fromWarehouse')">
              {{ detail.data.from_warehouse_name || detail.data.from_warehouse_id }}
              <span v-if="detail.data.from_location_code" class="text-el-placeholder">
                / {{ detail.data.from_location_code }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.transfers.toWarehouse')">
              {{ detail.data.to_warehouse_name || detail.data.to_warehouse_id }}
              <span v-if="detail.data.to_location_code" class="text-el-placeholder">
                / {{ detail.data.to_location_code }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.transfers.reason')">
              {{ detail.data.reason || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.stocktakes.createdAt')">
              {{ detail.data.created_at }}
            </el-descriptions-item>
          </el-descriptions>

          <el-table :data="detail.data.items" class="mt-4" stripe>
            <el-table-column prop="sku_code" :label="t('warehouse.stocks.skuCode')" width="150" />
            <el-table-column prop="sku_name" :label="t('warehouse.stocks.skuName')" min-width="150" />
            <el-table-column prop="qty" :label="t('warehouse.transfers.qty')" width="110" align="right" />
            <el-table-column :label="t('warehouse.batches.batchNo')" width="160">
              <template #default="{ row }">{{ row.batch_no || '—' }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.stocks.remark')" min-width="140">
              <template #default="{ row }">{{ row.remark || '—' }}</template>
            </el-table-column>
          </el-table>

          <div class="mt-4 flex gap-2 flex-wrap">
            <el-button
              v-if="detail.data.status === 'pending'"
              type="primary"
              @click="act(detail.data, 'approve')"
            >
              {{ t('warehouse.transfers.approve') }}
            </el-button>
            <el-button
              v-if="detail.data.status === 'approved'"
              type="success"
              @click="act(detail.data, 'execute')"
            >
              {{ t('warehouse.transfers.execute') }}
            </el-button>
            <el-button
              v-if="detail.data.status === 'pending' || detail.data.status === 'approved'"
              type="danger"
              plain
              @click="act(detail.data, 'cancel')"
            >
              {{ t('warehouse.transfers.cancelDoc') }}
            </el-button>
          </div>
        </template>
      </div>
    </el-drawer>
  </AdminPage>
</template>
