<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { productionApi, type SalarySlipOut } from '@/api/production'
import { http } from '@/utils/http'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const reminding = ref(false)
const exporting = ref(false)
const items = ref<SalarySlipOut[]>([])
const query = reactive({
  month: '',
  user_id: undefined as number | undefined,
  signed: '' as '' | 'true' | 'false',
  offset: 0,
  limit: 50,
})

function currentMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const params: any = {
      month: query.month || undefined,
      user_id: query.user_id || undefined,
      offset: query.offset,
      limit: query.limit,
    }
    if (query.signed === 'true') params.signed = true
    if (query.signed === 'false') params.signed = false
    const res = await productionApi.listSalarySlips(params)
    items.value = res.items ?? []
  } finally {
    loading.value = false
  }
}

function money(v: number) {
  return v.toFixed(2)
}

function confirmStatusLabel(v: string | undefined): string {
  if (v === 'signed') return t('production.salarySlips.confirmStatusSigned')
  if (v === 'rejected') return t('production.salarySlips.confirmStatusRejected')
  return t('production.salarySlips.confirmStatusPending')
}

function confirmStatusTagType(v: string | undefined) {
  if (v === 'signed') return 'success'
  if (v === 'rejected') return 'danger'
  return 'info'
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await productionApi.exportSalarySlips({ month: query.month || undefined })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `salary_slips_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

async function resetConfirm(id: number) {
  await ElMessageBox.confirm('确认重置该工资条确认状态？员工需重新签名确认。', '提示', { type: 'warning' })
  await productionApi.resetSalarySlipConfirm(id)
  ElMessage.success(t('production.salarySlips.resetSuccess'))
  await reload(true)
}

async function previewSignature(attachmentId: number) {
  const blob = await http.request<Blob>({ url: `/files/${attachmentId}`, method: 'GET', responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank')
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

async function downloadSignature(attachmentId: number, filename: string) {
  const blob = await http.request<Blob>({ url: `/files/${attachmentId}`, method: 'GET', params: { download: true }, responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

async function onRemind() {
  if (!query.month) return
  try {
    await ElMessageBox.confirm(
      `确认向 ${query.month} 月份所有未签名的员工发送催签通知？`,
      '批量催签',
      { type: 'warning', confirmButtonText: '发送', cancelButtonText: '取消' },
    )
  } catch { return }
  reminding.value = true
  try {
    const res = await productionApi.remindSalarySlips(query.month)
    ElMessage.success(`已发送 ${res.sent} 条催签通知${res.skipped > 0 ? `，跳过 ${res.skipped} 条已拒签` : ''}`)
  } finally {
    reminding.value = false
  }
}

onMounted(() => {
  query.month = currentMonth()
  reload(true)
})
</script>


<template>
  <AdminPage :title="t('production.salarySlips.title')">
    <el-card shadow="never">
      <template #header><span class="font-medium">{{ t('production.salarySlips.title') }}</span></template>

      <el-form :model="query" inline>
        <el-form-item :label="t('production.salary.month')">
          <el-input v-model="query.month" placeholder="YYYY-MM" style="width: 140px" />
        </el-form-item>
        <el-form-item :label="t('production.salary.employeeId')">
          <el-input-number v-model="query.user_id" :min="1" placeholder="全部" style="width: 160px" clearable />
        </el-form-item>
        <el-form-item :label="t('production.salarySlips.signStatus')">
          <el-select v-model="query.signed" style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="已签" value="true" />
            <el-option label="未签" value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="reload(true)">{{ t('production.common.search') }}</el-button>
          <el-button plain @click="onRemind" :loading="reminding" :disabled="!query.month">{{ t('production.salarySlips.remindUnsigned') }}</el-button>
          <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
        </el-form-item>
      </el-form>

      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" stripe style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="user_id" :label="t('production.salary.employeeId')" width="90" />
          <el-table-column prop="user_name" label="姓名" width="120" />
          <el-table-column prop="month" :label="t('production.salary.month')" width="90" />
          <el-table-column prop="total_qty" label="产量" width="80" />
          <el-table-column prop="item_amount" label="计件" width="110">
            <template #default="{ row }">¥{{ money(row.item_amount) }}</template>
          </el-table-column>
          <el-table-column prop="bonus_amount" label="补贴" width="110">
            <template #default="{ row }">¥{{ money(row.bonus_amount) }}</template>
          </el-table-column>
          <el-table-column prop="deduction_amount" label="扣款" width="110">
            <template #default="{ row }">¥{{ money(row.deduction_amount) }}</template>
          </el-table-column>
          <el-table-column prop="net_amount" label="实发" width="120">
            <template #default="{ row }">
              <span class="font-medium text-orange-600">¥{{ money(row.net_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="确认" width="120">
            <template #default="{ row }">
              <el-tooltip v-if="row.confirm_status === 'rejected' && row.reject_reason" :content="row.reject_reason" placement="top">
                <el-tag :type="confirmStatusTagType(row.confirm_status)">{{ confirmStatusLabel(row.confirm_status) }}</el-tag>
              </el-tooltip>
              <el-tag v-else :type="confirmStatusTagType(row.confirm_status)">{{ confirmStatusLabel(row.confirm_status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="signed_at" label="签名时间" width="170" />
          <el-table-column :label="t('production.salarySlips.signStatus')" width="160">
            <template #default="{ row }">
              <el-tag v-if="row.is_signed" type="success">{{ t('production.salarySlips.signed') }}</el-tag>
              <el-tag v-else type="info">{{ t('production.salarySlips.unsigned') }}</el-tag>
              <el-button
                v-if="row.signature_attachment_id"
                class="ml-2"
                size="small"
                @click="previewSignature(row.signature_attachment_id)"
              >
                预览
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button
                v-if="row.signature_attachment_id"
                size="small"
                @click="downloadSignature(row.signature_attachment_id, `salary_signature_${row.month}_${row.user_id}.png`)"
              >
                下载
              </el-button>
              <el-button v-if="row.confirm_status && row.confirm_status !== 'pending'" class="ml-2" size="small" @click="resetConfirm(row.id)">
                重置
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.user_name || `员工 #${row.user_id}` }}</div>
                <div class="text-xs text-el-placeholder">{{ row.month }} · #{{ row.id }}</div>
              </div>
              <span class="font-medium text-orange-600 text-sm">¥{{ money(row.net_amount) }}</span>
            </div>
            <dl class="admin-mobile-kv">
              <dt>产量</dt>
              <dd>{{ row.total_qty }}</dd>
              <dt>计件</dt>
              <dd>¥{{ money(row.item_amount) }}</dd>
              <dt>补贴</dt>
              <dd>¥{{ money(row.bonus_amount) }}</dd>
              <dt>扣款</dt>
              <dd>¥{{ money(row.deduction_amount) }}</dd>
              <dt>确认</dt>
              <dd class="text-left">
                <el-tooltip v-if="row.confirm_status === 'rejected' && row.reject_reason" :content="row.reject_reason" placement="top">
                  <el-tag :type="confirmStatusTagType(row.confirm_status)" size="small">{{ confirmStatusLabel(row.confirm_status) }}</el-tag>
                </el-tooltip>
                <el-tag v-else :type="confirmStatusTagType(row.confirm_status)" size="small">{{ confirmStatusLabel(row.confirm_status) }}</el-tag>
              </dd>
              <dt>签名</dt>
              <dd class="text-left">
                <el-tag v-if="row.is_signed" type="success" size="small">{{ t('production.salarySlips.signed') }}</el-tag>
                <el-tag v-else type="info" size="small">{{ t('production.salarySlips.unsigned') }}</el-tag>
                <span v-if="row.signed_at" class="block text-xs text-el-placeholder mt-1">{{ row.signed_at }}</span>
              </dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button
                v-if="row.signature_attachment_id"
                size="small"
                @click="previewSignature(row.signature_attachment_id)"
              >
                预览签名
              </el-button>
              <el-button
                v-if="row.signature_attachment_id"
                size="small"
                @click="downloadSignature(row.signature_attachment_id, `salary_signature_${row.month}_${row.user_id}.png`)"
              >
                下载
              </el-button>
              <el-button v-if="row.confirm_status && row.confirm_status !== 'pending'" size="small" @click="resetConfirm(row.id)">
                重置
              </el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" description="暂无工资条" />
        </div>
      </div>
    </el-card>  </AdminPage>
</template>
