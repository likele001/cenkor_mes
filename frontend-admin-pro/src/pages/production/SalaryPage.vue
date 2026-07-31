<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { productionApi, type SalaryLedgerOut } from '@/api/production'

const { t } = useI18n()
const router = useRouter()
const activeTab = ref('ledger')
const loading = ref(false)
const exporting = ref(false)
const items = ref<SalaryLedgerOut[]>([])
const total = ref(0)
const summary = ref<any[]>([])
const allowances = ref<any[]>([])

const query = reactive({
  month: '',
  user_id: undefined as number | undefined,
  status: '',
  keyword: '',
  offset: 0,
  limit: 50,
})

const allowanceForm = reactive({
  user_id: undefined as number | undefined,
  allowance_type: 'bonus',
  amount: 0,
  reason: '',
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)

const summaryTotal = computed(() =>
  summary.value.reduce((a: number, s: any) => a + Number(s.total_amount || 0), 0),
)
const summaryQty = computed(() => summary.value.reduce((a: number, s: any) => a + Number(s.total_qty || 0), 0))
const confirmedAmount = computed(() => summaryTotal.value)

function statusTagType(label: string) {
  if (label === '已确认') return 'success'
  if (label === '已拒绝') return 'danger'
  if (label === '待确认') return 'warning'
  return 'info'
}

function formatMoney(v: number) {
  return `¥${Number(v || 0).toFixed(2)}`
}

function formatTime(t: string | null) {
  return t ? String(t).slice(0, 19).replace('T', ' ') : '—'
}

function employeeLabel(row: SalaryLedgerOut) {
  return row.user_full_name || row.username || `员工#${row.user_id}`
}

async function loadLedger() {
  loading.value = true
  try {
    const res = await productionApi.listSalaryLedger({
      month: query.month || undefined,
      user_id: query.user_id,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items || []
    total.value = res.total ?? 0
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  const sResp = await productionApi.getSalarySummary({ month: query.month || undefined })
  summary.value = sResp?.items ?? []
}

async function loadAllowances() {
  const res = await productionApi.listSalaryAllowances({
    month: query.month || undefined,
    user_id: query.user_id,
  })
  allowances.value = res?.items ?? []
}

async function reload() {
  await Promise.all([loadLedger(), loadSummary()])
  if (activeTab.value === 'allowance') await loadAllowances()
}

function onSearch() {
  query.offset = 0
  reload()
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  loadLedger()
}

function goReportUnit(row: SalaryLedgerOut) {
  if (row.report_unit_id) {
    router.push('/production/report-units')
    ElMessage.info(`请在「件次报工审核」中查看件次 #${row.report_unit_id}`)
  }
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const params = {
      month: query.month || undefined,
      user_id: query.user_id || undefined,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
    }
    const blob = await productionApi.exportSalaryExcel(params)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `salary_detail_${query.month || 'all'}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出')
  } catch {
    /* http 已提示 */
  } finally {
    exporting.value = false
  }
}

async function addAllowance() {
  if (!allowanceForm.user_id || !query.month) {
    ElMessage.warning('请填写员工ID与月份')
    return
  }
  await productionApi.createSalaryAllowance({
    user_id: allowanceForm.user_id,
    allowance_type: allowanceForm.allowance_type,
    amount: allowanceForm.amount,
    month: query.month,
    reason: allowanceForm.reason || undefined,
  })
  ElMessage.success('已添加')
  allowanceForm.amount = 0
  allowanceForm.reason = ''
  await loadAllowances()
  await loadSummary()
}

onMounted(() => {
  const now = new Date()
  query.month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  reload()
})
</script>


<template>
  <AdminPage :title="t('production.salary.title')">
    <el-row :gutter="12" class="mb-4">
      <el-col :xs="12" :sm="6">
        <el-card shadow="never">
          <div class="text-xs text-zinc-500">{{ t('production.salary.monthlyConfirmed') }}</div>
          <div class="text-xl font-bold text-orange-600 mt-1">{{ formatMoney(confirmedAmount) }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never">
          <div class="text-xs text-zinc-500">{{ t('production.salary.summaryWithAllowance') }}</div>
          <div class="text-xl font-bold mt-1">{{ formatMoney(summaryTotal) }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never">
          <div class="text-xs text-zinc-500">{{ t('production.salary.totalOutput') }}</div>
          <div class="text-xl font-bold mt-1">{{ summaryQty }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never">
          <div class="text-xs text-zinc-500">{{ t('production.salary.currentMonth') }}</div>
          <div class="text-xl font-bold mt-1">{{ query.month || '—' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <el-tabs v-model="activeTab" @tab-change="reload">
        <el-tab-pane label="工资明细" name="ledger" />
        <el-tab-pane label="工资统计" name="stats" />
        <el-tab-pane label="补贴扣款" name="allowance" />
      </el-tabs>

      <div class="flex flex-wrap items-center gap-2 mb-4">
        <el-input v-model="query.month" :placeholder="t('production.salary.monthPlaceholder')" style="width: 130px" />
        <el-input-number v-model="query.user_id" :min="1" :controls="false" :placeholder="t('production.salary.employeeId')" style="width: 110px" />
        <el-select v-model="query.status" clearable :placeholder="t('production.common.status')" style="width: 120px">
          <el-option label="待确认" value="submitted" />
          <el-option label="待终审" value="leader_approved" />
          <el-option label="已确认" value="qc_approved" />
          <el-option label="已拒绝" value="rejected" />
        </el-select>
        <el-input v-model="query.keyword" :placeholder="t('production.salary.keywordPlaceholder')" clearable style="width: 180px" @keyup.enter="onSearch" />
        <el-button @click="reload">{{ t('production.common.refresh') }}</el-button>
        <el-button type="primary" @click="onSearch">{{ t('production.common.search') }}</el-button>
        <el-button :loading="exporting" @click="exportExcel">{{ t('production.salary.exportFilter') }}</el-button>
      </div>

      <!-- 工资明细 -->
      <div v-if="activeTab === 'ledger'" v-loading="loading">
        <el-table :data="items" border stripe class="w-full">
          <el-table-column prop="id" label="ID" width="72">
            <template #default="{ row }">
              <span class="text-xs">{{ row.salary_id || row.id }}</span>
              <el-tag v-if="row.source === 'unit'" size="small" class="ml-1">件</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="员工姓名" min-width="110">
            <template #default="{ row }">{{ employeeLabel(row) }}</template>
          </el-table-column>
          <el-table-column prop="order_code" :label="t('production.salary.orderCode')" min-width="150" show-overflow-tooltip />
          <el-table-column prop="product_name" :label="t('production.salary.productName')" min-width="110" show-overflow-tooltip />
          <el-table-column prop="sku_name" :label="t('production.salary.skuName')" min-width="110" show-overflow-tooltip />
          <el-table-column prop="process_name" :label="t('production.salary.processName')" min-width="100" />
          <el-table-column label="报工数量" width="88" align="center">
            <template #default="{ row }">
              <span v-if="row.unit_seq">第{{ row.unit_seq }}件</span>
              <span v-else>{{ row.reported_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column label="计件工资" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.amount > 0 ? 'text-orange-600 font-medium' : 'text-zinc-400'">
                {{ formatMoney(row.amount) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status_label)" size="small">{{ row.status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="报工时间" width="168">
            <template #default="{ row }">{{ formatTime(row.reported_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="88" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.report_unit_id" link type="primary" size="small" @click="goReportUnit(row)">
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
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
      </div>

      <!-- 工资统计 -->
      <div v-else-if="activeTab === 'stats'">
        <el-table :data="summary" border stripe>
          <el-table-column prop="user_id" :label="t('production.salary.userId')" width="90" />
          <el-table-column prop="month" :label="t('production.salary.month')" width="100" />
          <el-table-column label="总产量" width="100">
            <template #default="{ row }">{{ row.total_qty }}</template>
          </el-table-column>
          <el-table-column label="计件合计" width="120">
            <template #default="{ row }">{{ formatMoney(row.total_amount) }}</template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 补贴扣款 -->
      <div v-else>
        <el-form :model="allowanceForm" inline class="mb-4">
          <el-form-item :label="t('production.salary.userId')">
            <el-input-number v-model="allowanceForm.user_id" :min="1" :controls="false" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="allowanceForm.allowance_type" style="width: 120px">
              <el-option label="补贴" value="bonus" />
              <el-option label="扣款" value="deduction" />
            </el-select>
          </el-form-item>
          <el-form-item label="金额">
            <el-input-number v-model="allowanceForm.amount" :precision="2" />
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="allowanceForm.reason" placeholder="说明" style="width: 160px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="addAllowance">{{ t('production.salary.add') }}</el-button>
          </el-form-item>
        </el-form>
        <el-table :data="allowances" border stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="user_id" label="员工" width="80" />
          <el-table-column label="类型" width="90">
            <template #default="{ row }">{{ row.allowance_type === 'deduction' ? '扣款' : '补贴' }}</template>
          </el-table-column>
          <el-table-column label="金额" width="110">
            <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="month" :label="t('production.salary.month')" width="100" />
          <el-table-column prop="reason" label="原因" min-width="160" />
        </el-table>
      </div>
    </el-card>  </AdminPage>
</template>
