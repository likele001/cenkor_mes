<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  productionApi,
  type LedgerRow,
  type LedgerStats,
} from '@/api/production'
import { masterApi } from '@/api/master'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<LedgerRow[]>([])
const total = ref(0)
const stats = ref<LedgerStats | null>(null)

const query = reactive({
  result: '' as '' | 'pass' | 'fail' | 'na',
  process_id: null as number | null,
  defect_code_id: null as number | null,
  dateRange: [] as string[],
  keyword: '',
  offset: 0,
  limit: 20,
})

const processOptions = ref<{ id: number; code: string; name: string }[]>([])
const defectOptions = ref<{ id: number; code: string; name: string }[]>([])

function resultLabel(v: string | null) {
  if (!v) return '—'
  const map: Record<string, string> = {
    pass: t('production.inspections.resultPass'),
    fail: t('production.inspections.resultFail'),
    na: t('production.inspections.resultNa'),
  }
  return map[v] || v
}

function resultTag(v: string | null): 'success' | 'danger' | 'info' {
  if (v === 'pass') return 'success'
  if (v === 'fail') return 'danger'
  return 'info'
}

function severityTag(v: string | null): 'danger' | 'warning' | 'info' {
  if (v === 'critical') return 'danger'
  if (v === 'major') return 'warning'
  return 'info'
}

function fmtTime(v: string | null) {
  return v ? v.replace('T', ' ').slice(0, 19) : '—'
}

function buildParams(extra: Record<string, unknown> = {}) {
  const params: Record<string, unknown> = { ...extra }
  if (query.result) params.result = query.result
  if (query.process_id) params.process_id = query.process_id
  if (query.defect_code_id) params.defect_code_id = query.defect_code_id
  if (query.dateRange?.length === 2) {
    params.date_from = query.dateRange[0]
    params.date_to = query.dateRange[1]
  }
  if (query.keyword.trim()) params.keyword = query.keyword.trim()
  return params
}

async function load() {
  loading.value = true
  try {
    const data = await productionApi.listInspectionLedger(
      buildParams({ offset: query.offset, limit: query.limit }),
    )
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
    stats.value = await productionApi.inspectionLedgerStats(
      buildParams() as { date_from?: string; date_to?: string },
    )
  } catch {
    stats.value = null
  }
}

function search() {
  query.offset = 0
  load()
  loadStats()
}

function resetQuery() {
  query.result = ''
  query.process_id = null
  query.defect_code_id = null
  query.dateRange = []
  query.keyword = ''
  query.offset = 0
  load()
  loadStats()
}

function onPageChange(page: number) {
  query.offset = (page - 1) * query.limit
  load()
}

async function exportLedger() {
  try {
    const blob = await productionApi.exportInspectionLedger(buildParams())
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'inspection_ledger.xlsx'
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
    const p = await masterApi.listProcesses({ offset: 0, limit: 300 })
    processOptions.value = (p.items || []).map((x: any) => ({ id: x.id, code: x.code, name: x.name }))
  } catch {
    processOptions.value = []
  }
  try {
    const d = await productionApi.listDefectCodes()
    defectOptions.value = (d.items || []).map((x) => ({ id: x.id, code: x.code, name: x.name }))
  } catch {
    defectOptions.value = []
  }
}

// ── 详情 ──
const detailVisible = ref(false)
const detail = ref<LedgerRow | null>(null)

function viewDetail(row: LedgerRow) {
  detail.value = row
  detailVisible.value = true
}
</script>

<template>
  <AdminPage :title="t('production.inspectionLedger.title')">
    <template #actions>
      <el-button :loading="loading" @click="load">{{ t('production.inspectionLedger.refresh') }}</el-button>
      <el-button @click="exportLedger">{{ t('production.inspectionLedger.export') }}</el-button>
    </template>

    <div class="led-stats">
      <div class="led-stat">
        <span class="led-stat__label">{{ t('production.inspectionLedger.statsTotal') }}</span>
        <span class="led-stat__value">{{ stats?.total ?? 0 }}</span>
      </div>
      <div class="led-stat">
        <span class="led-stat__label">{{ t('production.inspectionLedger.statsFailed') }}</span>
        <span class="led-stat__value">{{ stats?.failed ?? 0 }}</span>
      </div>
      <div class="led-stat">
        <span class="led-stat__label">{{ t('production.inspectionLedger.statsPassRate') }}</span>
        <span class="led-stat__value">{{ stats?.pass_rate == null ? '—' : `${stats.pass_rate}%` }}</span>
      </div>
      <div class="led-stat led-stat--wide">
        <span class="led-stat__label">{{ t('production.inspectionLedger.statsBySeverity') }}</span>
        <span class="led-stat__value led-stat__chips">
          <el-tag
            v-for="(cnt, sev) in stats?.by_severity || {}"
            :key="sev"
            :type="severityTag(String(sev))"
            size="small"
            class="led-chip"
          >{{ String(sev) }} × {{ cnt }}</el-tag>
          <span v-if="!stats || !Object.keys(stats.by_severity || {}).length">—</span>
        </span>
      </div>
    </div>

    <el-form inline class="led-filter" @submit.prevent="search">
      <el-form-item :label="t('production.inspectionLedger.result')">
        <el-select v-model="query.result" clearable style="width: 120px" @change="search">
          <el-option :label="t('production.inspections.resultPass')" value="pass" />
          <el-option :label="t('production.inspections.resultFail')" value="fail" />
          <el-option :label="t('production.inspections.resultNa')" value="na" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('production.inspectionLedger.process')">
        <el-select v-model="query.process_id" filterable clearable style="width: 160px" @change="search">
          <el-option v-for="p in processOptions" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('production.inspectionLedger.defect')">
        <el-select v-model="query.defect_code_id" filterable clearable style="width: 180px" @change="search">
          <el-option v-for="d in defectOptions" :key="d.id" :label="`${d.code} ${d.name}`" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('production.inspectionLedger.dateRange')">
        <el-date-picker
          v-model="query.dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          :start-placeholder="t('production.inspectionLedger.dateFrom')"
          :end-placeholder="t('production.inspectionLedger.dateTo')"
          style="width: 240px"
          @change="search"
        />
      </el-form-item>
      <el-form-item :label="t('production.inspectionLedger.keyword')">
        <el-input v-model="query.keyword" :placeholder="t('production.inspectionLedger.keywordPlaceholder')" clearable style="width: 200px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">{{ t('production.inspectionLedger.search') }}</el-button>
        <el-button @click="resetQuery">{{ t('production.inspectionLedger.reset') }}</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="rows" border class="w-full">
      <el-table-column :label="t('production.inspectionLedger.recordedAt')" width="160">
        <template #default="{ row }">
          <el-link type="primary" @click="viewDetail(row)">{{ fmtTime(row.recorded_at) }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="item_name" :label="t('production.inspectionLedger.itemName')" min-width="130" show-overflow-tooltip />
      <el-table-column :label="t('production.inspectionLedger.result')" width="90">
        <template #default="{ row }">
          <el-tag :type="resultTag(row.result)" size="small">{{ resultLabel(row.result) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('production.inspectionLedger.measured')" width="100">
        <template #default="{ row }">
          <span v-if="row.measured_value">{{ row.measured_value }}{{ row.unit || '' }}</span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('production.inspectionLedger.defect')" min-width="140">
        <template #default="{ row }">
          <template v-if="row.defect_code">
            <el-tag :type="severityTag(row.defect_severity)" size="small" class="led-chip">{{ row.defect_severity }}</el-tag>
            {{ row.defect_code }} {{ row.defect_name || '' }}
          </template>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column prop="task_code" :label="t('production.inspectionLedger.taskCode')" width="130" />
      <el-table-column prop="process_name" :label="t('production.inspectionLedger.process')" width="110">
        <template #default="{ row }">{{ row.process_name || '—' }}</template>
      </el-table-column>
      <el-table-column :label="t('production.inspectionLedger.sku')" min-width="140">
        <template #default="{ row }">{{ [row.sku_code, row.sku_name].filter(Boolean).join(' ') || '—' }}</template>
      </el-table-column>
      <el-table-column prop="unit_seq" :label="t('production.inspectionLedger.unitSeq')" width="70" align="center" />
      <el-table-column prop="audit_level" :label="t('production.inspectionLedger.auditLevel')" width="90" align="center" />
    </el-table>

    <div class="led-pager">
      <el-pagination
        layout="total, prev, pager, next"
        :total="total"
        :page-size="query.limit"
        :current-page="Math.floor(query.offset / query.limit) + 1"
        @current-change="onPageChange"
      />
    </div>

    <!-- 详情 -->
    <el-drawer v-model="detailVisible" :title="t('production.inspectionLedger.detailTitle')" size="560px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('production.inspectionLedger.recordedAt')">{{ fmtTime(detail.recorded_at) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.result')">
            <el-tag :type="resultTag(detail.result)" size="small">{{ resultLabel(detail.result) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.itemName')" :span="2">{{ detail.item_name || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.itemStandard')" :span="2">
            {{ detail.standard_value || [detail.lower_limit, detail.upper_limit].filter(Boolean).join(' ~ ') || '—' }}
            {{ detail.unit || '' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.measured')">{{ detail.measured_value ? detail.measured_value + (detail.unit || '') : '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.defect')">
            {{ detail.defect_code ? `${detail.defect_code} ${detail.defect_name || ''}（${detail.defect_severity}）` : '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.taskCode')">{{ detail.task_code || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.process')">{{ detail.process_name || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.sku')" :span="2">
            {{ [detail.sku_code, detail.sku_name].filter(Boolean).join(' ') || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.unitSeq')">{{ detail.unit_seq ?? '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.auditLevel')">{{ detail.audit_level || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.inspectionLedger.remark')" :span="2">{{ detail.remark || '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </AdminPage>
</template>

<style scoped>
.led-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.led-stat {
  flex: 1 1 140px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.led-stat--wide {
  flex: 2 1 280px;
}
.led-stat__label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.led-stat__value {
  font-size: 20px;
  font-weight: 600;
}
.led-stat__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  font-size: 13px;
  font-weight: 400;
}
.led-filter {
  margin-bottom: 8px;
}
.led-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.led-chip {
  margin-right: 4px;
}
</style>
