<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
/** 四项基础台账共用一个配置驱动的表格 + 表单，避免四份几乎一样的页面各改各的。 */
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { basicsApi, type BasicList, type BasicOption } from '@/api/basics'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()

type Opt = { label: string; value: string | number }
type Field = {
  key: string
  label: string
  type?: 'text' | 'number' | 'date' | 'datetime' | 'select' | 'textarea' | 'bool'
  col?: boolean
  form?: boolean
  show?: string
  width?: number
  options?: Opt[]
  optionType?: string
  required?: boolean
  default?: any
}
type TabAction = {
  label: string
  type?: string
  when: (row: any) => boolean
  run: (row: any, input?: string) => Promise<any>
  prompt?: { title: string; message: string }
}
type TabCfg = {
  key: string
  label: string
  hint: string
  fields: Field[]
  list: (p: Record<string, unknown>) => Promise<BasicList>
  stats?: () => Promise<any>
  create: (d: Record<string, unknown>) => Promise<any>
  update: (id: number, d: Record<string, unknown>) => Promise<any>
  remove?: (id: number) => Promise<any>
  actions?: TabAction[]
  filters?: Field[]
}

const opt = (pairs: [string, string][]): Opt[] => pairs.map(([value, label]) => ({ value, label }))

const ECN_TYPES = opt([
  ['bom', 'BOM 变更'], ['process', '工艺变更'], ['document', '图纸/文件'], ['other', '其他'],
])
const DOWNTIME_REASONS = opt([
  ['breakdown', '设备故障'], ['changeover', '换型换模'], ['material', '待料'],
  ['quality', '质量异常'], ['maintenance', '计划保养'], ['other', '其他'],
])

const tabs: TabCfg[] = [
  {
    key: 'substitutes',
    label: '物料替代',
    hint: '替代关系只在缺料时给建议，不自动改写 BOM 行；实际领哪一颗料由仓储发料单决定。',
    fields: [
      { key: 'material_name', label: '原物料', col: true },
      { key: 'substitute_name', label: '替代料', col: true },
      { key: 'ratio', label: '替代比例', col: true, form: true, type: 'number', default: 1 },
      { key: 'priority', label: '优先级', col: true, form: true, type: 'number', default: 0 },
      { key: 'effective_from', label: '生效日期', col: true, form: true, type: 'date' },
      { key: 'effective_to', label: '失效日期', col: true, form: true, type: 'date' },
      { key: 'reason', label: '替代原因', col: true, form: true, type: 'text' },
      { key: 'is_active', label: '启用', col: true, form: true, type: 'bool', default: true },
      { key: 'material_id', label: '原物料', form: true, type: 'select', optionType: 'material', required: true },
      { key: 'substitute_material_id', label: '替代料', form: true, type: 'select', optionType: 'material', required: true },
      { key: 'bom_id', label: '限定 BOM', form: true, type: 'select', optionType: 'bom' },
      { key: 'remark', label: '备注', form: true, type: 'textarea' },
    ],
    filters: [
      { key: 'material_id', label: '原物料', type: 'select', optionType: 'material' },
    ],
    list: (p) => basicsApi.listSubstitutes(p),
    create: (d) => basicsApi.createSubstitute(d),
    update: (id, d) => basicsApi.updateSubstitute(id, d),
    remove: (id) => basicsApi.deleteSubstitute(id),
  },
  {
    key: 'ecn',
    label: '工程变更 ECN',
    hint: 'ECN 只登记变更决定与执行结果，不自动重写 BOM；状态走到「已执行」也不会悄悄改主数据。',
    fields: [
      { key: 'code', label: '变更单号', col: true, width: 170 },
      { key: 'title', label: '变更标题', col: true, form: true, type: 'text', required: true },
      { key: 'change_type', label: '类型', col: true, form: true, type: 'select', options: ECN_TYPES, default: 'bom' },
      { key: 'status', label: '状态', col: true, width: 100 },
      { key: 'sku_name', label: '产品', col: true },
      { key: 'effective_date', label: '生效日期', col: true, form: true, type: 'date' },
      { key: 'applied_at', label: '执行时间', col: true, width: 170 },
      { key: 'reason', label: '变更原因', form: true, type: 'textarea' },
      { key: 'description', label: '变更说明', form: true, type: 'textarea' },
      { key: 'before_snapshot', label: '变更前摘要', form: true, type: 'textarea' },
      { key: 'after_snapshot', label: '变更后摘要', form: true, type: 'textarea' },
      { key: 'sku_id', label: '产品型号', form: true, type: 'select', optionType: 'sku' },
      { key: 'bom_id', label: '关联 BOM', form: true, type: 'select', optionType: 'bom' },
    ],
    filters: [
      { key: 'status', label: '状态', type: 'select', options: opt([
        ['draft', '草稿'], ['pending', '待审批'], ['approved', '已批准'],
        ['rejected', '已驳回'], ['implemented', '已执行'], ['cancelled', '已作废'],
      ]) },
      { key: 'keyword', label: '单号 / 标题', type: 'text' },
    ],
    list: (p) => basicsApi.listEcn(p),
    stats: () => basicsApi.ecnStats(),
    create: (d) => basicsApi.createEcn(d),
    update: (id, d) => basicsApi.updateEcn(id, d),
    remove: (id) => basicsApi.deleteEcn(id),
    actions: [
      { label: '提交', when: (r) => ['draft', 'rejected'].includes(r.status), run: (r) => basicsApi.ecnAction(r.id, 'submit') },
      { label: '批准', type: 'primary', when: (r) => r.status === 'pending', run: (r) => basicsApi.ecnAction(r.id, 'approve') },
      {
        label: '驳回', when: (r) => r.status === 'pending',
        prompt: { title: '驳回变更单', message: '请填写驳回原因' },
        run: (r, input) => basicsApi.ecnAction(r.id, 'reject', { reason: input }),
      },
      { label: '标记执行', type: 'success', when: (r) => r.status === 'approved', run: (r) => basicsApi.ecnAction(r.id, 'implement') },
      { label: '作废', when: (r) => ['draft', 'pending'].includes(r.status), run: (r) => basicsApi.ecnAction(r.id, 'cancel') },
    ],
  },
  {
    key: 'downtimes',
    label: '设备停机',
    hint: '停机时长由起止时间自动计算，不接受手工填写；未结束的记录不进统计。',
    fields: [
      { key: 'code', label: '记录号', col: true, width: 170 },
      { key: 'equipment_name', label: '设备', col: true },
      { key: 'reason_code', label: '停机原因', col: true, form: true, type: 'select', options: DOWNTIME_REASONS, default: 'breakdown' },
      { key: 'started_at', label: '开始时间', col: true, form: true, type: 'datetime', width: 170, required: true },
      { key: 'ended_at', label: '结束时间', col: true, form: true, type: 'datetime', width: 170 },
      { key: 'duration_minutes', label: '时长(分)', col: true, width: 100 },
      { key: 'status', label: '状态', col: true, width: 100 },
      { key: 'description', label: '说明', col: true, form: true, type: 'textarea' },
      { key: 'equipment_id', label: '设备', form: true, type: 'select', optionType: 'equipment', required: true },
      { key: 'task_id', label: '关联任务 ID', form: true, type: 'number' },
    ],
    filters: [
      { key: 'equipment_id', label: '设备', type: 'select', optionType: 'equipment' },
      { key: 'status', label: '状态', type: 'select', options: opt([['open', '未结束'], ['closed', '已结束']]) },
    ],
    list: (p) => basicsApi.listDowntimes(p),
    stats: () => basicsApi.downtimeStats(),
    create: (d) => basicsApi.createDowntime(d),
    update: (id, d) => basicsApi.updateDowntime(id, d),
    remove: (id) => basicsApi.deleteDowntime(id),
    actions: [
      { label: '结束停机', type: 'primary', when: (r) => r.status === 'open', run: (r) => basicsApi.closeDowntime(r.id, {}) },
    ],
  },
  {
    key: 'scores',
    label: '供应商评分',
    hint: '权重固定：质量 40% / 交期 30% / 价格 20% / 服务 10%；总分与等级由系统算，同一供应商同一期间只能录一次。',
    fields: [
      { key: 'supplier_name', label: '供应商', col: true },
      { key: 'period', label: '期间', col: true, form: true, type: 'text', required: true },
      { key: 'quality_score', label: '质量', col: true, form: true, type: 'number', default: 0 },
      { key: 'delivery_score', label: '交期', col: true, form: true, type: 'number', default: 0 },
      { key: 'price_score', label: '价格', col: true, form: true, type: 'number', default: 0 },
      { key: 'service_score', label: '服务', col: true, form: true, type: 'number', default: 0 },
      { key: 'total_score', label: '总分', col: true },
      { key: 'grade', label: '等级', col: true, width: 80 },
      { key: 'evaluated_at', label: '评分日期', col: true, form: true, type: 'date' },
      { key: 'supplier_id', label: '供应商', form: true, type: 'select', optionType: 'supplier', required: true },
      { key: 'remark', label: '备注', form: true, type: 'textarea' },
    ],
    filters: [
      { key: 'supplier_id', label: '供应商', type: 'select', optionType: 'supplier' },
      { key: 'period', label: '期间', type: 'text' },
    ],
    list: (p) => basicsApi.listScores(p),
    stats: () => basicsApi.scoreStats(),
    create: (d) => basicsApi.createScore(d),
    update: (id, d) => basicsApi.updateScore(id, d),
    remove: (id) => basicsApi.deleteScore(id),
  },
]

const active = ref('substitutes')
const activeTab = computed(() => tabs.find((x) => x.key === active.value) || tabs[0])
const state = reactive<Record<string, { rows: any[]; total: number; loading: boolean; query: any; stats: any }>>({})
for (const tab of tabs) {
  state[tab.key] = {
    rows: [], total: 0, loading: false,
    query: { offset: 0, limit: 20, status: '', keyword: '' }, stats: null,
  }
}
const cur = computed(() => state[active.value])

const optionsMap = reactive<Record<string, BasicOption[]>>({})
const OPTION_TYPES = ['equipment', 'material', 'supplier', 'process', 'bom', 'sku']

function fieldOptions(f: Field): Opt[] {
  if (f.options) return f.options
  const list = f.optionType ? (optionsMap[f.optionType] || []) : []
  return list.map((o) => ({ label: o.label, value: o.id }))
}

function columns(tab: TabCfg) { return tab.fields.filter((f) => f.col) }
function formFields(tab: TabCfg) { return tab.fields.filter((f) => f.form) }

function cellValue(row: any, f: Field) {
  const v = row[f.show || f.key]
  if (f.key === 'is_active') return v ? '启用' : '停用'
  if (f.options) {
    const hit = f.options.find((o) => String(o.value) === String(v))
    if (hit) return hit.label
  }
  if (f.optionType && v != null) {
    const hit = (optionsMap[f.optionType] || []).find((o) => o.id === Number(v))
    if (hit) return hit.name
  }
  return v ?? '-'
}

function statusTag(v: any): string {
  const map: Record<string, string> = {
    draft: 'info', pending: 'warning', approved: 'primary', rejected: 'danger',
    implemented: 'success', cancelled: 'info', open: 'warning', closed: 'success',
  }
  return map[String(v)] || 'info'
}

async function loadOptions() {
  await Promise.all(OPTION_TYPES.map(async (type) => {
    try {
      optionsMap[type] = (await basicsApi.options(type)) || []
    } catch {
      optionsMap[type] = []
    }
  }))
}

async function load(key = active.value) {
  const tab = tabs.find((x) => x.key === key)!
  const s = state[key]
  s.loading = true
  try {
    const q: Record<string, unknown> = { offset: s.query.offset, limit: s.query.limit }
    for (const f of tab.filters || []) {
      const v = f.key === 'keyword' ? s.query.keyword : s.query[f.key]
      if (v !== '' && v !== undefined && v !== null) q[f.key] = v
    }
    const resp = await tab.list(q)
    s.rows = resp?.items || []
    s.total = resp?.total ?? s.rows.length
    if (tab.stats) {
      try { s.stats = await tab.stats() } catch { s.stats = null }
    }
  } finally {
    s.loading = false
  }
}

function onTabChange() { load() }

function onPageChange(p: number) {
  cur.value.query.offset = (p - 1) * cur.value.query.limit
  load()
}

// ── 新建 / 编辑 ──
const dialog = reactive({
  visible: false, key: '', saving: false, editing: null as any,
  form: {} as Record<string, any>,
})
const dialogTab = computed(() => tabs.find((x) => x.key === dialog.key) || tabs[0])

function defaults(tab: TabCfg): Record<string, any> {
  const d: Record<string, any> = {}
  for (const f of formFields(tab)) if (f.default !== undefined) d[f.key] = f.default
  return d
}

function openCreate() {
  dialog.key = active.value
  dialog.editing = null
  dialog.form = defaults(activeTab.value)
  dialog.visible = true
}

function openEdit(row: any) {
  dialog.key = active.value
  dialog.editing = row
  const d: Record<string, any> = {}
  for (const f of formFields(activeTab.value)) {
    const v = row[f.key]
    if (v !== undefined && v !== null) d[f.key] = v
  }
  dialog.form = d
  dialog.visible = true
}

async function save() {
  const tab = dialogTab.value
  for (const f of formFields(tab)) {
    if (f.required && (dialog.form[f.key] === '' || dialog.form[f.key] === undefined || dialog.form[f.key] === null)) {
      ElMessage.warning(`请填写「${f.label}」`)
      return
    }
  }
  dialog.saving = true
  try {
    const payload: Record<string, any> = {}
    for (const f of formFields(tab)) {
      const v = dialog.form[f.key]
      if (v !== undefined && v !== '') payload[f.key] = v
    }
    if (dialog.editing) await tab.update(dialog.editing.id, payload)
    else await tab.create(payload)
    ElMessage.success(dialog.editing ? '已保存' : '已新建')
    dialog.visible = false
    await load(dialog.key)
  } catch {
    // 拦截器已提示
  } finally {
    dialog.saving = false
  }
}

async function runAction(a: TabAction, row: any) {
  let input: string | undefined
  if (a.prompt) {
    try {
      const r = await ElMessageBox.prompt(a.prompt.message, a.prompt.title, { inputPattern: /\S/, inputErrorMessage: '不能为空' })
      input = r.value
    } catch { return }
  }
  try {
    await a.run(row, input)
    ElMessage.success(`${a.label}成功`)
    await load()
  } catch {
    // 拦截器已提示
  }
}

async function remove(row: any) {
  const tab = activeTab.value
  if (!tab.remove) return
  try {
    await ElMessageBox.confirm(`确认删除这条记录？`, '删除', { type: 'warning' })
  } catch { return }
  try {
    await tab.remove(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    // 拦截器已提示
  }
}

const canManage = computed(() => {
  const map: Record<string, string[]> = {
    substitutes: ['substitute.manage'], ecn: ['ecn.manage', 'ecn.approve'],
    downtimes: ['downtime.manage'], scores: ['supplier_score.manage'],
  }
  return auth.hasAnyPermission(map[active.value] || [])
})

onMounted(async () => {
  await loadOptions()
  await load()
})
</script>

<template>
  <AdminPage :title="t('menu.basicLedgers')">
    <template #actions>
      <el-button :loading="cur.loading" @click="load()">刷新</el-button>
      <el-button v-if="canManage" type="primary" @click="openCreate">新建</el-button>
    </template>

    <el-tabs v-model="active" @tab-change="onTabChange">
      <el-tab-pane v-for="tab in tabs" :key="tab.key" :label="tab.label" :name="tab.key" />
    </el-tabs>

    <el-alert type="info" :closable="false" show-icon class="mb-3" :title="activeTab.hint" />

    <div v-if="cur.stats" class="mb-3 text-sm text-el-regular">
      <template v-if="active === 'ecn'">共 {{ cur.stats.total }} 张，待审批 {{ cur.stats.pending }}，已执行 {{ cur.stats.implemented }}</template>
      <template v-else-if="active === 'downtimes'">已结束 {{ cur.stats.count }} 次，累计停机 {{ cur.stats.total_minutes }} 分钟</template>
      <template v-else-if="active === 'scores'">共 {{ cur.stats.total }} 条评分，平均分 {{ cur.stats.avg_score ?? '-' }}</template>
    </div>

    <el-form :inline="true" class="mb-2" @submit.prevent="load()">
      <el-form-item v-for="f in (activeTab.filters || [])" :key="f.key" :label="f.label">
        <el-select v-if="f.type === 'select'" v-model="cur.query[f.key]" clearable filterable style="width: 180px">
          <el-option v-for="o in fieldOptions(f)" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-input v-else v-model="cur.query[f.key]" clearable style="width: 180px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="cur.query.offset = 0; load()">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="cur.rows" v-loading="cur.loading" border stripe size="small">
      <el-table-column v-for="f in columns(activeTab)" :key="f.key" :prop="f.key" :label="f.label"
        :width="f.width" :min-width="f.width ? undefined : 120" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="f.key === 'status'" :type="(statusTag(row[f.key]) as any)" size="small">
            {{ cellValue(row, f) }}
          </el-tag>
          <el-tag v-else-if="f.key === 'grade'" :type="row.grade === 'A' ? 'success' : 'info'" size="small">
            {{ row.grade }}
          </el-tag>
          <span v-else>{{ cellValue(row, f) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" :width="activeTab.actions ? 300 : 150" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canManage" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button v-for="a in (activeTab.actions || []).filter((x) => x.when(row))" :key="a.label"
            v-show="canManage" size="small" :type="(a.type as any) || undefined" @click="runAction(a, row)">
            {{ a.label }}
          </el-button>
          <el-button v-if="canManage && activeTab.remove" size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="mt-3 flex justify-end">
      <el-pagination background layout="total, prev, pager, next" :total="cur.total"
        :page-size="cur.query.limit" :current-page="Math.floor(cur.query.offset / cur.query.limit) + 1"
        @current-change="onPageChange" />
    </div>

    <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑记录' : '新建记录'" width="640px">
      <el-form label-width="120px">
        <el-form-item v-for="f in formFields(dialogTab)" :key="f.key" :label="f.label" :required="f.required">
          <el-select v-if="f.type === 'select'" v-model="dialog.form[f.key]" clearable filterable style="width: 100%">
            <el-option v-for="o in fieldOptions(f)" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <el-switch v-else-if="f.type === 'bool'" v-model="dialog.form[f.key]" />
          <el-input-number v-else-if="f.type === 'number'" v-model="dialog.form[f.key]" :min="0" :controls="false" style="width: 100%" />
          <el-date-picker v-else-if="f.type === 'date'" v-model="dialog.form[f.key]" type="date"
            value-format="YYYY-MM-DD" style="width: 100%" />
          <el-date-picker v-else-if="f.type === 'datetime'" v-model="dialog.form[f.key]" type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
          <el-input v-else-if="f.type === 'textarea'" v-model="dialog.form[f.key]" type="textarea" :rows="2" />
          <el-input v-else v-model="dialog.form[f.key]" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>
