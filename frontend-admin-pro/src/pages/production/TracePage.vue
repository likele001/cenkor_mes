<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/utils/http'
import { openPrintWindow } from '@/utils/print'
import { productionApi } from '@/api/production'

interface TraceRecord {
  id: number
  code: string
  product_code?: string | null
  order_id: number
  sku_id: number
  process_id: number
  report_id: number
  user_id: number
  qty: number
  remark: string | null
  created_at: string
}

interface FlowChainItem {
  product_code: string | null
  trace_code: string
  task_seq: number | null
  process_id: number
  process_name: string | null
  user_full_name: string | null
  username: string | null
  parent_trace_code: string | null
  created_at: string
}

interface TraceChain {
  trace_code: string
  product_code: string | null
  public_trace_url?: string | null
  piece_no: number | null
  work_order_id: number | null
  flow_chain: FlowChainItem[]
  qty: number
  remark: string | null
  created_at: string
  order: { id: number; code: string; status: string } | null
  sku: { id: number; code: string; name: string; display_label?: string } | null
  process: { id: number; code: string; name: string } | null
  report: { id: number; good_qty: number; bad_qty: number; status: string; created_at: string } | null
  report_user: { id: number; full_name: string; username: string } | null
  audits: { audit_level: string; action: string; reason: string | null; created_at: string }[]
  salary: { id: number; amount: number; unit_price: number; good_qty: number; month: string } | null
  qr?: { code: string; text: string; trace_url: string; svg: string }
  media?: { id: number; kind: string; content_type: string; original_filename: string; url?: string | null }[]
}

const { t } = useI18n()
const route = useRoute()
const loading = ref(false)
const records = ref<TraceRecord[]>([])
const query = reactive({ order_id: undefined as number | undefined, offset: 0, limit: 50 })

const searchCode = ref('')
const chainResult = ref<TraceChain | null>(null)
const chainLoading = ref(false)
const showQrDialog = ref(false)
const showPrintDialog = ref(false)
const printingLabel = ref(false)
const printMode = ref<'current' | 'all' | 'range'>('current')
const printPieceFrom = ref(1)
const printPieceTo = ref(1)

const qrDataUrl = computed(() => {
  const svg = chainResult.value?.qr?.svg
  if (!svg) return ''
  const encoded = encodeURIComponent(svg)
  return `data:image/svg+xml;charset=utf-8,${encoded}`
})

function openPrintDialog() {
  const chain = chainResult.value
  if (!chain?.work_order_id) return
  const pn = chain.piece_no || 1
  printMode.value = 'current'
  printPieceFrom.value = pn
  printPieceTo.value = pn
  showPrintDialog.value = true
}

function previewMedia(m: { kind: string; url?: string | null }) {
  if (m.url) window.open(m.url, '_blank')
}

async function handlePrintLabel() {
  const woId = chainResult.value?.work_order_id
  if (!woId) return
  printingLabel.value = true
  try {
    const params: { piece_no_from?: number; piece_no_to?: number } = {}
    if (printMode.value === 'current') {
      const pn = chainResult.value?.piece_no || 1
      params.piece_no_from = pn
      params.piece_no_to = pn
    } else if (printMode.value === 'range') {
      params.piece_no_from = printPieceFrom.value
      params.piece_no_to = printPieceTo.value
    }
    const res = await productionApi.printProductLabels(woId, params)
    if (res?.html) {
      openPrintWindow(res.html, { title: `product_label_wo${woId}`, autoPrint: true })
    }
    showPrintDialog.value = false
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '打印失败')
  } finally {
    printingLabel.value = false
  }
}

async function loadRecords() {
  loading.value = true
  try {
    const resp = await http.request<any>({ url: '/admin/trace', method: 'GET', params: query })
    records.value = resp?.items ?? []
  } finally {
    loading.value = false
  }
}

async function searchTrace(code?: string | Event) {
  const q = (typeof code === 'string' ? code : searchCode.value).trim()
  if (!q) return
  chainLoading.value = true
  chainResult.value = null
  try {
    chainResult.value = await http.request<TraceChain>({ url: `/admin/trace/${encodeURIComponent(q)}`, method: 'GET' })
  } catch (e: unknown) {
    chainResult.value = null
    ElMessage.error((e as Error).message || '查询失败')
  } finally {
    chainLoading.value = false
  }
}

onMounted(() => {
  loadRecords()
  const q = route.query.id || route.query.code
  if (typeof q === 'string' && q.trim()) {
    searchCode.value = q.trim()
    searchTrace(q.trim())
  }
})
</script>


<template>
  <AdminPage :title="t('production.trace.title') + (chainResult ? ': ' + (chainResult.product_code || chainResult.trace_code) : '')">
    <!-- 扫码查询 -->
    <el-card shadow="never" class="mb-4">
      <el-form inline>
        <el-form-item :label="t('production.trace.成品码Label')">
          <el-input v-model="searchCode" :placeholder="t('production.trace.searchPlaceholder')" style="width: 260px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="chainLoading" @click="searchTrace">{{ t('production.trace.search') }}</el-button>
        </el-form-item>
      </el-form>

      <!-- 溯源结果 -->
      <el-card v-if="chainResult" shadow="never" class="mb-4">
        <template #header>
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <span class="font-medium">成品码：{{ chainResult.product_code || chainResult.trace_code }}</span>
            <div class="flex items-center gap-2 flex-wrap">
              <el-button
                v-if="chainResult.public_trace_url"
                type="primary"
                link
                tag="a"
                :href="chainResult.public_trace_url"
                target="_blank"
              >
                打开客户溯源页
              </el-button>
              <el-button
                v-if="chainResult.qr?.svg"
                type="default"
                size="small"
                @click="showQrDialog = true"
              >
                二维码
              </el-button>
              <el-button
                v-if="chainResult.work_order_id"
                type="default"
                size="small"
                @click="openPrintDialog"
              >
                打印标签
              </el-button>
            </div>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="数量">{{ chainResult.qty }}</el-descriptions-item>
          <el-descriptions-item label="生成时间">{{ chainResult.created_at }}</el-descriptions-item>
          <el-descriptions-item v-if="chainResult.order" :label="t('production.trace.order')" :span="2">
            #{{ chainResult.order.id }} {{ chainResult.order.code }} ({{ chainResult.order.status }})
          </el-descriptions-item>
          <el-descriptions-item v-if="chainResult.sku" :label="t('production.trace.sku')" :span="2">
            {{ chainResult.sku.display_label || chainResult.sku.name }}
          </el-descriptions-item>
          <el-descriptions-item v-if="chainResult.piece_no" label="工单件次">
            第 {{ chainResult.piece_no }} 件（全工序同一物理件）
          </el-descriptions-item>
          <el-descriptions-item v-if="chainResult.process" label="当前工序">
            {{ chainResult.process.name }}
          </el-descriptions-item>
          <el-descriptions-item v-if="chainResult.report" label="报工状态">
            <el-tag v-if="chainResult.report.status === 'qc_approved'" type="success">{{ t('production.trace.passed') }}</el-tag>
            <el-tag v-else>{{ chainResult.report.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="chainResult.report" label="合格数">{{ chainResult.report.good_qty }}</el-descriptions-item>
          <el-descriptions-item v-if="chainResult.report" label="不良数">{{ chainResult.report.bad_qty }}</el-descriptions-item>
          <el-descriptions-item v-if="chainResult.report_user" label="报工人" :span="2">
            {{ chainResult.report_user.full_name || chainResult.report_user.username }}
          </el-descriptions-item>
          <el-descriptions-item v-if="chainResult.salary" label="计件工资">
            ¥{{ chainResult.salary.amount.toFixed(2) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="chainResult.salary" label="单价">
            ¥{{ chainResult.salary.unit_price.toFixed(4) }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 工序流转链 -->
        <h4 v-if="chainResult.flow_chain?.length" class="mt-4 mb-2 font-medium">{{ t('production.trace.processFlow') }}</h4>
        <el-timeline v-if="chainResult.flow_chain?.length" class="mb-4">
          <el-timeline-item
            v-for="(step, idx) in chainResult.flow_chain"
            :key="idx"
            :timestamp="String(step.created_at).slice(0, 19)"
            :type="(step.product_code || step.trace_code) === (chainResult.product_code || chainResult.trace_code) && step.process_id === chainResult.process?.id ? 'primary' : undefined"
          >
            <div class="font-medium">{{ step.process_name }}</div>
            <div class="text-xs text-zinc-500 font-mono">{{ step.product_code || step.trace_code }}</div>
            <div class="text-xs">{{ step.user_full_name || step.username || '—' }}</div>
          </el-timeline-item>
        </el-timeline>

        <!-- 审核流水 -->
        <h4 class="mt-4 mb-2 font-medium">{{ t('production.trace.auditFlow') }}</h4>
        <template v-if="chainResult.audits?.length">
          <el-table class="hidden lg:block w-full" :data="chainResult.audits" size="small" stripe>
            <el-table-column prop="audit_level" :label="t('production.trace.auditLevel')" width="80">
              <template #default="{ row }">{{ row.audit_level === 'leader' ? '班组长' : '质检' }}</template>
            </el-table-column>
            <el-table-column prop="action" :label="t('production.trace.operationLabel')" width="80">
              <template #default="{ row }">
                <el-tag :type="row.action === 'approve' ? 'success' : 'danger'" size="small">
                  {{ row.action === 'approve' ? '通过' : '驳回' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reason" :label="t('production.trace.auditReason')" />
            <el-table-column prop="created_at" :label="t('production.trace.auditTime')" width="160" />
          </el-table>
          <div class="lg:hidden space-y-2">
            <div v-for="(row, idx) in chainResult.audits" :key="idx" class="admin-mobile-row">
              <div class="admin-mobile-row__head">
                <span class="text-xs text-el-placeholder">{{ row.created_at }}</span>
                <div class="flex gap-2">
                  <el-tag size="small">{{ row.audit_level === 'leader' ? '班组长' : '质检' }}</el-tag>
                  <el-tag :type="row.action === 'approve' ? 'success' : 'danger'" size="small">
                    {{ row.action === 'approve' ? '通过' : '驳回' }}
                  </el-tag>
                </div>
              </div>
              <p v-if="row.reason" class="text-sm text-el-regular m-0">原因：{{ row.reason }}</p>
            </div>
          </div>
        </template>
        <el-empty v-else description="暂无审核记录" />

        <!-- 报工/质检影像 -->
        <h4 v-if="chainResult.media?.length" class="mt-4 mb-2 font-medium">质检影像</h4>
        <div v-if="chainResult.media?.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 mt-2">
          <div v-for="m in chainResult.media" :key="m.id" class="border rounded-lg overflow-hidden">
            <img v-if="m.kind === 'image'" :src="m.url || ''" class="w-full aspect-square object-cover cursor-pointer" @click="previewMedia(m)" alt="" />
            <video v-else :src="m.url || ''" class="w-full aspect-square object-cover" controls />
          </div>
        </div>
      </el-card>
    </el-card>

    <!-- 追溯码列表 -->
    <el-card shadow="never">
      <template #header><span class="font-medium">{{ t('production.trace.traceListTitle') }}</span></template>
      <div v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="records" stripe style="width: 100%">
          <el-table-column :label="t('production.trace.traceCodeLabel')" width="200">
            <template #default="{ row }">
              <span class="font-mono text-sm">{{ row.product_code || row.code }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="order_id" :label="t('production.trace.order')" width="60" />
          <el-table-column prop="sku_id" :label="t('production.trace.sku')" width="60" />
          <el-table-column prop="process_id" :label="t('production.trace.processIdLabel')" width="60" />
          <el-table-column prop="report_id" :label="t('production.trace.reportIdLabel')" width="60" />
          <el-table-column prop="qty" :label="t('production.trace.qtyLabel')" width="60" />
          <el-table-column prop="remark" :label="t('production.trace.remarkLabel')" min-width="120" />
          <el-table-column prop="created_at" :label="t('production.trace.createTime')" width="160" />
          <el-table-column :label="t('production.trace.operationLabel')" width="80">
            <template #default="{ row }">
              <el-button size="small" @click="searchCode = row.code; searchTrace()">{{ t('production.trace.view') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="lg:hidden space-y-3">
          <div v-for="row in records" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-mono text-sm font-semibold text-el-primary break-all">{{ row.code }}</div>
                <div class="text-xs text-el-placeholder">{{ row.created_at }}</div>
              </div>
            </div>
            <dl class="admin-mobile-kv">
              <dt>订单</dt>
              <dd>{{ row.order_id }}</dd>
              <dt>型号</dt>
              <dd>{{ row.sku_id }}</dd>
              <dt>工序</dt>
              <dd>{{ row.process_id }}</dd>
              <dt>报工</dt>
              <dd>{{ row.report_id }}</dd>
              <dt>{{ t('production.trace.quantity') }}</dt>
              <dd>{{ row.qty }}</dd>
              <dt>备注</dt>
              <dd class="text-left">{{ row.remark || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="searchCode = row.code; searchTrace()">{{ t('production.trace.viewTrace') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !records.length" description="暂无追溯码" />
        </div>
      </div>
    </el-card>
  </AdminPage>

  <!-- 追溯码二维码弹窗 -->
  <el-dialog v-model="showQrDialog" title="追溯码二维码" width="360px" align-center>
    <div v-if="chainResult?.qr" class="flex flex-col items-center gap-3 py-4">
      <img :src="qrDataUrl" alt="QR Code" class="w-48 h-48" />
      <div class="font-mono text-sm text-zinc-500 break-all text-center">{{ chainResult.qr.code }}</div>
      <div class="text-xs text-zinc-400 break-all text-center">{{ chainResult.qr.text }}</div>
    </div>
  </el-dialog>

  <!-- 打印标签选择弹窗 -->
  <el-dialog v-model="showPrintDialog" title="打印标签" width="420px">
    <el-form label-width="80px">
      <el-form-item label="工单">
        <span>WO#{{ chainResult?.work_order_id }}</span>
        <span class="text-zinc-400 ml-2">· {{ chainResult?.product_code || chainResult?.trace_code }}</span>
      </el-form-item>
      <el-form-item label="打印方式">
        <el-radio-group v-model="printMode" class="flex flex-col items-start gap-2">
          <el-radio value="current">
            <div>
              <div>仅当前件</div>
              <div class="text-xs text-zinc-400">只打印第 {{ chainResult?.piece_no || 1 }} 件的标签</div>
            </div>
          </el-radio>
          <el-radio value="all">
            <div>
              <div>全部件</div>
              <div class="text-xs text-zinc-400">打印该工单全部产品的标签</div>
            </div>
          </el-radio>
          <el-radio value="range">
            <div>
              <div>自定义件号范围</div>
              <div class="text-xs text-zinc-400">指定起止套号，仅打印范围内的标签</div>
            </div>
          </el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="printMode === 'range'" label="件号范围">
        <div class="flex items-center gap-2">
          <el-input-number v-model="printPieceFrom" :min="1" style="width:120px" />
          <span>至</span>
          <el-input-number v-model="printPieceTo" :min="printPieceFrom" style="width:120px" />
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showPrintDialog = false">取消</el-button>
      <el-button type="primary" :loading="printingLabel" @click="handlePrintLabel">确认打印</el-button>
    </template>
  </el-dialog>
</template>
