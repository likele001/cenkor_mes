<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi, type ReportUnitDetailOut, type ReportUnitOut } from '@/api/production'
import { systemApi } from '@/api/system'
import { aiApi, type AuditSummaryOut } from '@/api/ai'
import { useAuthStore } from '@/stores/auth'
import AttachmentPreview, { type AttachmentMeta } from '@/components/AttachmentPreview.vue'
import CameraPhotoCapture from '@/components/CameraPhotoCapture.vue'
import CameraVideoCapture from '@/components/CameraVideoCapture.vue'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const route = useRoute()
const { label: statusLabel, type: statusTagType } = useStatus('report_unit')
const loading = ref(false)
const items = ref<ReportUnitOut[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const current = ref<ReportUnitDetailOut | null>(null)
const qcUploads = ref<{ id: number; name: string }[]>([])
const mediaCfg = ref({
  max_video_seconds: 15,
  max_video_mb: 8,
  max_video_count: 3,
})
const auth = useAuthStore()
const canAi = computed(() => auth.hasAnyPermission(['ai.use', 'report.audit']))
const aiSummaryLoading = ref(false)
const aiSummaryData = ref<AuditSummaryOut | null>(null)
const aiSummaryOpen = ref(false)
const visionLoading = ref(false)
const visionResult = ref('')

// 审批流步骤
const approvalSteps = ref<Array<{ step_order: number; approver_role: string; is_required: boolean; can_skip: boolean; label: string }>>([])
const approvalStepsLoaded = ref(false)

// 质检检查表
interface InspectionItem {
  id: number
  seq: number
  item_name: string
  item_type: string
  standard_value: string | null
  upper_limit: string | null
  lower_limit: string | null
  unit: string | null
  is_required: boolean
  remark: string | null
}
interface InspectionResult {
  template_item_id: number
  result: string
  measured_value: string | null
  defect_code_id: number | null
  remark: string | null
}
const inspectionItems = ref<InspectionItem[]>([])
const inspectionResults = ref<InspectionResult[]>([])
const defectCodes = ref<Array<{ id: number; code: string; name: string; severity: string }>>([])

const query = reactive({
  status: '',
  prescreen_level: '' as string,
  offset: 0,
  limit: 50,
})

const prescreenTagType: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  green: 'success',
  yellow: 'warning',
  red: 'danger',
}

const prescreenLabel: Record<string, string> = {
  green: t('production.reportUnits.lowRisk'),
  yellow: t('production.reportUnits.midRisk'),
  red: t('production.reportUnits.highRisk'),
}

function prescreenTag(level: string | null | undefined) {
  if (!level) return null
  return prescreenLabel[level] || level
}

function parseIds(raw: string | null | undefined): number[] {
  if (!raw) return []
  return raw
    .split(',')
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => Number.isFinite(n) && n > 0)
}

function employeeAttachments(): AttachmentMeta[] {
  const list = current.value?.employee_attachments
  if (list?.length) return list
  return parseIds(current.value?.employee_attachment_ids).map((id) => ({ id }))
}

function qcAttachments(): AttachmentMeta[] {
  const list = current.value?.qc_attachments
  if (list?.length) return list
  return parseIds(current.value?.qc_attachment_ids).map((id) => ({ id }))
}

function pendingQcAttachments(): AttachmentMeta[] {
  return qcUploads.value.map((u) => ({
    id: u.id,
    original_filename: u.name,
  }))
}

function listQueryParams() {
  const params: Record<string, unknown> = {
    offset: query.offset,
    limit: query.limit,
  }
  if (query.prescreen_level) params.prescreen_level = query.prescreen_level
  if (query.status) {
    params.status = query.status
  } else {
    // 默认只看待审，排除 draft 占位槽位
    params.pending_audit = true
  }
  return params
}

async function load() {
  loading.value = true
  try {
    const resp = await productionApi.listReportUnits(listQueryParams())
    items.value = resp.items || []
    total.value = (resp as { total?: number }).total ?? items.value.length
  } finally {
    loading.value = false
  }
}

async function loadApprovalSteps() {
  if (approvalStepsLoaded.value) return
  try {
    const res = await productionApi.getApprovalSteps()
    approvalSteps.value = res.steps || []
    approvalStepsLoaded.value = true
  } catch {
    // 默认 2 步
    approvalSteps.value = [
      { step_order: 1, approver_role: 'leader', is_required: true, can_skip: false, label: '班组长初审' },
      { step_order: 2, approver_role: 'qc', is_required: true, can_skip: false, label: 'QC 终审' },
    ]
    approvalStepsLoaded.value = true
  }
}

function getCurrentStepLabel(status: string): string {
  if (status === 'submitted') {
    const step = approvalSteps.value[0]
    return step ? `${stepButtonLabel(step, '初审')} (1/${approvalSteps.value.length})` : '初审'
  }
  if (status === 'leader_approved' || status.startsWith('step_')) {
    const auditCount = approvalSteps.value.length > 1 ? 1 : 0
    const step = approvalSteps.value[auditCount]
    if (step) return `${stepButtonLabel(step, '终审')} (${auditCount + 1}/${approvalSteps.value.length})`
    return '终审'
  }
  return ''
}

function isLastStepStatus(status: string): boolean {
  return status === 'leader_approved' || status.startsWith('step_')
}

function stepButtonLabel(step: { label: string; approver_role: string } | undefined, fallback: string): string {
  if (!step) return fallback
  const raw = (step.label || '').trim()
  // 用户在数据库里填了 label（且不是 fallback 出来的角色码），尊重填写
  if (raw && raw.toLowerCase() !== (step.approver_role || '').toLowerCase()) {
    return raw
  }
  // label 为空、或者等于 approver_role（后端 fallback 出来的），走 i18n 翻译
  const key = `production.reportUnits.auditRoles.${step.approver_role}`
  const translated = t(key)
  if (translated && translated !== key) return translated
  return step.approver_role || raw || fallback
}

async function viewDetail(id: number) {
  await loadApprovalSteps()
  try {
    current.value = await productionApi.getReportUnit(id)
    qcUploads.value = []
    inspectionItems.value = []
    inspectionResults.value = []

    // 如果待终审（最后一步），加载质检检查表
    const stepIndex = approvalSteps.value.length - 1
    const isLastStep = current.value?.status === 'leader_approved' || current.value?.status.startsWith('step_')
    if (isLastStep && current.value?.task?.process_id) {
      try {
        const tmpl = await productionApi.getInspectionForm(current.value.task.process_id)
        inspectionItems.value = tmpl.items || []
        inspectionResults.value = (tmpl.items || []).map((it) => ({
          template_item_id: it.id,
          result: 'pass',
          measured_value: null,
          defect_code_id: null,
          remark: null,
        }))
        if (inspectionItems.value.length) {
          const defs = await productionApi.listDefectCodes()
          defectCodes.value = defs.items || []
        }
      } catch {
        // 无模板不显示检查表
      }
    }

    dialogVisible.value = true
  } catch {
    ElMessage.error(t('production.reportUnits.detailFailed'))
  }
}

async function loadMediaConfig() {
  try {
    const cfg = await systemApi.getReportMediaSettings()
    mediaCfg.value = {
      max_video_seconds: cfg.max_video_seconds,
      max_video_mb: cfg.max_video_mb,
      max_video_count: cfg.max_video_count,
    }
  } catch {
    /* 默认 */
  }
}

async function handleApprove(row: ReportUnitOut) {
  await loadApprovalSteps()
  const auditCount = row.status === 'submitted' ? 0 : 1
  const isLastStep = auditCount >= approvalSteps.value.length - 1

  if (isLastStep) {
    if (!qcUploads.value.length) {
      ElMessage.warning('终审请至少上传1个审核图片或视频')
      return
    }
    const filledResults = inspectionResults.value.filter((r) => r.template_item_id > 0)
    await productionApi.approveReportUnit(row.id, {
      qc_attachment_ids: qcUploads.value.map((u) => u.id).join(','),
      inspection_results: filledResults.length ? filledResults : undefined,
    })
  } else {
    await productionApi.approveReportUnit(row.id)
  }

  const stepLabel = getCurrentStepLabel(row.status)
  ElMessage.success(stepLabel ? `${stepLabel} 通过` : '审核通过')
  dialogVisible.value = false
  load()
}

async function handleReject(row: ReportUnitOut) {
  const { value } = await ElMessageBox.prompt(t('production.reportUnits.rejectReasonTitle'), t('production.reportUnits.rejectTitle'), {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /\S/,
    inputErrorMessage: t('production.reportUnits.rejectReasonEmpty'),
  }).catch(() => null)
  if (!value) return
  await productionApi.rejectReportUnit(row.id, value)
  ElMessage.success(t('production.reportUnits.rejected'))
  dialogVisible.value = false
  load()
}

function resultLabel(val: string | null) {
  if (val === 'good') return t('production.reportUnits.goodResult')
  if (val === 'bad') return t('production.reportUnits.badResult')
  return '—'
}

async function fetchAuditSummary(openDialog = false) {
  aiSummaryLoading.value = true
  if (openDialog) {
    aiSummaryOpen.value = true
    aiSummaryData.value = null
  }
  try {
    aiSummaryData.value = await aiApi.auditSummary(query.status || 'submitted')
  } catch (e: unknown) {
    aiSummaryData.value = {
      anomaly_count: 0,
      ai_suggestions: [],
      conversation_id: 0,
      reply: '',
      summary: e instanceof Error ? e.message : 'AI 暂不可用',
      risk_points: [] as string[],
      suggest_actions: [] as string[],
      high_risk_ids: [] as number[],
    }
  } finally {
    aiSummaryLoading.value = false
  }
}

function runAuditSummary() {
  fetchAuditSummary(true)
}

async function runVisionAudit() {
  if (!current.value) return
  visionLoading.value = true
  visionResult.value = ''
  try {
    const res = await aiApi.reportVision(current.value.id)
    visionResult.value = String(res.summary || res.reply || JSON.stringify(res))
    ElMessage.success(t('production.reportUnits.visionComplete'))
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : t('production.reportUnits.visionFailed'))
  } finally {
    visionLoading.value = false
  }
}

onMounted(async () => {
  loadMediaConfig()
  load()
  loadApprovalSteps()
  if (canAi.value) fetchAuditSummary(false)
  // 深链直达：有 focus_id 就自动开 dialog
  const fid = route.query.focus_id
  if (fid) {
    const id = Number(fid)
    if (!Number.isNaN(id) && id > 0) {
      try {
        await viewDetail(id)
      } catch {
        /* viewDetail 内部已 ElMessage.error */
      }
    }
  }
})
</script>

<template>
  <AdminPage :title="t('production.reportUnits.title')">
    <el-alert
      class="mb-4"
      type="info"
      :closable="false"
      title="件次报工审核：员工照片/视频、审核证据均保存在服务器附件库（附件ID），页面上的 blob: 地址仅为临时预览，刷新后需重新加载。"
    />
    <el-card shadow="never" class="mb-4">
      <el-form :model="query" inline>
        <el-form-item :label="t('production.common.status')">
          <el-select v-model="query.status" clearable placeholder="待审（默认）" @change="load">
            <el-option label="待审（全部）" value="" />
            <el-option label="待初审" value="submitted" />
            <el-option v-for="(step, idx) in approvalSteps.slice(1)" :key="step.step_order" :label="`待${step.label}`" :value="idx === 0 ? 'leader_approved' : `step_${step.step_order - 1}_approved`" />
            <el-option label="已通过" value="qc_approved" />
            <el-option label="已驳回" value="rejected" />
            <el-option label="待报（未报工槽位）" value="draft" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('production.reportUnits.prescreenLevel')">
          <el-select v-model="query.prescreen_level" clearable placeholder="全部" @change="load">
            <el-option label="低风险" value="green" />
            <el-option label="中风险" value="yellow" />
            <el-option label="高风险" value="red" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">{{ t('production.common.search') }}</el-button>
          <el-button v-if="canAi" type="warning" plain :loading="aiSummaryLoading" @click="runAuditSummary">{{ t('production.reportUnits.aiBatchSummary') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert
      v-if="canAi && aiSummaryData?.summary"
      class="mb-4"
      type="info"
      :closable="true"
      :title="`待审 AI 摘要${aiSummaryData.pending_count != null ? `（${aiSummaryData.pending_count} 条）` : ''}`"
    >
      <p class="text-sm whitespace-pre-wrap m-0">{{ aiSummaryData.summary }}</p>
      <el-button class="mt-2" size="small" link type="primary" @click="runAuditSummary">查看详情</el-button>
    </el-alert>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="items" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="订单号" width="150">
          <template #default="{ row }">
            <span class="font-mono text-xs">{{ row.order?.code || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="产品" width="100">
          <template #default="{ row }">{{ row.product?.name || '—' }}</template>
        </el-table-column>
        <el-table-column label="型号" width="80">
          <template #default="{ row }">
            <span class="text-xs text-zinc-500">{{ row.product?.code || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="工序" width="90">
          <template #default="{ row }">{{ row.task?.process_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="任务" width="130">
          <template #default="{ row }">
            <span class="font-mono text-xs">{{ row.task?.task_code || row.task_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="员工" width="90">
          <template #default="{ row }">{{ row.report_user?.full_name || row.user_id }}</template>
        </el-table-column>
        <el-table-column prop="unit_seq" label="件次" width="60" />
        <el-table-column label="结果" width="70">
          <template #default="{ row }">{{ resultLabel(row.result_type) }}</template>
        </el-table-column>
        <el-table-column :label="t('production.common.status')" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status) || 'info'" size="small">{{ statusLabel(row.status) || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预筛" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.prescreen_level" :type="prescreenTagType[row.prescreen_level] || 'info'" size="small">
              {{ prescreenTag(row.prescreen_level) }}
            </el-tag>
            <span v-else class="text-zinc-400 text-xs">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="submitted_at" label="提交时间" width="150" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row.id)">{{ t('production.common.detail') }}</el-button>
            <el-button
              v-if="row.status === 'submitted' || row.status === 'leader_approved' || row.status.startsWith('step_')"
              size="small"
              :type="row.status === 'submitted' ? 'primary' : 'success'"
              @click="row.status === 'submitted' ? handleApprove(row) : viewDetail(row.id)"
            >
              {{ row.status === 'submitted' ? stepButtonLabel(approvalSteps[0], '初审') : stepButtonLabel(approvalSteps[approvalSteps.length - 1], '终审') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <template #extra>
    <el-dialog v-model="dialogVisible" :title="t('production.reportUnits.detailTitle')" width="720px" destroy-on-close>
      <template v-if="current">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="件次">第 {{ current.unit_seq }} 件</el-descriptions-item>
          <el-descriptions-item label="结果">{{ resultLabel(current.result_type) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.common.status')">{{ statusLabel(current.status) }}</el-descriptions-item>
          <el-descriptions-item label="员工">{{ current.report_user?.full_name }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ current.remark || '无' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="mt-4 mb-2 font-medium">{{ t('production.reportUnits.employeeEvidence') }}</h4>
        <div v-if="canAi && employeeAttachments().length" class="mb-2">
          <el-button size="small" type="warning" plain :loading="visionLoading" @click="runVisionAudit">{{ t('production.reportUnits.visionAssist') }}</el-button>
          <p v-if="visionResult" class="mt-2 text-xs text-zinc-600 whitespace-pre-wrap">{{ visionResult }}</p>
        </div>
        <div v-if="employeeAttachments().length" class="flex flex-wrap gap-3">
          <AttachmentPreview
            v-for="a in employeeAttachments()"
            :key="'e' + a.id"
            :attachment="a"
          />
        </div>
        <span v-else class="text-zinc-400 text-sm">{{ t('production.reportUnits.noEvidence') }}</span>

        <h4 v-if="isLastStepStatus(current.status)" class="mt-4 mb-2 font-medium">{{ t('production.reportUnits.finalReviewEvidence') }}</h4>
        <div v-if="isLastStepStatus(current.status)" class="space-y-3">
          <CameraPhotoCapture v-model="qcUploads" :max-count="5" label="拍摄审核照片" />
          <CameraVideoCapture
            v-model="qcUploads"
            :max-seconds="mediaCfg.max_video_seconds"
            :max-mb="mediaCfg.max_video_mb"
            :max-count="mediaCfg.max_video_count"
          />
          <div v-if="pendingQcAttachments().length" class="flex flex-wrap gap-3">
            <p class="w-full text-xs text-zinc-500">待提交预览（终审通过后将写入附件库）：</p>
            <AttachmentPreview
              v-for="a in pendingQcAttachments()"
              :key="'p' + a.id"
              :attachment="a"
            />
          </div>
          <!-- 质检检查表 -->
          <div v-if="inspectionItems.length" class="border rounded p-3">
            <h5 class="font-medium text-sm mb-3">📋 质检检查表</h5>
            <div v-for="(it, idx) in inspectionItems" :key="it.id" class="flex items-center gap-2 mb-2 pb-2 border-b last:border-0">
              <span class="text-sm min-w-[140px]">{{ it.item_name }}</span>

              <!-- pass_fail -->
              <template v-if="it.item_type === 'pass_fail'">
                <el-select v-model="inspectionResults[idx].result" size="small" style="width:100px">
                  <el-option label="合格" value="pass" />
                  <el-option label="不合格" value="fail" />
                  <el-option label="不适用" value="na" />
                </el-select>
              </template>

              <!-- measure -->
              <template v-else-if="it.item_type === 'measure'">
                <el-input v-model="inspectionResults[idx].measured_value" size="small" style="width:100px"
                  :placeholder="`标准${it.standard_value || ''}${it.unit || ''}`" />
                <span v-if="it.unit" class="text-xs text-zinc-500">{{ it.unit }}</span>
                <span v-if="(it.upper_limit || it.lower_limit)" class="text-xs text-zinc-400">
                  ({{ it.lower_limit || '—' }} ~ {{ it.upper_limit || '—' }})
                </span>
              </template>

              <!-- text -->
              <template v-else>
                <el-input v-model="inspectionResults[idx].remark" size="small" style="width:200px" placeholder="填写描述" />
              </template>

              <!-- 缺陷代码（仅 fail 时显示） -->
              <template v-if="inspectionResults[idx].result === 'fail' && defectCodes.length">
                <el-select v-model="inspectionResults[idx].defect_code_id" size="small" style="width:130px" placeholder="缺陷" clearable>
                  <el-option v-for="d in defectCodes" :key="d.id"
                    :label="`${d.code} ${d.name}`"
                    :value="d.id">
                    <span>{{ d.code }}</span>
                    <span class="ml-1 text-xs text-zinc-400">{{ d.name }}</span>
                  </el-option>
                </el-select>
              </template>

              <el-tag v-if="inspectionResults[idx].result === 'fail'" size="small" type="danger">{{ t('production.reportUnits.failResult') }}</el-tag>
            </div>
          </div>

          <el-button type="success" @click="handleApprove(current)">{{ getCurrentStepLabel(current.status) || '审核通过' }}</el-button>
          <el-button type="danger" @click="handleReject(current)">{{ t('production.reportUnits.reject') }}</el-button>
        </div>

        <div v-if="current.status === 'submitted'" class="mt-4 flex gap-2">
          <el-button type="primary" @click="handleApprove(current)">{{ getCurrentStepLabel(current.status) || '初审' }}</el-button>
          <el-button type="danger" @click="handleReject(current)">{{ t('production.reportUnits.reject') }}</el-button>
        </div>

        <template v-if="qcAttachments().length">
          <h4 class="mt-4 mb-2 font-medium">审核证据（已存档，附件 ID：{{ current.qc_attachment_ids }}）</h4>
          <div class="flex flex-wrap gap-3">
            <AttachmentPreview
              v-for="a in qcAttachments()"
              :key="'q' + a.id"
              :attachment="a"
            />
          </div>
        </template>
        <p v-else-if="current.status === 'qc_approved'" class="mt-4 text-sm text-amber-600">
          已通过但未找到审核附件记录，请联系管理员检查终审时是否上传成功。
        </p>
      </template>
    </el-dialog>

    <el-dialog v-model="aiSummaryOpen" title="待审 AI 批量摘要" width="560px">
      <div v-loading="aiSummaryLoading" class="text-sm text-zinc-700 space-y-3">
        <template v-if="aiSummaryData">
          <p v-if="aiSummaryData.pending_count != null" class="text-xs text-zinc-500">
            待审 {{ aiSummaryData.pending_count }} 条
          </p>
          <p v-if="aiSummaryData.summary" class="whitespace-pre-wrap">{{ aiSummaryData.summary }}</p>
          <div v-if="aiSummaryData.high_risk_ids?.length">
            <p class="font-medium text-amber-700">高风险件次 ID</p>
            <p>{{ aiSummaryData.high_risk_ids.join(', ') }}</p>
          </div>
          <div v-if="aiSummaryData.risk_points?.length">
            <p class="font-medium">风险点</p>
            <ul class="list-disc pl-5">
              <li v-for="(p, i) in aiSummaryData.risk_points" :key="'r' + i">{{ p }}</li>
            </ul>
          </div>
          <div v-if="aiSummaryData.suggest_actions?.length">
            <p class="font-medium">建议动作</p>
            <ul class="list-disc pl-5">
              <li v-for="(a, i) in aiSummaryData.suggest_actions" :key="'a' + i">{{ a }}</li>
            </ul>
          </div>
        </template>
        <p v-else-if="!aiSummaryLoading">生成中…</p>
      </div>
    </el-dialog>
    </template>
  </AdminPage>
</template>
