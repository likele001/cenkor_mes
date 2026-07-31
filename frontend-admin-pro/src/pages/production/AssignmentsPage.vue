<template>
  <AdminPage :title="t('production.assignments.title')" description="按「员工 × 工序任务」展示；二维码对应该任务码，员工 H5 扫码报工">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-input v-model="query.keyword" :placeholder="t('production.assignments.searchPlaceholder')" clearable style="width: 200px" @keyup.enter="reload(true)" />
          <el-input-number v-model="query.order_id" :min="1" :controls="false" :placeholder="t('production.assignments.orderId')" style="width: 120px" />
          <el-input-number v-model="query.user_id" :min="1" :controls="false" :placeholder="t('production.assignments.userId')" style="width: 120px" />
          <el-button @click="reload(true)">{{ t('production.common.refresh') }}</el-button>
          <el-button type="primary" @click="router.push('/production/tasks')">{{ t('production.assignments.goToTaskList') }}</el-button>
        </div>
    </template>

    <div class="mt-4" v-loading="loading">
        <el-table class="w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="72" />
          <el-table-column prop="order_code" label="订单号" min-width="150" show-overflow-tooltip />
          <el-table-column label="产品名称" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.product_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="型号名称" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.display_label || row.sku_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="工序名称" min-width="100">
            <template #default="{ row }">{{ row.process_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="员工" min-width="120">
            <template #default="{ row }">
              <div class="font-medium">{{ row.user_full_name || row.username }}</div>
              <div class="text-xs text-zinc-400">{{ row.username }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="assigned_qty" label="分配数量" width="90" align="center" />
          <el-table-column prop="reported_qty" label="已报数量" width="90" align="center" />
          <el-table-column prop="remaining_qty" label="待报数量" width="90" align="center" />
          <el-table-column label="进度" width="100">
            <template #default="{ row }">
              <el-progress :percentage="row.progress" :stroke-width="8" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="分配时间" width="170">
            <template #default="{ row }">{{ formatTime(row.assigned_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="320">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="showQr(row)">{{ t('production.assignments.generateQr') }}</el-button>
              <el-button size="small" type="primary" @click="downloadQr(row)">{{ t('production.assignments.downloadQr') }}</el-button>
              <el-button size="small" type="warning" @click="printLabel(row)">{{ t('production.assignments.printLabel') }}</el-button>
              <el-button size="small" type="danger" @click="onDelete(row)">{{ t('production.assignments.deleteBtn') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="query.limit"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>

    <template #extra>
      <el-dialog v-model="qrDlg.open" :title="t('production.assignments.qrTitle')" width="420px" destroy-on-close @closed="resetQrDlg">
            <div v-if="qrDlg.imgSrc" class="text-center">
              <div class="text-sm text-zinc-600 mb-2">
                员工：{{ qrDlg.userLabel }} · 任务码 <span class="font-mono">{{ qrDlg.taskCode }}</span>
              </div>
              <img :src="qrDlg.imgSrc" alt="报工二维码" class="w-52 h-52 mx-auto block border border-zinc-100 rounded" />
              <div v-if="qrDlg.reportUrl" class="text-xs text-zinc-400 mt-2 break-all px-2">{{ qrDlg.reportUrl }}</div>
              <div class="text-xs text-zinc-500 mt-3">可打印贴工位，或让员工在 H5「我的任务」中查看</div>
            </div>
            <template #footer>
              <el-button @click="qrDlg.open = false">{{ t('production.assignments.close') }}</el-button>
              <el-button type="primary" @click="downloadQrFromDlg">{{ t('production.assignments.downloadPng') }}</el-button>
              <el-button @click="downloadSvgFromDlg">{{ t('production.assignments.downloadSvg') }}</el-button>
              <el-button type="warning" @click="printLabelFromDlg">{{ t('production.assignments.printLabel') }}</el-button>
            </template>
          </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi, type DispatchAssignmentOut } from '@/api/production'
import { openPrintWindow } from '@/utils/print'
import { downloadSvgAsPng, downloadSvgFile, svgToDataUrl } from '@/utils/qr'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const { label: statusLabel, type: statusTagType } = useStatus('assignment')
const router = useRouter()
const loading = ref(false)
const items = ref<DispatchAssignmentOut[]>([])
const total = ref(0)
const query = reactive({
  keyword: '',
  order_id: null as number | null,
  user_id: null as number | null,
  offset: 0,
  limit: 50,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)

const qrDlg = reactive({
  open: false,
  svg: '',
  imgSrc: '',
  reportUrl: '',
  taskCode: '',
  taskId: 0,
  userLabel: '',
})

function resetQrDlg() {
  qrDlg.svg = ''
  qrDlg.imgSrc = ''
  qrDlg.reportUrl = ''
}

function formatTime(t: string) {
  return t ? t.slice(0, 16).replace('T', ' ') : '—'
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await productionApi.listDispatchAssignments({
      keyword: query.keyword || undefined,
      order_id: query.order_id || undefined,
      user_id: query.user_id || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

async function showQr(row: DispatchAssignmentOut) {
  const data = await productionApi.getDispatchAssignmentQr(row.id)
  qrDlg.svg = data.svg || ''
  qrDlg.imgSrc = svgToDataUrl(qrDlg.svg)
  qrDlg.reportUrl = data.report_url || data.text || ''
  qrDlg.taskCode = data.task_code
  qrDlg.taskId = row.task_id
  qrDlg.userLabel = row.user_full_name || row.username || String(row.user_id)
  qrDlg.open = true
}

async function downloadQr(row: DispatchAssignmentOut) {
  const data = await productionApi.getDispatchAssignmentQr(row.id)
  await downloadSvgAsPng(data.svg, `task_${row.task_code}_${row.username}.png`)
  ElMessage.success(t('production.assignments.downloadPngSuccess'))
}

async function downloadQrFromDlg() {
  if (!qrDlg.svg) return
  await downloadSvgAsPng(qrDlg.svg, `task_${qrDlg.taskCode}.png`)
  ElMessage.success(t('production.assignments.downloadSuccess'))
}

function downloadSvgFromDlg() {
  if (!qrDlg.svg) return
  downloadSvgFile(qrDlg.svg, `task_${qrDlg.taskCode}.svg`)
}

async function printLabel(row: DispatchAssignmentOut) {
  const resp = await productionApi.renderTaskLabel(row.task_id, { template_code: 'task_label' })
  if (resp?.html) openPrintWindow(resp.html, { title: `task_${row.task_code}`, autoPrint: true })
}

function printLabelFromDlg() {
  if (qrDlg.taskId) printLabel({ task_id: qrDlg.taskId, task_code: qrDlg.taskCode } as DispatchAssignmentOut)
}

async function onDelete(row: DispatchAssignmentOut) {
  const ok = await ElMessageBox.confirm(
    `确认删除「${row.user_full_name || row.username}」在该工序的派工？`,
    '删除派工',
    { type: 'warning' },
  )
    .then(() => true)
    .catch(() => false)
  if (!ok) return
  await productionApi.deleteDispatchAssignment(row.id)
  ElMessage.success(t('production.assignments.deletedSuccess'))
  await reload(false)
}

onMounted(() => reload(true))
</script>
