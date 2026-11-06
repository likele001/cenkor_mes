<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  warehouseApi,
  type StocktakeOut,
  type StocktakeSkuOption,
  type StocktakeStatus,
  type WarehouseOut,
} from '@/api/warehouse'
import { partyOptionLabel } from '@/utils/display'
import { saveBlob } from '@/utils/download'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<StocktakeOut[]>([])
const total = ref(0)
const warehouses = ref<WarehouseOut[]>([])

const query = reactive({
  warehouse_id: undefined as number | undefined,
  status: '' as '' | StocktakeStatus,
  page: 1,
  page_size: 20,
})

const STATUS_KEYS: Record<StocktakeStatus, string> = {
  draft: 'warehouse.stocktakes.statusDraft',
  counting: 'warehouse.stocktakes.statusCounting',
  confirmed: 'warehouse.stocktakes.statusConfirmed',
  cancelled: 'warehouse.stocktakes.statusCancelled',
}

const STATUS_TAG: Record<StocktakeStatus, 'info' | 'warning' | 'success'> = {
  draft: 'info',
  counting: 'warning',
  confirmed: 'success',
  cancelled: 'info',
}

function statusText(s: StocktakeStatus) {
  return t(STATUS_KEYS[s] || 'warehouse.stocktakes.statusDraft')
}

function statusTag(s: StocktakeStatus) {
  return STATUS_TAG[s] || 'info'
}

async function loadWarehouses() {
  const res = await warehouseApi.listWarehouses()
  warehouses.value = res.items ?? []
}

async function load() {
  loading.value = true
  try {
    const res = await warehouseApi.listStocktakes({
      warehouse_id: query.warehouse_id,
      status: query.status || undefined,
      offset: (query.page - 1) * query.page_size,
      limit: query.page_size,
    })
    rows.value = res.items ?? []
    total.value = res.total ?? rows.value.length
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  load()
}

function onPageChange(p: number) {
  query.page = p
  load()
}

// ───────────── 新建盘点单 ─────────────
const createVisible = ref(false)
const creating = ref(false)
const form = reactive({
  warehouse_id: undefined as number | undefined,
  item_type: 'all' as 'all' | 'product' | 'material' | 'selected',
  sku_ids: [] as number[],
  remark: '',
})
const skuOptions = ref<StocktakeSkuOption[]>([])
const skuSearching = ref(false)

async function loadSkuOptions(keyword = '') {
  skuSearching.value = true
  try {
    const res = await warehouseApi.stocktakeSkuOptions(keyword)
    skuOptions.value = res.items ?? []
  } finally {
    skuSearching.value = false
  }
}

function openCreate() {
  form.warehouse_id = query.warehouse_id
  form.item_type = 'all'
  form.sku_ids = []
  form.remark = ''
  createVisible.value = true
  loadSkuOptions()
}

async function submitCreate() {
  if (creating.value) return
  if (form.item_type === 'selected' && !form.sku_ids.length) {
    ElMessage.warning(t('warehouse.stocktakes.needSku'))
    return
  }
  creating.value = true
  try {
    const payload: Parameters<typeof warehouseApi.createStocktake>[0] = {
      warehouse_id: form.warehouse_id,
      remark: form.remark || undefined,
    }
    // 指定型号时不再传范围：后端以 sku_ids 为准
    if (form.item_type === 'selected') payload.sku_ids = form.sku_ids
    else payload.item_type = form.item_type
    const st = await warehouseApi.createStocktake(payload)
    createVisible.value = false
    ElMessage.success(t('warehouse.stocktakes.created'))
    await load()
    await openDetail(st)
  } catch {
    /* http 层已提示 */
  } finally {
    creating.value = false
  }
}

// ───────────── 详情：录实盘 / 确认 ─────────────
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<StocktakeOut | null>(null)
const counts = ref<Record<number, number | null>>({})
const saving = ref(false)
const editables = computed(() => detail.value?.status === 'draft' || detail.value?.status === 'counting')
const countedCount = computed(
  () => Object.values(counts.value).filter((v) => v !== null && v !== undefined).length,
)

function resetCounts() {
  const map: Record<number, number | null> = {}
  for (const it of detail.value?.items ?? []) map[it.id] = it.counted_qty
  counts.value = map
}

async function openDetail(row: StocktakeOut) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    detail.value = await warehouseApi.getStocktake(row.id)
    resetCounts()
  } finally {
    detailLoading.value = false
  }
}

async function reloadDetail() {
  if (!detail.value) return
  detail.value = await warehouseApi.getStocktake(detail.value.id)
  resetCounts()
}

function rowDiff(id: number, book: number): number | null {
  const c = counts.value[id]
  if (c === null || c === undefined) return null
  return c - book
}

async function saveCounts() {
  if (!detail.value || saving.value) return
  const items = (detail.value.items ?? [])
    .filter((it) => counts.value[it.id] !== null && counts.value[it.id] !== undefined)
    .map((it) => ({ item_id: it.id, counted_qty: Number(counts.value[it.id]) }))
  if (!items.length) {
    ElMessage.warning(t('warehouse.stocktakes.nothingToSave'))
    return
  }
  saving.value = true
  try {
    await warehouseApi.recordStocktakeCounts(detail.value.id, items)
    ElMessage.success(t('warehouse.stocktakes.saved'))
    await reloadDetail()
    await load()
  } catch {
    /* http 层已提示 */
  } finally {
    saving.value = false
  }
}

async function confirmIt() {
  if (!detail.value) return
  const id = detail.value.id
  if (!countedCount.value) {
    ElMessage.warning(t('warehouse.stocktakes.nothingCounted'))
    return
  }
  try {
    await ElMessageBox.confirm(t('warehouse.stocktakes.confirmTip'), t('warehouse.stocktakes.confirmTitle'), {
      type: 'warning',
      confirmButtonText: t('warehouse.stocktakes.confirmOk'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return
  }
  const res = await warehouseApi.confirmStocktake(id)
  ElMessage.success(
    t('warehouse.stocktakes.confirmedTip', {
      lines: res.adjusted_lines,
      gain: res.gain_qty,
      loss: res.loss_qty,
    }),
  )
  detailVisible.value = false
  await load()
}

async function cancelIt() {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(t('warehouse.stocktakes.cancelTip'), t('warehouse.stocktakes.cancelDoc'), {
      type: 'warning',
      confirmButtonText: t('warehouse.stocktakes.cancelOk'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return
  }
  await warehouseApi.cancelStocktake(detail.value.id)
  ElMessage.success(t('warehouse.stocktakes.cancelled'))
  detailVisible.value = false
  await load()
}

async function exportIt(row: StocktakeOut) {
  const blob = await warehouseApi.exportStocktake(row.id)
  saveBlob(blob, `stocktake_${row.code}.xlsx`)
  ElMessage.success(t('common.exported'))
}

// ───────────── 追加型号（盘盈物资） ─────────────
const addVisible = ref(false)
const addSkuId = ref<number | undefined>(undefined)
const adding = ref(false)

function openAdd() {
  addSkuId.value = undefined
  addVisible.value = true
  loadSkuOptions()
}

async function submitAdd() {
  if (!detail.value || !addSkuId.value || adding.value) return
  adding.value = true
  try {
    await warehouseApi.addStocktakeItem(detail.value.id, { sku_id: addSkuId.value })
    addVisible.value = false
    await reloadDetail()
    await load()
  } catch {
    /* http 层已提示 */
  } finally {
    adding.value = false
  }
}

async function removeLine(itemId: number) {
  if (!detail.value) return
  await warehouseApi.removeStocktakeItem(detail.value.id, itemId)
  await reloadDetail()
  await load()
}

onMounted(async () => {
  await loadWarehouses()
  await load()
})
</script>

<template>
  <AdminPage :title="t('warehouse.stocktakes.title')">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ t('warehouse.stocktakes.title') }}</span>
          <el-button type="primary" size="small" @click="openCreate">{{ t('warehouse.stocktakes.create') }}</el-button>
        </div>
      </template>

      <el-form :model="query" inline>
        <el-form-item :label="t('warehouse.stocktakes.warehouse')">
          <el-select v-model="query.warehouse_id" clearable style="width: 200px" :placeholder="t('warehouse.stocktakes.filterAll')">
            <el-option v-for="w in warehouses" :key="w.id" :label="partyOptionLabel(w)" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('warehouse.stocktakes.status')">
          <el-select v-model="query.status" style="width: 150px">
            <el-option :label="t('warehouse.stocktakes.filterAll')" value="" />
            <el-option :label="t('warehouse.stocktakes.statusDraft')" value="draft" />
            <el-option :label="t('warehouse.stocktakes.statusCounting')" value="counting" />
            <el-option :label="t('warehouse.stocktakes.statusConfirmed')" value="confirmed" />
            <el-option :label="t('warehouse.stocktakes.statusCancelled')" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">{{ t('warehouse.stocktakes.search') }}</el-button>
        </el-form-item>
      </el-form>

      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="rows" stripe style="width: 100%">
          <el-table-column prop="code" :label="t('warehouse.stocktakes.code')" width="160" />
          <el-table-column prop="warehouse_name" :label="t('warehouse.stocktakes.warehouse')" width="150" />
          <el-table-column :label="t('warehouse.stocktakes.status')" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('warehouse.stocktakes.progress')" width="130">
            <template #default="{ row }">{{ row.counted_items }} / {{ row.total_items }}</template>
          </el-table-column>
          <el-table-column :label="t('warehouse.stocktakes.diffRows')" width="110">
            <template #default="{ row }">
              <span :class="row.diff_items ? 'text-red-500 font-medium' : ''">{{ row.diff_items }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" :label="t('warehouse.stocktakes.createdAt')" width="180" />
          <el-table-column prop="confirmed_at" :label="t('warehouse.stocktakes.confirmedAt')" width="180" />
          <el-table-column :label="t('warehouse.stocktakes.actions')" min-width="200">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openDetail(row)">
                {{ t('warehouse.stocktakes.detail') }}
              </el-button>
              <el-button link type="primary" size="small" @click="exportIt(row)">
                {{ t('warehouse.stocktakes.export') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in rows" :key="row.id" class="admin-mobile-row" @click="openDetail(row)">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.code }}</div>
                <div class="text-xs text-el-placeholder">{{ row.warehouse_name || '—' }}</div>
              </div>
              <el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('warehouse.stocktakes.progress') }}</dt>
              <dd>{{ row.counted_items }} / {{ row.total_items }}</dd>
              <dt>{{ t('warehouse.stocktakes.diffRows') }}</dt>
              <dd>{{ row.diff_items }}</dd>
            </dl>
          </div>
          <el-empty v-if="!loading && !rows.length" :description="t('warehouse.stocktakes.empty')" />
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :page-size="query.page_size"
          :total="total"
          :current-page="query.page"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <!-- 新建 -->
    <el-dialog v-model="createVisible" :title="t('warehouse.stocktakes.createTitle')" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item :label="t('warehouse.stocktakes.warehouse')">
          <el-select v-model="form.warehouse_id" clearable style="width: 100%" :placeholder="t('warehouse.stocktakes.autoWarehouse')">
            <el-option v-for="w in warehouses" :key="w.id" :label="partyOptionLabel(w)" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('warehouse.stocktakes.scope')">
          <el-select v-model="form.item_type" style="width: 100%">
            <el-option :label="t('warehouse.stocktakes.scopeAll')" value="all" />
            <el-option :label="t('warehouse.stocktakes.scopeProduct')" value="product" />
            <el-option :label="t('warehouse.stocktakes.scopeMaterial')" value="material" />
            <el-option :label="t('warehouse.stocktakes.scopeSelected')" value="selected" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.item_type === 'selected'" :label="t('warehouse.stocktakes.sku')">
          <el-select
            v-model="form.sku_ids"
            multiple
            filterable
            remote
            reserve-keyword
            :remote-method="loadSkuOptions"
            :loading="skuSearching"
            style="width: 100%"
            :placeholder="t('warehouse.stocktakes.skuPlaceholder')"
          >
            <el-option
              v-for="o in skuOptions"
              :key="o.id"
              :label="`${o.code} ${o.name}`"
              :value="o.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('warehouse.stocktakes.remark')">
          <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">
          {{ t('warehouse.stocktakes.createOk') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-drawer v-model="detailVisible" :title="detail ? `${t('warehouse.stocktakes.detailTitle')} ${detail.code}` : ''" size="76%">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item :label="t('warehouse.stocktakes.warehouse')">
              {{ detail.warehouse_name || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.stocktakes.status')">
              <el-tag :type="statusTag(detail.status)" size="small">{{ statusText(detail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.stocktakes.progress')">
              {{ detail.counted_items }} / {{ detail.total_items }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.stocktakes.diffRows')">{{ detail.diff_items }}</el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.stocktakes.scope')" :span="2">{{ detail.scope }}</el-descriptions-item>
            <el-descriptions-item :label="t('warehouse.stocktakes.createdAt')" :span="2">
              {{ detail.created_at || '—' }}
            </el-descriptions-item>
          </el-descriptions>

          <el-alert class="mt-3" type="info" :closable="false" show-icon :title="t('warehouse.stocktakes.hint')" />

          <div class="mt-3 flex flex-wrap gap-2">
            <el-button v-if="editables" type="primary" size="small" :loading="saving" @click="saveCounts">
              {{ t('warehouse.stocktakes.saveCounts') }}
            </el-button>
            <el-button v-if="editables" size="small" @click="openAdd">{{ t('warehouse.stocktakes.addSku') }}</el-button>
            <el-button v-if="editables" type="success" size="small" @click="confirmIt">
              {{ t('warehouse.stocktakes.confirmOk') }}
            </el-button>
            <el-button v-if="editables" type="danger" plain size="small" @click="cancelIt">
              {{ t('warehouse.stocktakes.cancelDoc') }}
            </el-button>
            <el-button size="small" @click="exportIt(detail)">{{ t('warehouse.stocktakes.export') }}</el-button>
          </div>

          <el-table class="mt-3 w-full" :data="detail.items ?? []" stripe size="small" style="width: 100%">
            <el-table-column prop="sku_code" :label="t('warehouse.stocktakes.skuCode')" width="150" />
            <el-table-column prop="sku_name" :label="t('warehouse.stocktakes.skuName')" min-width="160" />
            <el-table-column prop="sku_spec" :label="t('warehouse.stocktakes.skuSpec')" width="120" />
            <el-table-column prop="book_qty" :label="t('warehouse.stocktakes.bookQty')" width="90" />
            <el-table-column :label="t('warehouse.stocktakes.countedQty')" width="150">
              <template #default="{ row }">
                <el-input-number
                  v-if="editables"
                  v-model="counts[row.id]"
                  :min="0"
                  :step="1"
                  size="small"
                  controls-position="right"
                  style="width: 120px"
                />
                <span v-else>{{ row.counted_qty === null ? t('warehouse.stocktakes.unCounted') : row.counted_qty }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('warehouse.stocktakes.diffQty')" width="100">
              <template #default="{ row }">
                <span
                  v-if="(counts[row.id] ?? null) !== null"
                  :class="rowDiff(row.id, row.book_qty) === 0 ? '' : 'font-medium text-red-500'"
                >
                  {{ rowDiff(row.id, row.book_qty) }}
                </span>
                <span v-else class="text-el-placeholder">—</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('warehouse.stocktakes.adjustedQty')" width="110">
              <template #default="{ row }">
                <span v-if="row.adjusted_qty === null" class="text-el-placeholder">—</span>
                <span v-else :class="row.adjusted_qty === 0 ? '' : 'font-medium'">{{ row.adjusted_qty }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('warehouse.stocktakes.actions')" width="90">
              <template #default="{ row }">
                <el-button
                  v-if="editables && row.counted_qty === null"
                  link
                  type="danger"
                  size="small"
                  @click="removeLine(row.id)"
                >
                  {{ t('warehouse.stocktakes.remove') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-drawer>

    <!-- 追加型号 -->
    <el-dialog v-model="addVisible" :title="t('warehouse.stocktakes.addSkuTitle')" width="480px">
      <el-select
        v-model="addSkuId"
        filterable
        remote
        reserve-keyword
        :remote-method="loadSkuOptions"
        :loading="skuSearching"
        style="width: 100%"
        :placeholder="t('warehouse.stocktakes.skuPlaceholder')"
      >
        <el-option v-for="o in skuOptions" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <template #footer>
        <el-button @click="addVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="adding" @click="submitAdd">{{ t('warehouse.stocktakes.addOk') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>
