<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { warehouseApi, type StockLogOut, type StockOut, type WarehouseOut } from '@/api/warehouse'
import { partyOptionLabel } from '@/utils/display'
import { useExport } from '@/composables/useExport'

const { t } = useI18n()

const activeTab = ref<'stocks' | 'logs'>('stocks')

const loading = ref(false)
const items = ref<StockOut[]>([])

const { exporting, doExport } = useExport()
const logsLoading = ref(false)
const logs = ref<StockLogOut[]>([])
const warehouses = ref<WarehouseOut[]>([])

const query = reactive({
  warehouse_id: undefined as number | undefined,
  item_type: 'all' as 'all' | 'product' | 'material',
  keyword: '',
})

const logQuery = reactive({
  warehouse_id: undefined as number | undefined,
  item_type: 'all' as 'all' | 'product' | 'material',
  sku_id: undefined as number | undefined,
  offset: 0,
  limit: 50,
})

const filtered = computed(() => {
  const kw = query.keyword.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter((x) => {
    const a = (x.sku_code || '').toLowerCase()
    const b = (x.sku_name || '').toLowerCase()
    return a.includes(kw) || b.includes(kw)
  })
})

async function loadWarehouses() {
  const res = await warehouseApi.listWarehouses()
  warehouses.value = res.items ?? []
}

async function loadStocks() {
  loading.value = true
  try {
    const res = await warehouseApi.listStocks({ warehouse_id: query.warehouse_id, item_type: query.item_type })
    items.value = res.items ?? []
  } finally {
    loading.value = false
  }
}

async function loadLogs(reset = false) {
  if (reset) logQuery.offset = 0
  logsLoading.value = true
  try {
    const res = await warehouseApi.listLogs({
      warehouse_id: logQuery.warehouse_id,
      item_type: logQuery.item_type,
      sku_id: logQuery.sku_id,
      offset: logQuery.offset,
      limit: logQuery.limit,
    })
    logs.value = res.items ?? []
  } finally {
    logsLoading.value = false
  }
}

const logPage = computed(() => Math.floor(logQuery.offset / logQuery.limit) + 1)
const logFakeTotal = computed(() => logQuery.offset + logs.value.length + (logs.value.length === logQuery.limit ? logQuery.limit : 0))

function onLogPageChange(p: number) {
  logQuery.offset = (p - 1) * logQuery.limit
  loadLogs(false)
}

onMounted(async () => {
  await loadWarehouses()
  await loadStocks()
  await loadLogs(true)
})

async function exportExcel() {
  await doExport(
    () => warehouseApi.exportStocks({
      warehouse_id: query.warehouse_id,
      item_type: query.item_type,
    }),
    `stocks_${new Date().toISOString().slice(0, 10)}.xlsx`,
  )
}
</script>


<template>
  <AdminPage :title="t('warehouse.stocks.title')">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ t('warehouse.stocks.title') }}</span>
          <el-button size="small" :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="mt-2">
        <el-tab-pane :label="t('warehouse.stocks.tabStocks')" name="stocks">
          <el-form :model="query" inline>
            <el-form-item :label="t('warehouse.stocks.warehouse')">
              <el-select v-model="query.warehouse_id" clearable style="width: 220px" :placeholder="t('warehouse.stocks.all')">
                <el-option v-for="w in warehouses" :key="w.id" :label="partyOptionLabel(w)" :value="w.id" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('warehouse.stocks.type')">
              <el-select v-model="query.item_type" style="width: 140px">
                <el-option :label="t('warehouse.stocks.all')" value="all" />
                <el-option :label="t('warehouse.stocks.finishedProduct')" value="product" />
                <el-option :label="t('warehouse.stocks.material')" value="material" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('warehouse.stocks.keyword')">
              <el-input v-model="query.keyword" clearable :placeholder="t('warehouse.stocks.keywordPlaceholder')" style="width: 220px" @keyup.enter="loadStocks" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadStocks">{{ t('warehouse.stocks.search') }}</el-button>
            </el-form-item>
          </el-form>

          <div class="mt-4" v-loading="loading">
            <el-table class="hidden lg:block w-full" :data="filtered" stripe style="width: 100%">
              <el-table-column prop="warehouse_name" :label="t('warehouse.stocks.warehouse')" width="180" />
              <el-table-column prop="sku_code" :label="t('warehouse.stocks.skuCode')" width="180" />
              <el-table-column prop="sku_name" :label="t('warehouse.stocks.skuName')" min-width="260" />
              <el-table-column prop="qty" :label="t('warehouse.stocks.quantity')" width="120" />
              <el-table-column prop="updated_at" :label="t('warehouse.stocks.updatedAt')" width="180" />
            </el-table>
            <div class="lg:hidden space-y-3">
              <div v-for="row in filtered" :key="row.id" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <div class="min-w-0">
                    <div class="font-semibold text-el-primary">{{ row.sku_name || row.sku_code }}</div>
                    <div class="text-xs text-el-placeholder">{{ row.sku_code }}</div>
                  </div>
                  <span class="text-sm font-medium text-el-primary">{{ row.qty }}</span>
                </div>
                <dl class="admin-mobile-kv">
                  <dt>{{ t('warehouse.stocks.warehouse') }}</dt>
                  <dd>{{ row.warehouse_name || '—' }}</dd>
                  <dt>{{ t('warehouse.stocks.updated') }}</dt>
                  <dd>{{ row.updated_at || '—' }}</dd>
                </dl>
              </div>
              <el-empty v-if="!loading && !filtered.length" :description="t('warehouse.stocks.emptyStocks')" />
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="t('warehouse.stocks.tabLogs')" name="logs">
          <el-form :model="logQuery" inline>
            <el-form-item :label="t('warehouse.stocks.warehouse')">
              <el-select v-model="logQuery.warehouse_id" clearable style="width: 220px" :placeholder="t('warehouse.stocks.all')">
                <el-option v-for="w in warehouses" :key="w.id" :label="partyOptionLabel(w)" :value="w.id" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('warehouse.stocks.type')">
              <el-select v-model="logQuery.item_type" style="width: 140px">
                <el-option :label="t('warehouse.stocks.all')" value="all" />
                <el-option :label="t('warehouse.stocks.finishedProduct')" value="product" />
                <el-option :label="t('warehouse.stocks.material')" value="material" />
              </el-select>
            </el-form-item>
            <el-form-item label="SKU ID">
              <el-input-number v-model="logQuery.sku_id" :min="1" :placeholder="t('warehouse.stocks.all')" style="width: 140px" clearable />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadLogs(true)">{{ t('warehouse.stocks.search') }}</el-button>
            </el-form-item>
          </el-form>

          <div class="mt-4" v-loading="logsLoading">
            <el-table class="hidden lg:block w-full" :data="logs" stripe style="width: 100%">
              <el-table-column prop="created_at" :label="t('warehouse.stocks.time')" width="180" />
              <el-table-column prop="warehouse_name" :label="t('warehouse.stocks.warehouse')" width="160" />
              <el-table-column prop="sku_code" :label="t('warehouse.stocks.skuCode')" width="180" />
              <el-table-column prop="sku_name" :label="t('warehouse.stocks.skuName')" min-width="240" />
              <el-table-column prop="biz_type" :label="t('warehouse.stocks.bizType')" width="140" />
              <el-table-column prop="change_qty" :label="t('warehouse.stocks.changeQty')" width="100" />
              <el-table-column prop="balance_qty" :label="t('warehouse.stocks.balanceQty')" width="100" />
              <el-table-column prop="remark" :label="t('warehouse.stocks.remark')" min-width="180" />
            </el-table>
            <div class="lg:hidden space-y-3">
              <div v-for="row in logs" :key="row.id" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <div class="min-w-0">
                    <div class="font-semibold text-el-primary text-sm">{{ row.sku_name || row.sku_code }}</div>
                    <div class="text-xs text-el-placeholder">{{ row.created_at }}</div>
                  </div>
                  <div class="text-right text-sm">
                    <div class="text-el-regular">{{ t('warehouse.stocks.changeQty') }} {{ row.change_qty }}</div>
                    <div class="text-xs text-el-placeholder">{{ t('warehouse.stocks.balanceQty') }} {{ row.balance_qty }}</div>
                  </div>
                </div>
                <dl class="admin-mobile-kv">
                  <dt>{{ t('warehouse.stocks.warehouse') }}</dt>
                  <dd>{{ row.warehouse_name || '—' }}</dd>
                  <dt>{{ t('warehouse.stocks.bizType') }}</dt>
                  <dd>{{ row.biz_type || '—' }}</dd>
                  <dt>{{ t('warehouse.stocks.remark') }}</dt>
                  <dd>{{ row.remark || '—' }}</dd>
                </dl>
              </div>
              <el-empty v-if="!logsLoading && !logs.length" :description="t('warehouse.stocks.emptyLogs')" />
            </div>
          </div>

          <div class="mt-4 flex justify-end">
            <el-pagination
              background
              layout="prev, pager, next"
              :page-size="logQuery.limit"
              :total="logFakeTotal"
              :current-page="logPage"
              @current-change="onLogPageChange"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>  </AdminPage>
</template>
