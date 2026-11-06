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
  type InspectionItemOut,
  type InspectionOut,
  type InspectionSourceOption,
  type InspectionStats,
  type InspectionStatus,
  type InspectionTemplateOption,
  type InspectionType,
} from '@/api/production'
import { masterApi } from '@/api/master'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()

const canManage = computed(() => auth.hasAnyPermission(['inspection.manage']))
const canAudit = computed(() => auth.hasAnyPermission(['inspection.audit']))

const loading = ref(false)
const saving = ref(false)
const rows = ref<InspectionOut[]>([])
const total = ref(0)
const stats = ref<InspectionStats | null>(null)

const query = reactive({
  inspection_type: '' as '' | InspectionType,
  status: '' as '' | InspectionStatus,
  keyword: '',
  offset: 0,
  limit: 20,
})

// ── 字典 ──
const defectOptions = ref<{ id: number; code: string; name: string }[]>([])

const TYPE_TAG: Record<string, 'primary' | 'success' | 'warning' | 'danger'> = {
  iqc: 'warning',
  ipqc: 'primary',
  oqc: 'success',
  fai: 'danger',
}
const STATUS_TAG: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
  draft: 'info',
  pending: 'warning',
  passed: 'success',
  failed: 'danger',
  cancelled: 'info',
}
const HANDLING_TAG: Record<string, 'primary' | 'danger' | 'warning' | 'success'> = {
  return: 'danger',
  accept: 'warning',
  rework: 'primary',
  scrap: 'danger',
}

function typeLabel(v: string) {
  const map: Record<string, string> = {
    iqc: t('production.inspections.typeIqc'),
    ipqc: t('production.inspections.typeIpqc'),
    oqc: t('production.inspections.typeOqc'),
    fai: t('production.inspections.typeFai'),
  }
  return map[v] || v
}
function typeTag(v: string) {
  return TYPE_TAG[v] || 'info'
}
function statusLabel(v: string) {
  const map: Record<string, string> = {
    draft: t('production.inspections.statusDraft'),
    pending: t('production.inspections.statusPending'),
    passed: t('production.inspections.statusPassed'),
    failed: t('production.inspections.statusFailed'),
    cancelled: t('production.inspections.statusCancelled'),
  }
  return map[v] || v
}
function statusTag(v: string) {
  return STATUS_TAG[v] || 'info'
}
function handlingLabel(v: string | null) {
  if (!v) return '—'
  const map: Record<string, string> = {
    return: t('production.inspections.handlingReturn'),
    accept: t('production.inspections.handlingAccept'),
    rework: t('production.inspections.handlingRework'),
    scrap: t('production.inspections.handlingScrap'),
  }
  return map[v] || v
}
function resultLabel(v: string | null) {
  if (!v) return '—'
  const map: Record<string, string> = {
    pass: t('production.inspections.resultPass'),
    fail: t('production.inspections.resultFail'),
    na: t('production.inspections.resultNa'),
  }
  return map[v] || v
}

function fmtTime(v: string | null) {
  return v ? v.replace('T', ' ').slice(0, 19) : '—'
}

// ── 列表 ──
async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { offset: query.offset, limit: query.limit }
    if (query.inspection_type) params.inspection_type = query.inspection_type
    if (query.status) params.status = query.status
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    const data = await productionApi.listInspections(params)
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
    stats.value = await productionApi.inspectionStats()
  } catch {
    stats.value = null
  }
}

function search() {
  query.offset = 0
  load()
}

function resetQuery() {
  query.inspection_type = ''
  query.status = ''
  query.keyword = ''
  query.offset = 0
  load()
}

function onPageChange(page: number) {
  query.offset = (page - 1) * query.limit
  load()
}

async function exportList() {
  try {
    const params: Record<string, unknown> = {}
    if (query.inspection_type) params.inspection_type = query.inspection_type
    if (query.status) params.status = query.status
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    const blob = await productionApi.exportInspections(params)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'inspections.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    /* http 已提示 */
  }
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
}

// ── 制单 / 改单 ──
const formVisible = ref(false)
const editingId = ref<number | null>(null)
const templateOptions = ref<InspectionTemplateOption[]>([])
const sourceOptions = ref<InspectionSourceOption[]>([])
const sourceLoading = ref(false)

const form = reactive({
  inspection_type: 'iqc' as InspectionType,
  source_id: null as number | null,
  template_id: null as number | null,
  qty: 0,
  sample_qty: 0,
  batch_no: '',
  item_name: '',
  remark: '',
})

const selectedSource = computed(
  () => sourceOptions.value.find((o) => o.id === form.source_id) || null,
)

const SOURCE_TYPE_BY_INSPECTION: Record<InspectionType, string> = {
  iqc: 'purchase_order',
  ipqc: 'work_order',
  oqc: 'shipment',
  fai: 'task',
}

async function loadTemplates() {
  try {
    const data = await productionApi.inspectionTemplateOptions({ limit: 100 })
    templateOptions.value = data || []
  } catch {
    templateOptions.value = []
  }
}

async function searchSources(keyword: string) {
  sourceLoading.value = true
  try {
    const data = await productionApi.inspectionSourceOptions({
      inspection_type: form.inspection_type,
      keyword: keyword || undefined,
      limit: 50,
    })
    sourceOptions.value = data || []
  } catch {
    sourceOptions.value = []
  } finally {
    sourceLoading.value = false
  }
}

async function onTypeChange() {
  form.source_id = null
  sourceOptions.value = []
  await searchSources('')
}

function onSourceChange(opt: InspectionSourceOption) {
  // 送检量默认带出来源单据数量，改过就不覆盖
  if (opt.qty && form.qty === 0) form.qty = opt.qty
  if (opt.item_name && !form.item_name) form.item_name = opt.item_name
}

function openCreate() {
  editingId.value = null
  form.inspection_type = 'iqc'
  form.source_id = null
  form.template_id = null
  form.qty = 0
  form.sample_qty = 0
  form.batch_no = ''
  form.item_name = ''
  form.remark = ''
  sourceOptions.value = []
  formVisible.value = true
  loadTemplates()
  searchSources('')
}

async function openEdit(row: InspectionOut) {
  editingId.value = row.id
  form.inspection_type = row.inspection_type
  form.source_id = null
  form.template_id = row.template_id
  form.qty = row.qty
  form.sample_qty = row.sample_qty
  form.batch_no = row.batch_no || ''
  form.item_name = row.item_name || ''
  form.remark = row.remark || ''
  sourceOptions.value = []
  formVisible.value = true
  loadTemplates()
  await viewDetail(row.id)
  formVisible.value = false
}

async function saveForm() {
  if (!form.qty || form.qty <= 0) {
    ElMessage.warning(t('production.inspections.needQty'))
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await productionApi.updateInspection(editingId.value, {
        qty: form.qty,
        sample_qty: form.sample_qty,
        batch_no: form.batch_no || undefined,
        item_name: form.item_name || undefined,
        template_id: form.template_id || undefined,
        remark: form.remark || undefined,
      })
      ElMessage.success(t('production.inspections.saveOk'))
    } else {
      await productionApi.createInspection({
        inspection_type: form.inspection_type,
        qty: form.qty,
        sample_qty: form.sample_qty,
        template_id: form.template_id || undefined,
        source_type: form.source_id
          ? SOURCE_TYPE_BY_INSPECTION[form.inspection_type]
          : 'manual',
        source_id: form.source_id || undefined,
        item_name: form.item_name || undefined,
        batch_no: form.batch_no || undefined,
        remark: form.remark || undefined,
      })
      ElMessage.success(t('production.inspections.createOk'))
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
async function doSubmit(row: InspectionOut) {
  try {
    await ElMessageBox.confirm(t('production.inspections.submitTip'), t('production.inspections.submit'), {
      confirmButtonText: t('production.inspections.submit'),
      cancelButtonText: t('production.common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await productionApi.submitInspection(row.id)
    ElMessage.success(t('production.inspections.submitOk'))
    await Promise.all([load(), loadStats()])
    if (detail.value?.id === row.id) await viewDetail(row.id)
  } catch {
    /* http 已提示 */
  }
}

async function doCancel(row: InspectionOut) {
  try {
    await ElMessageBox.confirm(t('production.inspections.cancelTip'), t('production.inspections.cancelDoc'), {
      confirmButtonText: t('production.inspections.cancelDoc'),
      cancelButtonText: t('production.common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await productionApi.cancelInspection(row.id)
    ElMessage.success(t('production.inspections.cancelOk'))
    await Promise.all([load(), loadStats()])
    if (detail.value?.id === row.id) detailVisible.value = false
  } catch {
    /* http 已提示 */
  }
}

async function doDelete(row: InspectionOut) {
  try {
    await ElMessageBox.confirm(t('production.inspections.deleteTip'), t('production.inspections.del'), {
      confirmButtonText: t('production.inspections.del'),
      cancelButtonText: t('production.common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await productionApi.deleteInspection(row.id)
    ElMessage.success(t('production.inspections.deleteOk'))
    await Promise.all([load(), loadStats()])
  } catch {
    /* http 已提示 */
  }
}

async function doClose(row: InspectionOut) {
  try {
    await ElMessageBox.confirm(t('production.inspections.closeTip'), t('production.inspections.closeDoc'), {
      confirmButtonText: t('production.inspections.closeDoc'),
      cancelButtonText: t('production.common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await productionApi.closeInspection(row.id)
    ElMessage.success(t('production.inspections.closeOk'))
    await Promise.all([load(), loadStats()])
    if (detail.value?.id === row.id) await viewDetail(row.id)
  } catch {
    /* http 已提示 */
  }
}

// ── 详情 / 录结果 ──
const detailVisible = ref(false)
const detail = ref<InspectionOut | null>(null)
/** 录结果模式：draft / pending 且有 manage 权限时可改检查项 */
const recording = ref(false)
const editItems = ref<InspectionItemOut[]>([])

async function viewDetail(id: number) {
  try {
    detail.value = await productionApi.getInspection(id)
    detailVisible.value = true
    stopRecord()
  } catch {
    /* http 已提示 */
  }
}

const canRecord = computed(
  () =>
    !!detail.value &&
    ['draft', 'pending'].includes(detail.value.status) &&
    canManage.value,
)

function startRecord() {
  if (!detail.value) return
  editItems.value = (detail.value.items || []).map((it) => ({ ...it, remark: it.remark || '' }))
  recording.value = true
}

function stopRecord() {
  recording.value = false
  editItems.value = []
}

async function saveRecord() {
  if (!detail.value) return
  saving.value = true
  try {
    // 只提交 seq + 录入字段，后端按 seq 合并，不会动其他项
    await productionApi.updateInspection(detail.value.id, {
      items: editItems.value.map((it) => ({
        seq: it.seq,
        result: it.result || undefined,
        measured_value: it.measured_value || undefined,
        defect_code_id: it.defect_code_id || undefined,
        remark: it.remark || undefined,
      })),
    })
    ElMessage.success(t('production.inspections.recordOk'))
    stopRecord()
    await Promise.all([load(), loadStats()])
    await viewDetail(detail.value.id)
  } catch {
    /* http 已提示 */
  } finally {
    saving.value = false
  }
}

// ── 判定 ──
const judgeVisible = ref(false)
const judgeTarget = ref<InspectionOut | null>(null)
const judgeForm = reactive({
  accept_qty: 0,
  reject_qty: 0,
  handling: '' as '' | 'return' | 'accept' | 'rework' | 'scrap',
  conclusion: '',
})

function openJudge(row: InspectionOut) {
  judgeTarget.value = row
  judgeForm.accept_qty = row.qty
  judgeForm.reject_qty = 0
  judgeForm.handling = ''
  judgeForm.conclusion = ''
  judgeVisible.value = true
}

async function saveJudge() {
  if (!judgeTarget.value) return
  if (judgeForm.handling && judgeForm.accept_qty + judgeForm.reject_qty > judgeTarget.value.qty) {
    ElMessage.warning(t('production.inspections.overQty'))
    return
  }
  saving.value = true
  try {
    await productionApi.judgeInspection(judgeTarget.value.id, {
      accept_qty: judgeForm.accept_qty,
      reject_qty: judgeForm.reject_qty,
      handling: judgeForm.handling || undefined,
      conclusion: judgeForm.conclusion || undefined,
    })
    ElMessage.success(t('production.inspections.judgeOk'))
    judgeVisible.value = false
    await Promise.all([load(), loadStats()])
    if (detail.value?.id === judgeTarget.value.id) await viewDetail(judgeTarget.value.id)
  } catch {
    /* http 已提示 */
  } finally {
    saving.value = false
  }
}

// ── 单张导出 ──
async function exportDoc(row: InspectionOut) {
  try {
    const blob = await productionApi.exportInspection(row.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `inspection_${row.code}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    /* http 已提示 */
  }
}
</script>

<template>
  <AdminPage :title="t('production.inspections.title')">
    <template #actions>
      <el-button :loading="loading" @click="load">{{ t('production.inspections.refresh') }}</el-button>
      <el-button @click="exportList">{{ t('production.inspections.export') }}</el-button>
      <el-button v-if="canManage" type="primary" @click="openCreate">{{ t('production.inspections.create') }}</el-button>
    </template>

    <div class="insp-stats">
      <div class="insp-stat">
        <span class="insp-stat__label">{{ t('production.inspections.statsPending') }}</span>
        <span class="insp-stat__value">{{ stats?.pending ?? 0 }}</span>
      </div>
      <div class="insp-stat">
        <span class="insp-stat__label">{{ t('production.inspections.statsPassed') }}</span>
        <span class="insp-stat__value">{{ stats?.passed ?? 0 }}</span>
      </div>
      <div class="insp-stat">
        <span class="insp-stat__label">{{ t('production.inspections.statsFailed') }}</span>
        <span class="insp-stat__value">{{ stats?.failed ?? 0 }}</span>
      </div>
      <div class="insp-stat">
        <span class="insp-stat__label">{{ t('production.inspections.statsPassRate') }}</span>
        <span class="insp-stat__value">{{ stats?.pass_rate == null ? '—' : `${stats.pass_rate}%` }}</span>
      </div>
      <div class="insp-stat">
        <span class="insp-stat__label">{{ t('production.inspections.statsRejectQty') }}</span>
        <span class="insp-stat__value">{{ stats?.reject_qty ?? 0 }}</span>
      </div>
    </div>

    <el-form inline class="insp-filter" @submit.prevent="search">
      <el-form-item :label="t('production.inspections.inspectionType')">
        <el-select v-model="query.inspection_type" clearable style="width: 130px" @change="search">
          <el-option :label="t('production.inspections.all')" value="" />
          <el-option :label="t('production.inspections.typeIqc')" value="iqc" />
          <el-option :label="t('production.inspections.typeIpqc')" value="ipqc" />
          <el-option :label="t('production.inspections.typeOqc')" value="oqc" />
          <el-option :label="t('production.inspections.typeFai')" value="fai" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('production.inspections.status')">
        <el-select v-model="query.status" clearable style="width: 130px" @change="search">
          <el-option :label="t('production.inspections.all')" value="" />
          <el-option :label="t('production.inspections.statusDraft')" value="draft" />
          <el-option :label="t('production.inspections.statusPending')" value="pending" />
          <el-option :label="t('production.inspections.statusPassed')" value="passed" />
          <el-option :label="t('production.inspections.statusFailed')" value="failed" />
          <el-option :label="t('production.inspections.statusCancelled')" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('production.inspections.keyword')">
        <el-input v-model="query.keyword" :placeholder="t('production.inspections.keywordPlaceholder')" clearable style="width: 220px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">{{ t('production.inspections.search') }}</el-button>
        <el-button @click="resetQuery">{{ t('production.inspections.reset') }}</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="rows" border class="w-full">
      <el-table-column prop="code" :label="t('production.inspections.code')" width="150">
        <template #default="{ row }">
          <el-link type="primary" @click="viewDetail(row.id)">{{ row.code }}</el-link>
        </template>
      </el-table-column>
      <el-table-column :label="t('production.inspections.inspectionType')" width="100">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.inspection_type)" size="small">{{ typeLabel(row.inspection_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('production.inspections.statusLabel')" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source_code" :label="t('production.inspections.sourceCode')" width="130">
        <template #default="{ row }">{{ row.source_code || '—' }}</template>
      </el-table-column>
      <el-table-column prop="item_name" :label="t('production.inspections.objectName')" min-width="150" show-overflow-tooltip />
      <el-table-column prop="batch_no" :label="t('production.inspections.batchNo')" width="110">
        <template #default="{ row }">{{ row.batch_no || '—' }}</template>
      </el-table-column>
      <el-table-column prop="qty" :label="t('production.inspections.qty')" width="90" align="right" />
      <el-table-column :label="t('production.inspections.progress')" width="100" align="center">
        <template #default="{ row }">
          <span :class="{ 'insp-progress-bad': row.item_failed > 0 }">{{ row.item_filled }}/{{ row.item_total }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('production.inspections.handling')" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.handling" :type="HANDLING_TAG[row.handling] || 'info'" size="small">{{ handlingLabel(row.handling) }}</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column prop="inspector_name" :label="t('production.inspections.inspector')" width="100">
        <template #default="{ row }">{{ row.inspector_name || '—' }}</template>
      </el-table-column>
      <el-table-column :label="t('production.inspections.inspectedAt')" width="150">
        <template #default="{ row }">{{ fmtTime(row.inspected_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('production.inspections.actions')" width="250" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewDetail(row.id)">{{ t('production.inspections.detail') }}</el-button>
          <el-button v-if="canManage && row.status === 'draft'" size="small" @click="openEdit(row)">
            {{ t('production.inspections.edit') }}
          </el-button>
          <el-button v-if="canManage && row.status === 'draft'" size="small" type="primary" @click="doSubmit(row)">
            {{ t('production.inspections.submit') }}
          </el-button>
          <el-button v-if="canAudit && row.status === 'pending'" size="small" type="primary" @click="openJudge(row)">
            {{ t('production.inspections.judge') }}
          </el-button>
          <el-button v-if="canManage && ['passed', 'failed'].includes(row.status) && !row.is_closed" size="small" type="success" @click="doClose(row)">
            {{ t('production.inspections.closeDoc') }}
          </el-button>
          <el-button v-if="canManage && ['draft', 'pending'].includes(row.status)" size="small" @click="doCancel(row)">
            {{ t('production.inspections.cancelDoc') }}
          </el-button>
          <el-button v-if="canManage && row.status === 'draft'" size="small" type="danger" @click="doDelete(row)">
            {{ t('production.inspections.del') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="insp-pager">
      <el-pagination
        layout="total, prev, pager, next"
        :total="total"
        :page-size="query.limit"
        :current-page="Math.floor(query.offset / query.limit) + 1"
        @current-change="onPageChange"
      />
    </div>

    <!-- 制单 / 改单 -->
    <el-dialog v-model="formVisible" :title="editingId ? t('production.inspections.editTitle') : t('production.inspections.createTitle')" width="720px" top="8vh">
      <el-form label-width="100px">
        <el-form-item :label="t('production.inspections.inspectionType')" required>
          <el-select v-model="form.inspection_type" :disabled="!!editingId" style="width: 220px" @change="onTypeChange">
            <el-option :label="t('production.inspections.typeIqc')" value="iqc" />
            <el-option :label="t('production.inspections.typeIpqc')" value="ipqc" />
            <el-option :label="t('production.inspections.typeOqc')" value="oqc" />
            <el-option :label="t('production.inspections.typeFai')" value="fai" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!editingId" :label="t('production.inspections.source')">
          <el-select
            v-model="form.source_id"
            filterable
            remote
            reserve-keyword
            clearable
            :remote-method="searchSources"
            :loading="sourceLoading"
            :placeholder="t('production.inspections.sourcePlaceholder')"
            style="width: 100%"
            @change="onSourceChange(selectedSource!)"
          >
            <el-option v-for="o in sourceOptions" :key="o.id" :label="o.label" :value="o.id" />
            <template #empty>
              <div class="insp-empty">{{ t('production.inspections.sourceEmpty') }}</div>
            </template>
          </el-select>
          <div v-if="selectedSource" class="insp-hint">{{ selectedSource.label }}</div>
        </el-form-item>
        <el-form-item :label="t('production.inspections.template')">
          <el-select v-model="form.template_id" filterable clearable :placeholder="t('production.inspections.templatePlaceholder')" style="width: 100%">
            <el-option v-for="tp in templateOptions" :key="tp.id" :label="`${tp.code} ${tp.name}（${tp.item_count} ${t('production.inspections.itemCountUnit')}）`" :value="tp.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('production.inspections.qty')" required>
          <el-input-number v-model="form.qty" :min="0" :controls="false" style="width: 130px" />
          <span class="insp-inline-label">{{ t('production.inspections.sampleQty') }}</span>
          <el-input-number v-model="form.sample_qty" :min="0" :controls="false" style="width: 110px" />
        </el-form-item>
        <el-form-item :label="t('production.inspections.batchNo')">
          <el-input v-model="form.batch_no" maxlength="64" style="width: 220px" />
        </el-form-item>
        <el-form-item v-if="form.inspection_type === 'iqc'" :label="t('production.inspections.objectName')">
          <el-input v-model="form.item_name" maxlength="255" :placeholder="t('production.inspections.objectPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('production.inspections.remark')">
          <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <div class="insp-hint">{{ t('production.inspections.hint') }}</div>
      <template #footer>
        <el-button @click="formVisible = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveForm">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 判定 -->
    <el-dialog v-model="judgeVisible" :title="t('production.inspections.judgeTitle')" width="560px">
      <div v-if="judgeTarget" class="insp-hint">
        {{ judgeTarget.code }} · {{ typeLabel(judgeTarget.inspection_type) }} ·
        {{ t('production.inspections.qty') }} {{ judgeTarget.qty }} ·
        {{ t('production.inspections.failedItems') }} {{ judgeTarget.item_failed }}
      </div>
      <el-form label-width="100px">
        <el-form-item :label="t('production.inspections.acceptQty')">
          <el-input-number v-model="judgeForm.accept_qty" :min="0" :controls="false" style="width: 130px" />
        </el-form-item>
        <el-form-item :label="t('production.inspections.rejectQty')">
          <el-input-number v-model="judgeForm.reject_qty" :min="0" :controls="false" style="width: 130px" />
        </el-form-item>
        <el-form-item :label="t('production.inspections.handling')">
          <el-select v-model="judgeForm.handling" clearable style="width: 220px" :placeholder="t('production.inspections.handlingPlaceholder')">
            <el-option :label="t('production.inspections.handlingReturn')" value="return" />
            <el-option :label="t('production.inspections.handlingAccept')" value="accept" />
            <el-option :label="t('production.inspections.handlingRework')" value="rework" />
            <el-option :label="t('production.inspections.handlingScrap')" value="scrap" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('production.inspections.conclusion')">
          <el-input v-model="judgeForm.conclusion" type="textarea" :rows="2" maxlength="500" :placeholder="t('production.inspections.conclusionPlaceholder')" />
        </el-form-item>
      </el-form>
      <div class="insp-hint">{{ t('production.inspections.judgeTip') }}</div>
      <template #footer>
        <el-button @click="judgeVisible = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveJudge">{{ t('production.inspections.judge') }}</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-drawer v-model="detailVisible" :title="t('production.inspections.detailTitle')" size="760px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('production.inspections.code')">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.statusLabel')">
            <el-tag :type="statusTag(detail.status)" size="small">{{ statusLabel(detail.status) }}</el-tag>
            <el-tag v-if="detail.is_closed" size="small" type="success" class="insp-tag">{{ t('production.inspections.isClosed') }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.inspectionType')">{{ typeLabel(detail.inspection_type) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.sourceCode')">{{ detail.source_code || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.objectName')" :span="2">{{ detail.item_name || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.batchNo')">{{ detail.batch_no || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.qty')">{{ detail.qty }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.sampleQty')">{{ detail.sample_qty }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.progress')">{{ detail.item_filled }}/{{ detail.item_total }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.status === 'failed' || detail.status === 'passed'" :label="t('production.inspections.acceptQty')">{{ detail.accept_qty ?? 0 }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.status === 'failed' || detail.status === 'passed'" :label="t('production.inspections.rejectQty')">{{ detail.reject_qty ?? 0 }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.handling')">{{ handlingLabel(detail.handling) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.inspector')">{{ detail.inspector_name || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.inspectedAt')">{{ fmtTime(detail.inspected_at) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.closedAt')">{{ fmtTime(detail.closed_at) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.conclusion')" :span="2">{{ detail.conclusion || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspections.remark')" :span="2">{{ detail.remark || '—' }}</el-descriptions-item>
        </el-descriptions>

        <div class="insp-detail-bar">
          <el-button v-if="canRecord && !recording" type="primary" size="small" @click="startRecord">
            {{ t('production.inspections.record') }}
          </el-button>
          <template v-if="recording">
            <el-button type="primary" size="small" :loading="saving" @click="saveRecord">{{ t('production.common.save') }}</el-button>
            <el-button size="small" @click="stopRecord">{{ t('production.common.cancel') }}</el-button>
          </template>
          <el-button v-if="canAudit && detail.status === 'pending'" type="primary" size="small" @click="openJudge(detail)">
            {{ t('production.inspections.judge') }}
          </el-button>
          <el-button size="small" @click="exportDoc(detail)">{{ t('production.inspections.exportOne') }}</el-button>
        </div>

        <el-table :data="recording ? editItems : (detail.items || [])" border size="small" class="insp-detail-table">
          <el-table-column prop="seq" :label="t('production.inspections.itemSeq')" width="55" align="center" />
          <el-table-column prop="item_name" :label="t('production.inspections.itemName')" min-width="130">
            <template #default="{ row }">
              {{ row.item_name }}
              <el-tag v-if="row.is_required" size="small" type="danger" class="insp-tag">*</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.inspections.itemStandard')" min-width="130">
            <template #default="{ row }">
              {{ row.standard_value || [row.lower_limit, row.upper_limit].filter((x: string | null) => x).join(' ~ ') || '—' }}
              {{ row.unit || '' }}
            </template>
          </el-table-column>
          <el-table-column :label="t('production.inspections.itemMeasured')" width="120">
            <template #default="{ row }">
              <el-input v-if="recording" v-model="row.measured_value" size="small" :placeholder="t('production.inspections.itemMeasured')" />
              <span v-else>{{ row.measured_value || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.inspections.itemResult')" width="110">
            <template #default="{ row }">
              <el-select v-if="recording" v-model="row.result" size="small" clearable>
                <el-option :label="t('production.inspections.resultPass')" value="pass" />
                <el-option :label="t('production.inspections.resultFail')" value="fail" />
                <el-option :label="t('production.inspections.resultNa')" value="na" />
              </el-select>
              <el-tag v-else-if="row.result" :type="row.result === 'fail' ? 'danger' : row.result === 'pass' ? 'success' : 'info'" size="small">
                {{ resultLabel(row.result) }}
              </el-tag>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.inspections.itemDefect')" width="170">
            <template #default="{ row }">
              <el-select v-if="recording && row.result === 'fail'" v-model="row.defect_code_id" size="small" filterable clearable>
                <el-option v-for="d in defectOptions" :key="d.id" :label="`${d.code} ${d.name}`" :value="d.id" />
              </el-select>
              <span v-else>{{ row.defect_code ? `${row.defect_code} ${row.defect_name || ''}` : '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.inspections.itemRemark')" min-width="110">
            <template #default="{ row }">
              <el-input v-if="recording" v-model="row.remark" size="small" />
              <span v-else>{{ row.remark || '—' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </AdminPage>
</template>

<style scoped>
.insp-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.insp-stat {
  flex: 1 1 140px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.insp-stat__label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.insp-stat__value {
  font-size: 20px;
  font-weight: 600;
}
.insp-filter {
  margin-bottom: 8px;
}
.insp-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.insp-progress-bad {
  color: var(--el-color-danger);
  font-weight: 600;
}
.insp-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.insp-inline-label {
  margin: 0 10px 0 18px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.insp-empty {
  padding: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.insp-detail-bar {
  display: flex;
  gap: 8px;
  margin: 12px 0;
}
.insp-detail-table {
  margin-top: 0;
}
.insp-tag {
  margin-left: 4px;
}
</style>
