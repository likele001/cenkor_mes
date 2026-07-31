<template>
  <AdminPage :title="t('master.processPrices.title')">
    <el-card>
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="text-[16px] font-semibold">{{ t('master.processPrices.title') }}</div>
        <div class="flex items-center gap-2 flex-wrap justify-end">
          <el-select v-model="query.sku_id" clearable filterable :placeholder="t('master.processPrices.sku')" style="width: 320px" @change="reload(true)">
            <el-option v-for="s in skus" :key="s.id" :label="skuOptionLabel(s)" :value="s.id">
              <div class="leading-tight py-0.5">
                <div>{{ skuOptionLabel(s) }}</div>
                <div class="text-xs text-zinc-400">{{ masterSkuOptionSubline(s) }}</div>
              </div>
            </el-option>
          </el-select>
          <el-switch v-model="query.include_inactive" :active-text="t('master.processPrices.includeDisabled')" @change="reload(true)" />
          <el-button type="primary" @click="openBatch()">{{ t('master.processPrices.batchSet') }}</el-button>
          <el-button plain @click="openCreate">{{ t('master.processPrices.add') }}</el-button>
          <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
        </div>
      </div>

      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" :label="t('master.common.id')" width="90" />
          <el-table-column :label="t('master.processPrices.product')" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ productLabel(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.processPrices.sku')" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ skuLabel(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.processPrices.process')" width="120">
            <template #default="{ row }">
              <span>{{ processLabel(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="unit_price" :label="t('master.processPrices.unitPrice')" width="140" />
          <el-table-column :label="t('master.processPrices.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('master.processPrices.enabled') : t('master.processPrices.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.processPrices.operation')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('master.processPrices.edit') }}</el-button>
              <el-popconfirm :title="t('master.processPrices.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.processPrices.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ productLabel(row) }}</div>
                <div class="text-xs text-el-placeholder">{{ skuLabel(row) }} · #{{ row.id }}</div>
              </div>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('master.processPrices.enabled') : t('master.processPrices.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('master.processPrices.process') }}</dt>
              <dd>{{ processLabel(row) }}</dd>
              <dt>{{ t('master.processPrices.unitPrice') }}</dt>
              <dd>{{ row.unit_price }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('master.processPrices.edit') }}</el-button>
              <el-popconfirm :title="t('master.processPrices.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.processPrices.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('master.processPrices.noData')" />
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
    </el-card>

    <el-dialog v-model="batch.open" :title="t('master.processPrices.batchSetTitle')" width="860px" destroy-on-close @closed="resetBatch">
      <el-alert
        class="mb-3"
        type="info"
        :closable="false"
        :title="t('master.processPrices.batchHint')"
        :description="t('master.processPrices.batchHintDesc')"
      />
      <el-form inline class="mb-3">
        <el-form-item :label="t('master.processPrices.sku')">
          <el-select v-model="batch.skuId" filterable style="width: 320px" @change="loadBatchMatrix">
            <el-option v-for="s in skus" :key="s.id" :label="skuOptionLabel(s)" :value="s.id">
              <div class="leading-tight py-0.5">
                <div>{{ skuOptionLabel(s) }}</div>
                <div class="text-xs text-zinc-400">{{ masterSkuOptionSubline(s) }}</div>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item v-if="batch.routeHint">
          <span class="text-sm text-zinc-500">{{ t('master.processPrices.routeLabel') }}{{ batch.routeHint }}</span>
        </el-form-item>
      </el-form>

      <el-table v-loading="batch.loading" :data="batch.rows" border size="small" max-height="420">
        <el-table-column :label="t('master.processPrices.process')" min-width="180">
          <template #default="{ row }">
            <template v-if="row._picker">
              <el-select v-model="row.process_id" filterable :placeholder="t('master.processPrices.pleaseSelectProcess')" style="width: 100%" @change="onPickProcess(row)">
                <el-option
                  v-for="p in availableProcessesForRow(row)"
                  :key="p.id"
                  :label="processOptionLabel(p)"
                  :value="p.id"
                />
              </el-select>
            </template>
            <span v-else>{{ row.process_display_name || row.process_name }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('master.processPrices.unitPriceLabel')" width="160">
          <template #default="{ row }">
            <el-input v-model="row.unit_price" :placeholder="t('master.processPrices.unitPriceHint')" :disabled="!row.process_id" />
          </template>
        </el-table-column>
        <el-table-column :label="t('master.processPrices.enable')" width="80" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" :disabled="!row.process_id" />
          </template>
        </el-table-column>
        <el-table-column :label="t('master.processPrices.operation')" width="70">
          <template #default="{ $index }">
            <el-button link type="danger" @click="batch.rows.splice($index, 1)">{{ t('master.processPrices.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-button class="mt-2" size="small" @click="addBatchRow">{{ t('master.processPrices.addRow') }}</el-button>

      <template #footer>
        <el-button @click="batch.open = false">{{ t('master.common.cancel') }}</el-button>
        <el-button type="primary" :loading="batch.saving" :disabled="!batch.skuId" @click="saveBatch">{{ t('master.processPrices.saveAll') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dlg.open" :title="dlg.id ? t('master.processPrices.editTitle') : t('master.processPrices.addTitle')" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="90px">
        <el-form-item :label="t('master.processPrices.sku')" prop="sku_id">
          <el-select v-model="dlg.form.sku_id" filterable style="width: 100%" :disabled="Boolean(dlg.id)">
            <el-option v-for="s in skus" :key="s.id" :label="skuOptionLabel(s)" :value="s.id">
              <div class="leading-tight py-0.5">
                <div>{{ skuOptionLabel(s) }}</div>
                <div class="text-xs text-zinc-400">{{ masterSkuOptionSubline(s) }}</div>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item :label="t('master.processPrices.process')" prop="process_id">
          <el-select v-model="dlg.form.process_id" filterable style="width: 100%" :disabled="Boolean(dlg.id)">
            <el-option v-for="p in processes" :key="p.id" :label="processOptionLabel(p)" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('master.processPrices.unitPrice')" prop="unit_price">
          <el-input v-model="dlg.form.unit_price" :placeholder="t('master.processPrices.unitPriceHint')" />
        </el-form-item>
        <el-form-item :label="t('master.processPrices.enable')" prop="is_active">
          <el-switch v-model="dlg.form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('master.common.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('master.common.save') }}</el-button>
      </template>
    </el-dialog>  </AdminPage>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { masterApi, type ProcessOut, type ProcessPriceOut, type ProductOut, type SkuOut } from '@/api/master'
import { masterSkuOptionLabel, masterSkuOptionSubline, processOptionLabel, processRowLabel } from '@/utils/display'

const { t } = useI18n()

type BatchRow = {
  process_id: number | null
  process_name?: string
  process_display_name?: string
  unit_price: string
  is_active: boolean
  _picker?: boolean
}

const loading = ref(false)
const exporting = ref(false)
const route = useRoute()
const items = ref<ProcessPriceOut[]>([])
const skus = ref<SkuOut[]>([])
const products = ref<ProductOut[]>([])
const processes = ref<ProcessOut[]>([])
const query = reactive({ sku_id: null as number | null, offset: 0, limit: 50, include_inactive: false })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { sku_id: null as number | null, process_id: null as number | null, unit_price: '', is_active: true },
})

const batch = reactive({
  open: false,
  skuId: null as number | null,
  loading: false,
  saving: false,
  routeHint: '',
  rows: [] as BatchRow[],
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  sku_id: [{ required: true, message: t('master.processPrices.pleaseSelectSku'), trigger: 'change' }],
  process_id: [{ required: true, message: t('master.processPrices.pleaseSelectProcess'), trigger: 'change' }],
  unit_price: [{ required: true, message: t('master.processPrices.pleaseInputPrice'), trigger: 'blur' }],
}

function productLabel(row: ProcessPriceOut) {
  if (row.product?.display_name) return row.product.display_name
  if (row.product?.name) return row.product.name
  const s = skus.value.find((x) => x.id === row.sku_id)
  if (!s) return '—'
  const p = products.value.find((x) => x.id === s.product_id)
  return p ? (p.display_name || p.name) : '—'
}

function skuLabel(row: ProcessPriceOut) {
  if (row.sku?.display_label) return row.sku.display_label
  if (row.sku?.display_name) return row.sku.display_name
  const s = skus.value.find((x) => x.id === row.sku_id)
  return s ? masterSkuOptionLabel(s) : `${row.sku_id}`
}

function skuOptionLabel(s: SkuOut) {
  return masterSkuOptionLabel(s)
}

function processLabel(row: ProcessPriceOut) {
  return processRowLabel(row)
}

async function loadOptions() {
  const [s, pr, p] = await Promise.all([
    masterApi.listSkus({ offset: 0, limit: 200, include_inactive: true }),
    masterApi.listProducts({ offset: 0, limit: 200, include_inactive: true }),
    masterApi.listProcesses({ offset: 0, limit: 200, include_inactive: true }),
  ])
  skus.value = s.items
  products.value = pr.items
  processes.value = p.items
}

function listPricesParams() {
  const params: Record<string, unknown> = {
    offset: query.offset,
    limit: query.limit,
    include_inactive: query.include_inactive,
  }
  if (query.sku_id != null) params.sku_id = query.sku_id
  return params
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await masterApi.listPrices(listPricesParams())
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

function openCreate() {
  dlg.id = null
  dlg.form = { sku_id: query.sku_id, process_id: null, unit_price: '', is_active: true }
  dlg.open = true
}

function openBatch(skuId?: number | null) {
  batch.open = true
  batch.skuId = skuId ?? query.sku_id
  batch.rows = []
  batch.routeHint = ''
  if (batch.skuId) loadBatchMatrix()
}

function resetBatch() {
  batch.skuId = null
  batch.rows = []
  batch.routeHint = ''
}

async function loadBatchMatrix() {
  if (!batch.skuId) {
    batch.rows = []
    batch.routeHint = ''
    return
  }
  batch.loading = true
  try {
    const res = await masterApi.getPriceMatrix(batch.skuId)
    batch.routeHint = res.route_name ? `${res.route_name}` : t('master.processPrices.noRouteHint')
    batch.rows = (res.rows || []).map((r) => ({
      process_id: r.process_id,
      process_name: r.process_name,
      process_display_name: r.process_display_name || r.process_name,
      unit_price: r.unit_price != null ? String(r.unit_price) : '',
      is_active: r.is_active,
    }))
    if (!batch.rows.length) addBatchRow()
  } finally {
    batch.loading = false
  }
}

function usedProcessIds(excludeRow?: BatchRow) {
  return new Set(batch.rows.filter((r) => r !== excludeRow && r.process_id).map((r) => r.process_id!))
}

function availableProcessesForRow(row: BatchRow) {
  const used = usedProcessIds(row)
  return processes.value.filter((p) => !used.has(p.id))
}

function addBatchRow() {
  batch.rows.push({ process_id: null, unit_price: '', is_active: true, _picker: true })
}

function onPickProcess(row: BatchRow) {
  const p = processes.value.find((x) => x.id === row.process_id)
  if (p) {
    row.process_name = p.name
    row.process_display_name = p.display_name || p.name
    row._picker = false
  }
}

async function saveBatch() {
  if (!batch.skuId) return
  const batchItems = batch.rows
    .filter((r) => r.process_id && String(r.unit_price).trim() !== '')
    .map((r) => ({
      process_id: Number(r.process_id),
      unit_price: String(r.unit_price).trim(),
      is_active: r.is_active,
    }))
  if (!batchItems.length) {
    ElMessage.warning(t('master.processPrices.pleaseFillAtLeastOne'))
    return
  }
  batch.saving = true
  try {
    const res = await masterApi.batchSavePrices({ sku_id: batch.skuId, items: batchItems })
    ElMessage.success(t('master.processPrices.batchSaveSuccess', { created: res.created, updated: res.updated }))
    batch.open = false
    query.sku_id = batch.skuId
    await reload(true)
  } finally {
    batch.saving = false
  }
}

function openEdit(row: ProcessPriceOut) {
  dlg.id = row.id
  dlg.form = { sku_id: row.sku_id, process_id: row.process_id, unit_price: String(row.unit_price), is_active: row.is_active }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    if (!dlg.id) {
      await masterApi.createPrice({
        sku_id: dlg.form.sku_id,
        process_id: dlg.form.process_id,
        unit_price: dlg.form.unit_price,
        is_active: dlg.form.is_active,
      })
    } else {
      await masterApi.updatePrice(dlg.id, {
        unit_price: dlg.form.unit_price,
        is_active: dlg.form.is_active,
      })
    }
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: ProcessPriceOut) {
  await masterApi.disablePrice(row.id)
  await reload(false)
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await masterApi.exportProcessPrices({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `process-prices_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(async () => {
  await loadOptions()
  await reload(true)
  const qSku = route.query.sku_id
  if (route.query.batch === '1' && qSku) {
    openBatch(Number(qSku))
  }
})
</script>
