<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  productionApi,
  type DispositionItemIn,
  type DispositionMethod,
  type DispositionOut,
  type DispositionReportOption,
  type DispositionStats,
  type DispositionStatus,
} from '@/api/production'
import { masterApi } from '@/api/master'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()

const canManage = computed(() => auth.hasAnyPermission(['disposition.manage']))
const canApprove = computed(() => auth.hasAnyPermission(['disposition.approve']))

const loading = ref(false)
const saving = ref(false)
const rows = ref<DispositionOut[]>([])
const total = ref(0)
const stats = ref<DispositionStats | null>(null)

const query = reactive({
  status: '' as '' | DispositionStatus,
  method: '' as '' | DispositionMethod,
  keyword: '',
  offset: 0,
  limit: 20,
})

// ── 字典 ──
const defectOptions = ref<{ id: number; code: string; name: string }[]>([])
const processOptions = ref<{ id: number; code: string; name: string }[]>([])

const METHOD_TAG: Record<string, 'primary' | 'danger' | 'warning' | 'success'> = {
  rework: 'primary',
  scrap: 'danger',
  concede: 'warning',
  return_process: 'success',
}

function methodLabel(m: string) {
  const map: Record<string, string> = {
    rework: t('production.dispositions.methodRework'),
    scrap: t('production.dispositions.methodScrap'),
    concede: t('production.dispositions.methodConcede'),
    return_process: t('production.dispositions.methodReturn'),
  }
  return map[m] || m
}

function methodTag(m: string) {
  return METHOD_TAG[m] || 'info'
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: t('production.dispositions.statusDraft'),
    pending: t('production.dispositions.statusPending'),
    approved: t('production.dispositions.statusApproved'),
    rejected: t('production.dispositions.statusRejected'),
    closed: t('production.dispositions.statusClosed'),
    cancelled: t('production.dispositions.statusCancelled'),
  }
  return map[s] || s
}

function statusTag(s: string): 'info' | 'warning' | 'success' | 'danger' | 'primary' {
  if (s === 'pending') return 'warning'
  if (s === 'approved') return 'primary'
  if (s === 'closed') return 'success'
  if (s === 'rejected') return 'danger'
  return 'info'
}

function fmtTime(v: string | null) {
  return v ? v.replace('T', ' ').slice(0, 19) : '—'
}

function fmtMoney(v: number) {
  return `¥${Number(v || 0).toFixed(2)}`
}

/** 明细按处置方式合并数量：一行报工的 10 件不良可能拆成 3 报废 + 5 返修 + 2 让步 */
function groupMethods(row: DispositionOut) {
  const out: Record<string, number> = {}
  for (const it of row.items || []) {
    out[it.method] = (out[it.method] || 0) + Number(it.qty || 0)
  }
  return out
}

// ── 列表 ──
async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { offset: query.offset, limit: query.limit }
    if (query.status) params.status = query.status
    if (query.method) params.method = query.method
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    const data = await productionApi.listDispositions(params)
    rows.value = data.items || []
    total.value = data.total ?? rows.value.length
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await productionApi.dispositionStats()
  } catch {
    stats.value = null
  }
}

function search() {
  query.offset = 0
  load()
}

function resetQuery() {
  query.status = ''
  query.method = ''
  query.keyword = ''
  query.offset = 0
  load()
}

function onPageChange(page: number) {
  query.offset = (page - 1) * query.limit
  load()
}

onMounted(async () => {
  await Promise.all([load(), loadStats(), loadDicts()])
})

async function loadDicts() {
  try {
    const d = await productionApi.listDefectCodes()
    defectOptions.value = (d.items || []).map((x) => ({ id: x.id, code: x.code, name: x.name }))
  } catch {
    defectOptions.value = []
  }
  try {
    const p = await masterApi.listProcesses({ offset: 0, limit: 300 })
    processOptions.value = (p.items || []).map((x: any) => ({ id: x.id, code: x.code, name: x.name }))
  } catch {
    processOptions.value = []
  }
}

// ── 制单 ──
const formVisible = ref(false)
const editingId = ref<number | null>(null)
const reportOptions = ref<DispositionReportOption[]>([])
const reportLoading = ref(false)
const form = reactive({
  report_id: null as number | null,
  reason: '',
  remark: '',
  items: [] as DispositionItemIn[],
})

const selectedReport = computed(
  () => reportOptions.value.find((o) => o.report_id === form.report_id) || null,
)

const formQty = computed(() => form.items.reduce((s, it) => s + Number(it.qty || 0), 0))
const overCapacity = computed(
  () => !!selectedReport.value && formQty.value > selectedReport.value.remaining_qty,
)

function blankItem(): DispositionItemIn {
  return { method: 'rework', qty: 1, defect_code_id: null, target_process_id: null, cost_amount: 0, remark: '' }
}

async function searchReports(keyword: string) {
  reportLoading.value = true
  try {
    const data = await productionApi.dispositionReportOptions({ keyword: keyword || undefined, limit: 50 })
    reportOptions.value = data.items || []
  } catch {
    reportOptions.value = []
  } finally {
    reportLoading.value = false
  }
}

function reportLabel(o: DispositionReportOption) {
  const sku = [o.sku_code, o.sku_name].filter(Boolean).join(' ')
  return `${o.task_code || '#' + o.report_id}${sku ? ' · ' + sku : ''} · ${t('production.dispositions.badQty')} ${o.bad_qty} · ${t('production.dispositions.remaining')} ${o.remaining_qty}`
}

async function openCreate() {
  editingId.value = null
  form.report_id = null
  form.reason = ''
  form.remark = ''
  form.items = [blankItem()]
  reportOptions.value = []
  formVisible.value = true
  await searchReports('')
}

async function openEdit(row: DispositionOut) {
  editingId.value = row.id
  form.report_id = row.report_id
  form.reason = row.reason || ''
  form.remark = row.remark || ''
  form.items = (row.items || []).map((it) => ({
    method: it.method,
    qty: it.qty,
    defect_code_id: it.defect_code_id,
    target_process_id: it.target_process_id,
    cost_amount: it.cost_amount ?? 0,
    remark: it.remark || '',
  }))
  reportOptions.value = []
  formVisible.value = true
  await searchReports('')
  // 编辑中的报工可能已不在候选里（比如额度被自己占了），补一条占位让下拉能显示
  if (!reportOptions.value.some((o) => o.report_id === row.report_id)) {
    reportOptions.value = [
      {
        report_id: row.report_id,
        report_status: '',
        task_id: row.task_id,
        task_code: row.task_code || '',
        process_id: row.process_id,
        process_name: row.process_name,
        work_order_id: row.work_order_id,
        order_code: null,
        sku_id: row.sku_id,
        sku_code: row.sku_code,
        sku_name: row.sku_name,
        good_qty: 0,
        bad_qty: row.bad_qty + row.total_qty,
        used_qty: row.total_qty,
        remaining_qty: row.bad_qty,
        created_at: null,
      },
      ...reportOptions.value,
    ]
  }
}

function addItem() {
  form.items.push(blankItem())
}

function removeItem(idx: number) {
  if (form.items.length <= 1) {
    ElMessage.warning(t('production.dispositions.needItem'))
    return
  }
  form.items.splice(idx, 1)
}

async function saveForm() {
  if (!form.report_id) {
    ElMessage.warning(t('production.dispositions.needReport'))
    return
  }
  if (!form.items.length || form.items.some((it) => !it.method || Number(it.qty) <= 0)) {
    ElMessage.warning(t('production.dispositions.needItem'))
    return
  }
  if (overCapacity.value) {
    ElMessage.warning(t('production.dispositions.overCapacity'))
    return
  }
  saving.value = true
  try {
    const payload = {
      report_id: form.report_id,
      reason: form.reason || null,
      remark: form.remark || null,
      items: form.items.map((it) => ({
        method: it.method,
        qty: Number(it.qty),
        defect_code_id: it.defect_code_id || null,
        target_process_id: it.method === 'return_process' ? it.target_process_id || null : null,
        cost_amount: it.method === 'scrap' ? Number(it.cost_amount || 0) : 0,
        remark: it.remark || null,
      })),
    }
    if (editingId.value) {
      await productionApi.updateDisposition(editingId.value, {
        items: payload.items,
        reason: payload.reason ?? undefined,
        remark: payload.remark ?? undefined,
      })
      ElMessage.success(t('production.dispositions.saveOk'))
    } else {
      await productionApi.createDisposition(payload)
      ElMessage.success(t('production.dispositions.createOk'))
    }
    formVisible.value = false
    await Promise.all([load(), loadStats()])
  } catch {
    /* http 已提示 */
  } finally {
    saving.value = false
  }
}

// ── 状态流转 ──
async function doSubmit(row: DispositionOut) {
  try {
    await ElMessageBox.confirm(t('production.dispositions.submitTip'), t('production.dispositions.submit'), {
      confirmButtonText: t('production.dispositions.submit'),
      cancelButtonText: t('production.common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await productionApi.submitDisposition(row.id)
    ElMessage.success(t('production.dispositions.submitOk'))
    await Promise.all([load(), loadStats()])
  } catch {
    /* http 已提示 */
  }
}

async function doApprove(row: DispositionOut) {
  try {
    await ElMessageBox.confirm(t('production.dispositions.approveTip'), t('production.dispositions.approve'), {
      confirmButtonText: t('production.dispositions.approve'),
      cancelButtonText: t('production.common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await productionApi.approveDisposition(row.id)
    ElMessage.success(t('production.dispositions.approveOk'))
    await Promise.all([load(), loadStats()])
  } catch {
    /* http 已提示 */
  }
}

async function doReject(row: DispositionOut) {
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt(
      t('production.dispositions.rejectReason'),
      t('production.dispositions.reject'),
      {
        confirmButtonText: t('production.dispositions.reject'),
        cancelButtonText: t('production.common.cancel'),
        inputPattern: /\S/,
        inputErrorMessage: t('production.dispositions.rejectReason'),
      },
    )
    reason = value
  } catch {
    return
  }
  try {
    await productionApi.rejectDisposition(row.id, reason)
    ElMessage.success(t('production.dispositions.rejectOk'))
    await Promise.all([load(), loadStats()])
  } catch {
    /* http 已提示 */
  }
}

async function doCancel(row: DispositionOut) {
  try {
    await ElMessageBox.confirm(t('production.dispositions.cancelTip'), t('production.dispositions.cancelDoc'), {
      confirmButtonText: t('production.dispositions.cancelDoc'),
      cancelButtonText: t('production.common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await productionApi.cancelDisposition(row.id)
    ElMessage.success(t('production.dispositions.cancelOk'))
    await Promise.all([load(), loadStats()])
  } catch {
    /* http 已提示 */
  }
}

async function doDelete(row: DispositionOut) {
  try {
    await ElMessageBox.confirm(t('production.dispositions.deleteTip'), t('production.dispositions.del'), {
      confirmButtonText: t('production.dispositions.del'),
      cancelButtonText: t('production.common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await productionApi.deleteDisposition(row.id)
    ElMessage.success(t('production.dispositions.deleteOk'))
    await Promise.all([load(), loadStats()])
  } catch {
    /* http 已提示 */
  }
}

// ── 闭环登记 ──
const closeVisible = ref(false)
const closeTarget = ref<DispositionOut | null>(null)
const closeNote = ref('')
const closeItems = ref<{ item_id: number; done_qty: number; remark: string }[]>([])

function openClose(row: DispositionOut) {
  closeTarget.value = row
  closeNote.value = ''
  closeItems.value = (row.items || []).map((it) => ({
    item_id: it.id,
    done_qty: it.done_qty ?? it.qty,
    remark: it.remark || '',
  }))
  closeVisible.value = true
}

async function saveClose() {
  if (!closeTarget.value) return
  saving.value = true
  try {
    await productionApi.closeDisposition(closeTarget.value.id, {
      items: closeItems.value.map((it) => ({ item_id: it.item_id, done_qty: Number(it.done_qty), remark: it.remark || undefined })),
      note: closeNote.value || undefined,
    })
    ElMessage.success(t('production.dispositions.closeOk'))
    closeVisible.value = false
    await Promise.all([load(), loadStats()])
    if (detail.value?.id === closeTarget.value.id) await viewDetail(closeTarget.value.id)
  } catch {
    /* http 已提示 */
  } finally {
    saving.value = false
  }
}

// ── 详情 / 导出 ──
const detailVisible = ref(false)
const detail = ref<DispositionOut | null>(null)

async function viewDetail(id: number) {
  try {
    detail.value = await productionApi.getDisposition(id)
    detailVisible.value = true
  } catch {
    /* http 已提示 */
  }
}

async function exportDoc(row: DispositionOut) {
  try {
    const blob = await productionApi.exportDisposition(row.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `disposition_${row.code}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(t('production.dispositions.exportOk'))
  } catch {
    /* http 已提示 */
  }
}
</script>

<template>
  <AdminPage :title="t('production.dispositions.title')">
    <template #actions>
      <el-button :loading="loading" @click="load">{{ t('production.dispositions.refresh') }}</el-button>
      <el-button v-if="canManage" type="primary" @click="openCreate">{{ t('production.dispositions.create') }}</el-button>
    </template>

    <div class="disp-stats">
      <div class="disp-stat">
        <span class="disp-stat__label">{{ t('production.dispositions.statsPending') }}</span>
        <span class="disp-stat__value">{{ stats?.by_status?.pending ?? 0 }}</span>
      </div>
      <div class="disp-stat">
        <span class="disp-stat__label">{{ t('production.dispositions.statsApproved') }}</span>
        <span class="disp-stat__value">{{ stats?.by_status?.approved ?? 0 }}</span>
      </div>
      <div class="disp-stat">
        <span class="disp-stat__label">{{ t('production.dispositions.statsTotal') }}</span>
        <span class="disp-stat__value">{{ stats?.total_qty ?? 0 }}</span>
      </div>
      <div class="disp-stat">
        <span class="disp-stat__label">{{ t('production.dispositions.statsScrapCost') }}</span>
        <span class="disp-stat__value">{{ fmtMoney(stats?.scrap_cost ?? 0) }}</span>
      </div>
      <div class="disp-stat">
        <span class="disp-stat__label">{{ t('production.dispositions.methodScrap') }}</span>
        <span class="disp-stat__value">{{ stats?.by_method?.scrap?.qty ?? 0 }}</span>
      </div>
      <div class="disp-stat">
        <span class="disp-stat__label">{{ t('production.dispositions.methodRework') }}</span>
        <span class="disp-stat__value">{{ stats?.by_method?.rework?.qty ?? 0 }}</span>
      </div>
    </div>

    <el-form inline class="disp-filter" @submit.prevent="search">
      <el-form-item :label="t('production.dispositions.status')">
        <el-select v-model="query.status" :placeholder="t('production.dispositions.all')" clearable style="width: 140px" @change="search">
          <el-option :label="t('production.dispositions.all')" value="" />
          <el-option :label="t('production.dispositions.statusDraft')" value="draft" />
          <el-option :label="t('production.dispositions.statusPending')" value="pending" />
          <el-option :label="t('production.dispositions.statusApproved')" value="approved" />
          <el-option :label="t('production.dispositions.statusRejected')" value="rejected" />
          <el-option :label="t('production.dispositions.statusClosed')" value="closed" />
          <el-option :label="t('production.dispositions.statusCancelled')" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('production.dispositions.method')">
        <el-select v-model="query.method" :placeholder="t('production.dispositions.all')" clearable style="width: 140px" @change="search">
          <el-option :label="t('production.dispositions.all')" value="" />
          <el-option :label="t('production.dispositions.methodRework')" value="rework" />
          <el-option :label="t('production.dispositions.methodScrap')" value="scrap" />
          <el-option :label="t('production.dispositions.methodConcede')" value="concede" />
          <el-option :label="t('production.dispositions.methodReturn')" value="return_process" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('production.dispositions.keyword')">
        <el-input v-model="query.keyword" :placeholder="t('production.dispositions.keywordPlaceholder')" clearable style="width: 200px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">{{ t('production.dispositions.search') }}</el-button>
        <el-button @click="resetQuery">{{ t('production.dispositions.reset') }}</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="rows" border class="w-full">
      <el-table-column prop="code" :label="t('production.dispositions.code')" width="160">
        <template #default="{ row }">
          <el-link type="primary" @click="viewDetail(row.id)">{{ row.code }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="task_code" :label="t('production.dispositions.taskCode')" width="140" />
      <el-table-column prop="process_name" :label="t('production.dispositions.process')" width="120" />
      <el-table-column :label="t('production.dispositions.sku')" min-width="160">
        <template #default="{ row }">
          <div>{{ row.sku_code || '—' }}</div>
          <div class="disp-sub">{{ row.sku_name || '' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="bad_qty" :label="t('production.dispositions.badQty')" width="100" align="right" />
      <el-table-column prop="total_qty" :label="t('production.dispositions.totalQty')" width="100" align="right" />
      <el-table-column :label="t('production.dispositions.methods')" min-width="150">
        <template #default="{ row }">
          <el-tag
            v-for="(grp, m) in groupMethods(row)"
            :key="m"
            :type="methodTag(String(m))"
            size="small"
            class="disp-tag"
          >{{ methodLabel(String(m)) }} × {{ grp }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('production.dispositions.scrapCost')" width="110" align="right">
        <template #default="{ row }">{{ fmtMoney(row.scrap_cost) }}</template>
      </el-table-column>
      <el-table-column :label="t('production.dispositions.statusLabel')" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('production.dispositions.createdAt')" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('production.dispositions.actions')" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewDetail(row.id)">{{ t('production.dispositions.detail') }}</el-button>
          <el-button v-if="canManage && (row.status === 'draft' || row.status === 'rejected')" size="small" @click="openEdit(row)">
            {{ t('production.dispositions.edit') }}
          </el-button>
          <el-button v-if="canManage && (row.status === 'draft' || row.status === 'rejected')" size="small" type="primary" @click="doSubmit(row)">
            {{ t('production.dispositions.submit') }}
          </el-button>
          <el-button v-if="canApprove && row.status === 'pending'" size="small" type="primary" @click="doApprove(row)">
            {{ t('production.dispositions.approve') }}
          </el-button>
          <el-button v-if="canApprove && row.status === 'pending'" size="small" type="danger" @click="doReject(row)">
            {{ t('production.dispositions.reject') }}
          </el-button>
          <el-button v-if="canManage && row.status === 'approved'" size="small" type="success" @click="openClose(row)">
            {{ t('production.dispositions.closeDoc') }}
          </el-button>
          <el-button v-if="canManage && ['draft', 'pending', 'rejected'].includes(row.status)" size="small" @click="doCancel(row)">
            {{ t('production.dispositions.cancelDoc') }}
          </el-button>
          <el-button v-if="canManage && row.status === 'draft'" size="small" type="danger" @click="doDelete(row)">
            {{ t('production.dispositions.del') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="disp-pager">
      <el-pagination
        layout="total, prev, pager, next"
        :total="total"
        :page-size="query.limit"
        :current-page="Math.floor(query.offset / query.limit) + 1"
        @current-change="onPageChange"
      />
    </div>

    <!-- 制单 / 改单 -->
    <el-dialog v-model="formVisible" :title="editingId ? t('production.dispositions.editTitle') : t('production.dispositions.createTitle')" width="880px" top="6vh">
      <el-form label-width="96px">
        <el-form-item :label="t('production.dispositions.report')" required>
          <el-select
            v-model="form.report_id"
            filterable
            remote
            reserve-keyword
            :remote-method="searchReports"
            :loading="reportLoading"
            :disabled="!!editingId"
            :placeholder="t('production.dispositions.reportPlaceholder')"
            style="width: 100%"
          >
            <el-option v-for="o in reportOptions" :key="o.report_id" :label="reportLabel(o)" :value="o.report_id" />
            <template #empty>
              <div class="disp-empty">{{ t('production.dispositions.reportEmpty') }}</div>
            </template>
          </el-select>
        </el-form-item>
        <el-form-item :label="t('production.dispositions.reason')">
          <el-input v-model="form.reason" maxlength="255" :placeholder="t('production.dispositions.reasonPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('production.dispositions.items')" required>
          <div class="disp-items">
            <div v-for="(it, idx) in form.items" :key="idx" class="disp-item">
              <el-select v-model="it.method" style="width: 130px">
                <el-option :label="t('production.dispositions.methodRework')" value="rework" />
                <el-option :label="t('production.dispositions.methodScrap')" value="scrap" />
                <el-option :label="t('production.dispositions.methodConcede')" value="concede" />
                <el-option :label="t('production.dispositions.methodReturn')" value="return_process" />
              </el-select>
              <el-input-number v-model="it.qty" :min="1" :controls="false" style="width: 90px" />
              <el-select v-model="it.defect_code_id" filterable clearable :placeholder="t('production.dispositions.itemDefect')" style="width: 170px">
                <el-option v-for="d in defectOptions" :key="d.id" :label="`${d.code} ${d.name}`" :value="d.id" />
              </el-select>
              <el-select
                v-if="it.method === 'return_process'"
                v-model="it.target_process_id"
                filterable
                clearable
                :placeholder="t('production.dispositions.itemTargetProcess')"
                style="width: 160px"
              >
                <el-option v-for="p in processOptions" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
              <el-input-number
                v-if="it.method === 'scrap'"
                v-model="it.cost_amount"
                :min="0"
                :precision="2"
                :controls="false"
                :placeholder="t('production.dispositions.itemCost')"
                style="width: 120px"
              />
              <el-input v-model="it.remark" :placeholder="t('production.dispositions.itemRemark')" style="width: 150px" />
              <el-button type="danger" text @click="removeItem(idx)">{{ t('production.dispositions.removeItem') }}</el-button>
            </div>
            <el-button text type="primary" @click="addItem">+ {{ t('production.dispositions.addItem') }}</el-button>
            <div class="disp-sum" :class="{ 'is-over': overCapacity }">
              {{ t('production.dispositions.sumTip', { qty: formQty, remaining: selectedReport?.remaining_qty ?? '—' }) }}
            </div>
          </div>
        </el-form-item>
        <el-form-item :label="t('production.dispositions.remark')">
          <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <div class="disp-hint">{{ t('production.dispositions.hint') }}</div>
      <template #footer>
        <el-button @click="formVisible = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveForm">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-drawer v-model="detailVisible" :title="t('production.dispositions.detailTitle')" size="640px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('production.dispositions.code')">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.statusLabel')">
            <el-tag :type="statusTag(detail.status)" size="small">{{ statusLabel(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.taskCode')">{{ detail.task_code || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.process')">{{ detail.process_name || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.sku')">{{ [detail.sku_code, detail.sku_name].filter(Boolean).join(' ') || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.badQty')">{{ detail.bad_qty }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.totalQty')">{{ detail.total_qty }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.scrapCost')">{{ fmtMoney(detail.scrap_cost) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.reason')" :span="2">{{ detail.reason || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.rejectReasonLabel')" :span="2">{{ detail.reject_reason || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.closeNote')" :span="2">{{ detail.close_note || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.createdAt')">{{ fmtTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.dispositions.closedAt')">{{ fmtTime(detail.closed_at) }}</el-descriptions-item>
        </el-descriptions>

        <el-table :data="detail.items || []" border size="small" class="disp-detail-table">
          <el-table-column :label="t('production.dispositions.itemMethod')" width="100">
            <template #default="{ row }">
              <el-tag :type="methodTag(row.method)" size="small">{{ methodLabel(row.method) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="qty" :label="t('production.dispositions.itemQty')" width="80" align="right" />
          <el-table-column :label="t('production.dispositions.itemDefect')" min-width="130">
            <template #default="{ row }">{{ row.defect_code ? `${row.defect_code} ${row.defect_name || ''}` : '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('production.dispositions.itemTargetProcess')" width="110">
            <template #default="{ row }">{{ row.target_process_name || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('production.dispositions.itemCost')" width="100" align="right">
            <template #default="{ row }">{{ fmtMoney(row.cost_amount) }}</template>
          </el-table-column>
          <el-table-column :label="t('production.dispositions.doneQty')" width="90" align="right">
            <template #default="{ row }">{{ row.done_qty ?? '—' }}</template>
          </el-table-column>
        </el-table>

        <div class="disp-detail-actions">
          <el-button v-if="canApprove && detail.status === 'pending'" type="primary" @click="doApprove(detail)">{{ t('production.dispositions.approve') }}</el-button>
          <el-button v-if="canApprove && detail.status === 'pending'" type="danger" @click="doReject(detail)">{{ t('production.dispositions.reject') }}</el-button>
          <el-button v-if="canManage && detail.status === 'approved'" type="success" @click="openClose(detail)">{{ t('production.dispositions.closeDoc') }}</el-button>
          <el-button @click="exportDoc(detail)">{{ t('production.dispositions.export') }}</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 闭环 -->
    <el-dialog v-model="closeVisible" :title="t('production.dispositions.closeTitle')" width="620px">
      <div class="disp-hint">{{ t('production.dispositions.closeTip') }}</div>
      <el-table :data="closeItems" border size="small">
        <el-table-column :label="t('production.dispositions.itemMethod')" width="110">
          <template #default="{ row, $index }">
            {{ methodLabel((closeTarget?.items || [])[$index]?.method || '') }}
          </template>
        </el-table-column>
        <el-table-column :label="t('production.dispositions.itemQty')" width="90" align="right">
          <template #default="{ $index }">{{ (closeTarget?.items || [])[$index]?.qty ?? '' }}</template>
        </el-table-column>
        <el-table-column :label="t('production.dispositions.doneQty')" width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.done_qty" :min="0" :controls="false" style="width: 110px" />
          </template>
        </el-table-column>
        <el-table-column :label="t('production.dispositions.itemRemark')" min-width="140">
          <template #default="{ row }">
            <el-input v-model="row.remark" maxlength="255" />
          </template>
        </el-table-column>
      </el-table>
      <el-form label-width="96px" class="disp-close-note">
        <el-form-item :label="t('production.dispositions.closeNote')">
          <el-input v-model="closeNote" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeVisible = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveClose">{{ t('production.dispositions.closeDoc') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<style scoped>
.disp-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.disp-stat {
  flex: 1 1 140px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.disp-stat__label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.disp-stat__value {
  font-size: 20px;
  font-weight: 600;
}
.disp-filter {
  margin-bottom: 8px;
}
.disp-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.disp-tag {
  margin: 2px 4px 2px 0;
}
.disp-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.disp-items {
  width: 100%;
}
.disp-item {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.disp-sum {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.disp-sum.is-over {
  color: var(--el-color-danger);
  font-weight: 600;
}
.disp-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.disp-detail-table {
  margin-top: 12px;
}
.disp-detail-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
.disp-close-note {
  margin-top: 12px;
}
.disp-empty {
  padding: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
