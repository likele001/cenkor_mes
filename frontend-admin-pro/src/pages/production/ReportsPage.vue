<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi, type ReportOut } from '@/api/production'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const route = useRoute()
const { label: statusLabel, type: statusTagType } = useStatus('report')
const loading = ref(false)
const exporting = ref(false)
const reports = ref<ReportOut[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const currentReport = ref<any>(null)

const query = reactive({
  status: '',
  offset: 0,
  limit: 50,
})

function listQueryParams() {
  const params: Record<string, unknown> = {
    offset: query.offset,
    limit: query.limit,
  }
  if (query.status) {
    params.status = query.status
  } else {
    params.pending_audit = true
  }
  return params
}

async function load() {
  loading.value = true
  try {
    const resp = await productionApi.listReports(listQueryParams()) as any
    if (resp?.items) {
      reports.value = resp.items
      total.value = resp.total ?? resp.items.length
    } else if (Array.isArray(resp)) {
      reports.value = resp
      total.value = resp.length
    } else {
      reports.value = []
      total.value = 0
    }
  } finally {
    loading.value = false
  }
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await productionApi.exportReportUnits(listQueryParams())
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `reports_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

async function viewDetail(id: number) {
  try {
    currentReport.value = await productionApi.getReport(id)
    dialogVisible.value = true
  } catch {
    ElMessage.error(t('production.reports.detailFailed'))
  }
}

async function handleApprove(report: ReportOut, level: 'leader' | 'qc') {
  try {
    if (level === 'leader') {
      await productionApi.leaderApprove(report.id)
    } else {
      await productionApi.qcApprove(report.id)
    }
    ElMessage.success(t('production.reports.approveSuccess'))
    dialogVisible.value = false
    load()
  } catch {
    // handled by interceptor
  }
}

async function handleReject(report: ReportOut) {
  try {
    const { value } = await ElMessageBox.prompt(t('production.reports.rejectReasonTitle'), t('production.reports.rejectReport'), {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /\S/,
      inputErrorMessage: t('production.reports.rejectReasonEmpty'),
    })
    await productionApi.rejectReport(report.id, value)
    ElMessage.success(t('production.reports.rejected'))
    dialogVisible.value = false
    load()
  } catch {
    // cancelled or error
  }
}

onMounted(async () => {
  await load()
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
  <AdminPage :title="t('production.reports.title')">
    <el-alert class="mb-4" type="warning" :closable="false" title="此为旧版批量报工记录（按数量填报），新派工请使用「件次报工审核」。" />
    <!-- 筛选 -->
    <el-card shadow="never" class="mb-4">
      <el-form :model="query" inline>
        <el-form-item :label="t('production.common.status')">
          <el-select v-model="query.status" clearable placeholder="待审（默认）" @change="load">
            <el-option label="待审（初审+终审）" value="" />
            <el-option label="待初审" value="submitted" />
            <el-option label="待终审" value="leader_approved" />
            <el-option label="已通过" value="qc_approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">{{ t('production.common.search') }}</el-button>
          <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never">
      <div v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="reports" stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column label="报工人" width="130">
            <template #default="{ row }">
              <span v-if="row.report_user">{{ row.report_user.full_name }}</span>
              <span v-else>{{ row.report_user_id ? `用户#${row.report_user_id}` : '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="任务" min-width="180">
            <template #default="{ row }">
              <span v-if="row.task" class="font-mono text-xs">{{ row.task.task_code }}</span>
              <span v-else>任务#{{ row.task_id }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="good_qty" label="合格数" width="70" />
          <el-table-column prop="bad_qty" label="不良数" width="70" />
          <el-table-column prop="status" :label="t('production.common.status')" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status) || 'info'">
                {{ statusLabel(row.status) || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
          <el-table-column prop="created_at" label="报工时间" width="160" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="viewDetail(row.id)">{{ t('production.common.detail') }}</el-button>
              <el-button size="small" type="primary" @click="handleApprove(row, 'leader')" v-if="row.status === 'submitted'">
                初审通过
              </el-button>
              <el-button size="small" type="success" @click="handleApprove(row, 'qc')" v-if="row.status === 'leader_approved'">
                终审通过
              </el-button>
              <el-button size="small" type="danger" @click="handleReject(row)" v-if="['submitted', 'leader_approved'].includes(row.status)">
                驳回
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in reports" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">报工 #{{ row.id }}</div>
                <div class="text-xs text-el-placeholder font-mono">{{ row.task?.task_code || `任务#${row.task_id}` }}</div>
              </div>
              <el-tag :type="statusTagType(row.status) || 'info'" size="small">{{ statusLabel(row.status) || row.status }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>报工人</dt>
              <dd>
                <span v-if="row.report_user">{{ row.report_user.full_name }}</span>
                <span v-else>{{ row.report_user_id ? `用户#${row.report_user_id}` : '—' }}</span>
              </dd>
              <dt>合格/不良</dt>
              <dd>{{ row.good_qty }} / {{ row.bad_qty }}</dd>
              <dt>备注</dt>
              <dd>{{ row.remark || '—' }}</dd>
              <dt>报工时间</dt>
              <dd>{{ row.created_at }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="viewDetail(row.id)">{{ t('production.common.detail') }}</el-button>
              <el-button size="small" type="primary" @click="handleApprove(row, 'leader')" v-if="row.status === 'submitted'">{{ t('production.reports.firstApprove') }}</el-button>
              <el-button size="small" type="success" @click="handleApprove(row, 'qc')" v-if="row.status === 'leader_approved'">{{ t('production.reports.finalApprove') }}</el-button>
              <el-button size="small" type="danger" @click="handleReject(row)" v-if="['submitted', 'leader_approved'].includes(row.status)">
                驳回
              </el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !reports.length" description="暂无数据" />
        </div>
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="dialogVisible" :title="t('production.reports.detailTitle')" width="600px">
      <template v-if="currentReport">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="报工ID">{{ currentReport.id }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.common.status')">
            <el-tag :type="statusTagType(currentReport.status) || 'info'">
              {{ statusLabel(currentReport.status) || currentReport.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="合格数">{{ currentReport.good_qty }}</el-descriptions-item>
          <el-descriptions-item label="不良数">{{ currentReport.bad_qty }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ currentReport.remark || '无' }}</el-descriptions-item>
          <el-descriptions-item label="附件" :span="2">{{ currentReport.attachment_ids || '无' }}</el-descriptions-item>
          <el-descriptions-item label="报工时间">{{ currentReport.created_at }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ currentReport.updated_at }}</el-descriptions-item>
        </el-descriptions>

        <!-- 审核流水 -->
        <h4 class="mt-4 mb-2 font-medium">{{ t('production.reports.auditFlow') }}</h4>
        <template v-if="currentReport.audits?.length">
          <el-table class="hidden lg:block w-full" :data="currentReport.audits" size="small" stripe>
            <el-table-column prop="audit_level" label="级别" width="80">
              <template #default="{ row }">
                {{ row.audit_level === 'leader' ? '班组长' : '质检' }}
              </template>
            </el-table-column>
            <el-table-column prop="action" label="操作" width="80">
              <template #default="{ row }">
                <el-tag :type="row.action === 'approve' ? 'success' : 'danger'" size="small">
                  {{ row.action === 'approve' ? '通过' : '驳回' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" min-width="120" />
            <el-table-column prop="created_at" label="时间" width="160" />
          </el-table>
          <div class="lg:hidden space-y-2">
            <div v-for="(row, idx) in currentReport.audits" :key="idx" class="admin-mobile-row">
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
      </template>
    </el-dialog>  </AdminPage>
</template>
