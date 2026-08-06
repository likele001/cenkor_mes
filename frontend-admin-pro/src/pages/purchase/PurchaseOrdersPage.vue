<template>
  <AdminPage :title="t('purchase.orders.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-input v-model="query.keyword" :placeholder="t('purchase.orders.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
          <el-select v-model="query.supplier_id" clearable filterable :placeholder="t('purchase.orders.supplier')" style="width: 220px" @change="reload(true)">
            <el-option v-for="s in suppliers" :key="s.id" :label="partyOptionLabel(s)" :value="s.id" />
          </el-select>
          <el-select v-model="query.status" clearable :placeholder="t('purchase.orders.status')" style="width: 160px" @change="reload(true)">
            <el-option :label="t('purchase.orders.statusDraft')" value="draft" />
            <el-option :label="t('purchase.orders.statusConfirmed')" value="confirmed" />
            <el-option :label="t('purchase.orders.statusPartialReceived')" value="partial_received" />
            <el-option :label="t('purchase.orders.statusReceived')" value="received" />
            <el-option :label="t('purchase.orders.statusCanceled')" value="canceled" />
          </el-select>
          <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
          <el-button @click="reload(true)">{{ t('purchase.orders.refresh') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="code" :label="t('purchase.orders.code')" width="220" />
          <el-table-column :label="t('purchase.orders.supplier')" width="240">
            <template #default="{ row }">
              <span>{{ row.supplier_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('purchase.orders.status')" width="140">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remark" :label="t('purchase.orders.remark')" min-width="240" />
          <el-table-column prop="confirmed_at" :label="t('purchase.orders.confirmedAt')" width="180" />
          <el-table-column prop="created_at" :label="t('purchase.orders.createdAt')" width="180" />
          <el-table-column :label="t('purchase.orders.action')" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="router.push(`/purchase/orders/${row.id}`)">{{ t('purchase.orders.detail') }}</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.code }}</div>
                <div class="text-xs text-el-placeholder">{{ row.supplier_name || '—' }} · #{{ row.id }}</div>
              </div>
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('purchase.orders.remark') }}</dt>
              <dd class="text-left">{{ row.remark || '—' }}</dd>
              <dt>{{ t('purchase.orders.confirm') }}</dt>
              <dd>{{ row.confirmed_at || '—' }}</dd>
              <dt>{{ t('purchase.orders.create') }}</dt>
              <dd>{{ row.created_at || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" type="primary" @click="router.push(`/purchase/orders/${row.id}`)">{{ t('purchase.orders.detail') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('purchase.orders.empty')" />
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
import { useI18n } from 'vue-i18n'
import { purchaseApi, type PurchaseOrderOut } from '@/api/purchase'
import { materialsApi, type SupplierOut } from '@/api/materials'
import { partyOptionLabel } from '@/utils/display'
import { useStatus } from '@/utils/status-maps'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const items = ref<PurchaseOrderOut[]>([])
const suppliers = ref<SupplierOut[]>([])

const query = reactive({
  keyword: '',
  supplier_id: null as number | null,
  status: '',
  offset: 0,
  limit: 50,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const { label: statusLabel, type: statusTagType } = useStatus('purchase_order')
const exporting = ref(false)

async function loadSuppliers() {
  const res = await materialsApi.listSuppliers({ keyword: '', offset: 0, limit: 200, include_inactive: true })
  suppliers.value = res.items
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await purchaseApi.exportOrders()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `purchase_orders_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await purchaseApi.listOrders({
      keyword: query.keyword || undefined,
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

onMounted(async () => {
  await loadSuppliers()
  await reload(true)
})
</script>
