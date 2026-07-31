<template>
  <AdminPage :title="t('production.workOrders.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-input-number v-model="query.order_id" :min="1" :controls="false" :placeholder="t('production.workOrders.orderId')" style="width: 140px" @change="reload(true)" />
          <el-select v-model="query.status" clearable :placeholder="t('production.common.status')" style="width: 140px" @change="reload(true)">
            <el-option :label="t('production.common.all')" value="" />
            <el-option :label="t('production.workOrders.statusOpen')" value="open" />
            <el-option :label="t('production.workOrders.statusInProgress')" value="in_progress" />
            <el-option :label="t('production.workOrders.statusDone')" value="done" />
            <el-option :label="t('production.workOrders.statusCancelled')" value="cancelled" />
          </el-select>
          <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
          <el-button @click="reload(true)">{{ t('production.common.refresh') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="order_id" label="订单ID" width="90" />
          <el-table-column :label="t('production.workOrders.sku')" min-width="200">
            <template #default="{ row }">
              <span v-if="row.sku">{{ skuRowLabel({ sku: row.sku }) }}</span>
              <span v-else class="text-zinc-400">{{ t('production.common.customer') }}#{{ row.sku_id }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="qty" :label="t('production.workOrders.quantity')" width="80" />
          <el-table-column :label="t('production.common.status')" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.workOrders.taskProgress')" width="180">
            <template #default>
              <span class="text-xs text-zinc-400">{{ t('production.workOrders.clickDetail') }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" :label="t('production.workOrders.createTime')" width="170" />
          <el-table-column :label="t('production.common.operation')" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openDetail(row.id)">{{ t('production.common.detail') }}</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">
                  <span v-if="row.sku">{{ row.sku.display_label || row.sku.name }}</span>
                  <span v-else>{{ t('production.common.customer') }}#{{ row.sku_id }}</span>
                </div>
                <div class="text-xs text-el-placeholder">{{ t('production.workOrders.orderPrefix') }} #{{ row.id }} · {{ t('production.common.customer') }} {{ row.order_id }}</div>
              </div>
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('production.workOrders.skuName') }}</dt>
              <dd>{{ row.sku?.name || '—' }}</dd>
              <dt>{{ t('production.workOrders.quantityLabel') }}</dt>
              <dd>{{ row.qty }}</dd>
              <dt>{{ t('production.workOrders.createdTime') }}</dt>
              <dd>{{ row.created_at }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" type="primary" @click="openDetail(row.id)">{{ t('production.common.detail') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" description="暂无数据" />
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

    <template #extra>
    <!-- 详情弹窗 -->
    <el-dialog v-model="detailOpen" :title="t('production.workOrders.detailTitle')" width="800px" destroy-on-close @closed="detailData=null">
      <div v-loading="detailLoading" v-if="detailData">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="ID">{{ detailData.id }}</el-descriptions-item>
          <el-descriptions-item label="订单ID">{{ detailData.order_id }}</el-descriptions-item>
          <el-descriptions-item label="SKU">
            <span v-if="detailData.sku">{{ skuRowLabel({ sku: detailData.sku }) }}</span>
            <span v-else>#{{ detailData.sku_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="数量">{{ detailData.qty }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detailData.status)" size="small">{{ statusLabel(detailData.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detailData.created_at }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="mt-4 mb-2 text-sm font-medium">{{ t('production.workOrders.allTasks', { count: detailData.tasks?.length || 0 }) }}{{ detailData.tasks?.length || 0 }} 项）</h4>
        <el-table class="hidden lg:block w-full" :data="detailData.tasks || []" size="small" border stripe>
          <el-table-column prop="seq" :label="t('production.workOrders.processSeq')" width="90" />
          <el-table-column :label="t('production.workOrders.process')" min-width="160">
            <template #default="{ row }">
              <span v-if="row.process">{{ processRowLabel({ process: row.process }) }}</span>
              <span v-else>{{ row.process_id }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="task_code" :label="t('production.workOrders.taskCode')" min-width="150" />
          <el-table-column prop="planned_qty" :label="t('production.workOrders.plannedQty')" width="80" />
          <el-table-column :label="t('production.common.status')" width="100">
            <template #default="{ row }">
              <el-tag :type="taskStatusType(row.status)" size="small">{{ taskStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.workOrders.assignedUser')" width="100">
            <template #default="{ row }">
              {{ row.assigned_user_id ? `用户#${row.assigned_user_id}` : '—' }}
            </template>
          </el-table-column>
        </el-table>
        <div class="lg:hidden space-y-3">
          <div v-for="row in detailData.tasks || []" :key="row.task_code + '-' + row.seq" class="admin-mobile-row">
            <div class="font-mono text-xs text-el-regular">{{ row.task_code }}</div>
            <div class="text-sm">
              <span v-if="row.process">{{ row.process.name }}</span>
              <span v-else>#{{ row.process_id }}</span>
              · 顺序 {{ row.seq }}
            </div>
            <dl class="admin-mobile-kv mt-2">
              <dt>计划</dt>
              <dd>{{ row.planned_qty }}</dd>
              <dt>派工</dt>
              <dd>{{ row.assigned_user_id ? `用户#${row.assigned_user_id}` : '—' }}</dd>
              <dt>状态</dt>
              <dd>
                <el-tag :type="taskStatusType(row.status)" size="small">{{ taskStatusLabel(row.status) }}</el-tag>
              </dd>
            </dl>
          </div>
        </div>
        <div v-if="!detailData.tasks?.length" class="py-4 text-center text-sm text-zinc-400">{{ t('production.workOrders.noTasks') }}</div>

        <div class="mt-4 flex flex-wrap gap-2 justify-end">
          <el-button :loading="printingLabels" @click="printLabels">{{ t('production.workOrders.printAllLabels') }}</el-button>
          <el-button type="primary" :loading="printingLabels" @click="printLabelsRange">{{ t('production.workOrders.printRange') }}</el-button>
        </div>
      </div>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi, type WorkOrderDetailOut, type WorkOrderOut } from '@/api/production'
import { processRowLabel, skuRowLabel } from '@/utils/display'
import { openPrintWindow } from '@/utils/print'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const loading = ref(false)
const items = ref<WorkOrderOut[]>([])
const query = reactive({ order_id: null as number | null, status: '', offset: 0, limit: 50 })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const detailOpen = ref(false)
const detailLoading = ref(false)
const detailData = ref<WorkOrderDetailOut | null>(null)
const printingLabels = ref(false)
const exporting = ref(false)

const { label: statusLabel, type: statusTagType } = useStatus('work_order')

function taskStatusLabel(s: string | undefined) {
  if (s === 'pending') return '待开始'
  if (s === 'working') return '进行中'
  if (s === 'done') return '已完成'
  return s || '—'
}

function taskStatusType(s: string | undefined) {
  if (s === 'pending') return 'primary'
  if (s === 'working') return 'warning'
  if (s === 'done') return 'success'
  return 'info'
}

async function printLabels() {
  if (!detailData.value) return
  printingLabels.value = true
  try {
    const res = await productionApi.printProductLabels(detailData.value.id)
    if (!res.count) {
      ElMessage.warning('暂无成品码可打印，请先在首道工序完成派工（逐件模式会自动生成套号池）')
      return
    }
    openPrintWindow(res.html, { title: '产品追溯码打印', autoPrint: true })
  } finally {
    printingLabels.value = false
  }
}

async function printLabelsRange() {
  if (!detailData.value) return
  try {
    const { value } = await ElMessageBox.prompt('打印套号范围（留空=全部）', '打印成品溯源标签', {
      confirmButtonText: '打印',
      cancelButtonText: '取消',
      inputPlaceholder: '例如 1-45 或留空',
    })
    let piece_no_from: number | undefined
    let piece_no_to: number | undefined
    const raw = (value || '').trim()
    if (raw) {
      const m = raw.match(/^(\d+)\s*[-~]\s*(\d+)$/)
      if (m) {
        piece_no_from = Number(m[1])
        piece_no_to = Number(m[2])
      } else if (/^\d+$/.test(raw)) {
        piece_no_from = Number(raw)
        piece_no_to = Number(raw)
      }
    }
    printingLabels.value = true
    const res = await productionApi.printProductLabels(detailData.value.id, { piece_no_from, piece_no_to })
    if (!res.count) {
      ElMessage.warning('指定范围内没有可打印的成品码')
      return
    }
    openPrintWindow(res.html, { title: '产品追溯码打印', autoPrint: true })
  } catch {
    /* cancelled */
  } finally {
    printingLabels.value = false
  }
}

async function openDetail(id: number) {
  detailOpen.value = true
  detailLoading.value = true
  try {
    detailData.value = await productionApi.getWorkOrder(id)
  } finally {
    detailLoading.value = false
  }
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await productionApi.exportWorkOrders()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `work_orders_${new Date().toISOString().slice(0, 10)}.xlsx`
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
    const res = await productionApi.listWorkOrders({
      order_id: query.order_id || undefined,
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

onMounted(() => reload(true))
</script>
