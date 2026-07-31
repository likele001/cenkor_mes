<template>
  <AdminPage :title="t('dashboard.kanban.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-select v-model="query.status" clearable :placeholder="t('dashboard.kanban.orderStatus')" style="width: 160px" @change="reload(true)">
            <el-option :label="t('dashboard.kanban.draft')" value="draft" />
            <el-option :label="t('dashboard.kanban.confirmed')" value="confirmed" />
          </el-select>
          <el-select
            v-model="query.customer_id"
            clearable
            filterable
            :placeholder="t('dashboard.kanban.customer')"
            style="width: 220px"
            @change="reload(true)"
          >
            <el-option v-for="c in customers" :key="c.id" :label="partyOptionLabel(c)" :value="c.id" />
          </el-select>
          <el-date-picker
            v-model="dueRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            :range-separator="t('dashboard.kanban.to')"
            :start-placeholder="t('dashboard.kanban.deliveryStart')"
            :end-placeholder="t('dashboard.kanban.deliveryEnd')"
            @change="reload(true)"
          />
          <el-button @click="reload(true)">{{ t('dashboard.kanban.refresh') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="code" :label="t('dashboard.kanban.orderNo')" width="240" />
          <el-table-column :label="t('dashboard.kanban.customer')" min-width="200">
            <template #default="{ row }">
              <div class="truncate">
                {{ row.customer ? partyOptionLabel(row.customer) : '-' }}
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('dashboard.kanban.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.status === 'draft' ? 'info' : 'success'">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('dashboard.kanban.deliveryDate')" width="200">
            <template #default="{ row }">
              <el-tag v-if="row.due_date" :type="levelTagType(row.warning_level)">
                {{ row.due_date }}{{ dueDaysText(row.due_days) }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('dashboard.kanban.progress')" min-width="300">
            <template #default="{ row }">
              <div class="flex items-center gap-3">
                <el-progress
                  :percentage="toPercent(row.progress)"
                  :stroke-width="10"
                  :text-inside="true"
                  :format="() => percentLabel(row)"
                  :color="levelProgressColor(row.warning_level)"
                />
                <div class="text-[12px] text-gray-600 whitespace-nowrap">{{ row.done_qty }}/{{ row.total_qty }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('dashboard.kanban.action')" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="goDetail(row.id)">{{ t('dashboard.kanban.view') }}</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.code }}</div>
                <div class="text-xs text-el-placeholder truncate">
                  {{ row.customer ? partyOptionLabel(row.customer) : '-' }}
                </div>
              </div>
              <el-tag :type="row.status === 'draft' ? 'info' : 'success'" size="small">{{ statusLabel(row.status) }}</el-tag>
            </div>
            <div v-if="row.due_date" class="mb-2">
              <el-tag :type="levelTagType(row.warning_level)" size="small">
                {{ t('dashboard.kanban.deliveryDate') }} {{ row.due_date }}{{ dueDaysText(row.due_days) }}
              </el-tag>
            </div>
            <el-progress
              :percentage="toPercent(row.progress)"
              :stroke-width="12"
              :text-inside="true"
              :format="() => percentLabel(row)"
              :color="levelProgressColor(row.warning_level)"
            />
            <div class="text-xs text-el-placeholder mt-1">{{ row.done_qty }}/{{ row.total_qty }}</div>
            <div class="admin-mobile-actions">
              <el-button size="small" type="primary" @click="goDetail(row.id)">{{ t('dashboard.kanban.view') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('dashboard.kanban.noOrders')" />
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
import { kanbanApi, type KanbanOrderOut } from '@/api/kanban'
import { productionApi, type CustomerOut } from '@/api/production'
import { partyOptionLabel } from '@/utils/display'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const { label: statusLabel } = useStatus('order')
const router = useRouter()

const loading = ref(false)
const items = ref<KanbanOrderOut[]>([])
const customers = ref<CustomerOut[]>([])
const dueRange = ref<[string, string] | null>(null)
const query = reactive({ status: '', customer_id: undefined as number | undefined, offset: 0, limit: 50 })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

function toPercent(v: number | null) {
  if (typeof v !== 'number') return 0
  const p = Math.round(v * 10000) / 100
  if (p < 0) return 0
  if (p > 100) return 100
  return p
}

function percentLabel(row: KanbanOrderOut) {
  if (typeof row.progress !== 'number' || row.total_qty <= 0) return '-'
  return `${toPercent(row.progress)}%`
}

function levelTagType(level: string) {
  if (level === 'overdue') return 'danger'
  if (level === 'warn') return 'warning'
  return 'success'
}

function levelProgressColor(level: string) {
  if (level === 'overdue') return '#ef4444'
  if (level === 'warn') return '#f59e0b'
  return '#10b981'
}

function dueDaysText(v: number | null) {
  if (v === null || v === undefined) return ''
  return ` (${v}${t('dashboard.kanban.days')})`
}

async function loadCustomers() {
  const res = await productionApi.listCustomers({ offset: 0, limit: 200, include_inactive: false })
  customers.value = res.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const due_from = dueRange.value?.[0]
    const due_to = dueRange.value?.[1]
    const res = await kanbanApi.listOrders({
      status: query.status || undefined,
      customer_id: query.customer_id || undefined,
      due_from: due_from || undefined,
      due_to: due_to || undefined,
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

function goDetail(id: number) {
  router.push(`/dashboard/kanban/orders/${id}`)
}

onMounted(async () => {
  await loadCustomers()
  await reload(true)
})
</script>
