<template>
  <AdminPage :title="t('production.tasks.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-input
            v-model="query.keyword"
            ::placeholder="t('production.tasks.searchPlaceholder')"
            clearable
            style="width: 280px"
            @keyup.enter="reload(true)"
            @clear="reload(true)"
          />
          <el-select v-model="query.status" clearable ::placeholder="t('production.common.status')" style="width: 130px" @change="reload(true)">
            <el-option :label="t('production.tasks.all')" value="" />
            <el-option :label="t('production.tasks.pending')" value="pending" />
            <el-option :label="t('production.tasks.working')" value="working" />
            <el-option :label="t('production.tasks.done')" value="done" />
          </el-select>
          <el-button type="primary" @click="reload(true)">{{ t('production.tasks.search') }}</el-button>
          <el-button v-if="canDispatch" :disabled="!selectedTaskIds.length" type="primary" plain @click="batchPrintLabels">
            批量打印({{ selectedTaskIds.length }})
          </el-button>
          <el-button @click="reload(true)">{{ t('production.common.refresh') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border @selection-change="onSelectionChange">
          <el-table-column type="selection" width="46" />
          <el-table-column :label="t('production.tasks.taskCode')" min-width="150">
            <template #default="{ row }">
              <span class="font-mono text-sm font-medium">{{ row.task_code }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.tasks.order')" min-width="140">
            <template #default="{ row }">
              <div class="font-medium">{{ row.order?.code || '—' }}</div>
              <div v-if="row.order?.customer_name" class="text-xs text-el-placeholder">{{ row.order.customer_name }}</div>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.tasks.productSku')" min-width="200">
            <template #default="{ row }">
              {{ row.sku?.display_label || row.work_order?.sku_display_label || skuRowLabel({ sku: row.sku }) || '—' }}
            </template>
          </el-table-column>
          <el-table-column :label="t('production.tasks.process')" min-width="140">
            <template #default="{ row }">
              <span>{{ processRowLabel({ process: row.process }) }}</span>
              <span class="text-xs text-el-placeholder ml-1">#{{ row.seq }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="planned_qty" :label="t('production.tasks.plannedQty')" width="90" align="center" />
          <el-table-column :label="t('production.common.status')" width="100">
            <template #default="{ row }">
              <el-tag :type="taskStatusType(row.status)" size="small">{{ taskStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="派工" min-width="140">
            <template #default="{ row }">
              <span v-if="row.assignments?.length">
                {{ row.assignments.length }}人 / {{ row.assigned_total_qty ?? 0 }}/{{ row.planned_qty }}
              </span>
              <span v-else class="text-el-placeholder">{{ t('production.tasks.notAssigned') }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.tasks.equipment')" width="160">
            <template #default="{ row }">
              {{ row.equipment ? equipmentOptionLabel(row.equipment) : row.equipment_id ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="assigned_at" :label="t('production.tasks.dispatchTime')" width="180" />
          <el-table-column :label="t('production.common.operation')" width="320">
            <template #default="{ row }">
              <el-button v-if="canDispatch" size="small" type="primary" @click="openAssign(row)">{{ t('production.tasks.assign') }}</el-button>
              <el-button v-if="canDispatch" size="small" type="success" @click="printLabel(row)">{{ t('production.tasks.printLabel') }}</el-button>
              <el-button v-if="canDispatch" size="small" type="warning" @click="exportLabelPdf(row)">{{ t('production.tasks.exportPdf') }}</el-button>
              <el-button v-if="canDispatch" size="small" type="danger" :disabled="!row.assignments?.length" @click="cancelAssign(row)">
                取消派工
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="flex items-start gap-2 min-w-0 flex-1">
                <el-checkbox
                  v-if="canDispatch"
                  :model-value="selectedTaskIds.includes(row.id)"
                  @update:model-value="(v: string | number | boolean) => toggleSelectTask(row.id, Boolean(v))"
                />
                <div class="min-w-0">
                  <div class="font-semibold text-el-primary font-mono text-sm">{{ row.task_code }}</div>
                  <div class="text-xs text-el-placeholder">
                    {{ row.order?.code || '—' }}
                    <span v-if="row.order?.customer_name"> · {{ row.order.customer_name }}</span>
                  </div>
                </div>
              </div>
              <el-tag :type="taskStatusType(row.status)" size="small">{{ taskStatusLabel(row.status) }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('production.tasks.model') }}</dt>
              <dd>{{ row.sku?.display_label || skuRowLabel({ sku: row.sku }) || '—' }}</dd>
              <dt>{{ t('production.tasks.processLabel') }}</dt>
              <dd>{{ processRowLabel({ process: row.process }) }}（序 {{ row.seq }}）</dd>
              <dt>{{ t('production.tasks.plannedQtyLabel') }}</dt>
              <dd>{{ row.planned_qty }}</dd>
              <dt>{{ t('production.tasks.assign') }}</dt>
              <dd>
                {{
                  row.assignments?.length
                    ? `${row.assignments.length}人 ${row.assigned_total_qty}/${row.planned_qty}`
                    : '—'
                }}
              </dd>
              <dt>{{ t('production.tasks.equipmentLabel') }}</dt>
              <dd>{{ row.equipment ? equipmentOptionLabel(row.equipment) : row.equipment_id ?? '—' }}</dd>
              <dt>{{ t('production.tasks.dispatchTimeLabel') }}</dt>
              <dd>{{ row.assigned_at || '—' }}</dd>
            </dl>
            <div v-if="canDispatch" class="admin-mobile-actions">
              <el-button size="small" type="primary" @click="openAssign(row)">{{ t('production.tasks.assign') }}</el-button>
              <el-button size="small" type="success" @click="printLabel(row)">打印</el-button>
              <el-button size="small" type="warning" @click="exportLabelPdf(row)">PDF</el-button>
              <el-button size="small" type="danger" :disabled="!row.assignments?.length" @click="cancelAssign(row)">{{ t('production.tasks.cancelAssign') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" description="暂无数据" />
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :page-size="query.limit"
          :total="fakeTotal"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    <template #extra>
    <el-dialog v-model="assign.open" :title="t('production.tasks.assignTitle')" width="720px" destroy-on-close>
      <el-alert
        class="mb-3"
        type="info"
        :closable="false"
        :title="t('production.tasks.assignDescription')"
        description="派工后：① 点任务行「打印标签」贴工位（员工可微信扫标签）；② 员工手机 H5「我的任务」→ 任务详情里有「我的报工码」。"
      />
      <el-form label-width="96px">
        <el-form-item label="任务">
          <span class="font-mono">{{ assign.taskCode || assign.taskId }}</span>
          <span class="ml-2 text-el-regular">{{ assign.taskSummary }}</span>
          <span class="ml-3 text-el-placeholder">
            已派 {{ assignAssignedTotal }} / 计划 {{ assign.plannedQty }}
          </span>
        </el-form-item>
        <el-form-item label="技能筛选">
          <el-select
            v-model="assign.skillIds"
            multiple
            filterable
            clearable
            :loading="assign.loadingSkills"
            :placeholder="t('production.tasks.skillPlaceholder')"
            style="width: 100%"
            @change="reloadUsers"
          >
            <el-option v-for="s in assign.skills" :key="s.id" :label="`${s.name}（${s.code}）`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="派工明细">
          <div class="w-full">
            <el-table :data="assign.rows" border size="small" empty-text="点击下方添加员工">
              <el-table-column label="员工" min-width="220">
                <template #default="{ row }">
                  <el-select
                    v-model="row.user_id"
                    filterable
                    remote
                    :remote-method="onUserSearch"
                    :loading="assign.loadingUsers"
                    :placeholder="t('production.tasks.employeePlaceholder')"
                    style="width: 100%"
                  >
                    <el-option v-for="u in assign.users" :key="u.id" :label="userLabel(u)" :value="u.id" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="派工数" width="130">
                <template #default="{ row }">
                  <el-input-number v-model="row.assigned_qty" :min="1" :max="assign.plannedQty" controls-position="right" style="width: 110px" />
                </template>
              </el-table-column>
              <el-table-column label="已报" width="80">
                <template #default="{ row }">
                  {{ row.reported_qty ?? 0 }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="70">
                <template #default="{ $index }">
                  <el-button link type="danger" @click="removeAssignRow($index)">删</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-button class="mt-2" size="small" @click="addAssignRow">+ 添加员工</el-button>
          </div>
        </el-form-item>
        <el-form-item label="选择设备">
          <el-select
            v-model="assign.equipmentId"
            filterable
            clearable
            :loading="assign.loadingEquipments"
            :placeholder="t('production.tasks.equipmentPlaceholder')"
            style="width: 100%"
          >
            <el-option v-for="e in assign.equipments" :key="e.id" :label="equipmentOptionLabel(e)" :value="e.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assign.open = false">取消</el-button>
        <el-button type="primary" :loading="assign.saving" @click="doAssign">{{ t('production.tasks.saveAssign') }}</el-button>
      </template>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi, type TaskOut, type UserOut } from '@/api/production'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/utils/http'
import { openPrintWindow } from '@/utils/print'
import { equipmentOptionLabel, processRowLabel, skuRowLabel } from '@/utils/display'

const { t } = useI18n()
const auth = useAuthStore()
const canDispatch = computed(() => auth.hasAnyPermission(['dispatch.manage']))

const loading = ref(false)
const items = ref<TaskOut[]>([])
const selectedTaskIds = ref<number[]>([])
const query = reactive({ keyword: '', status: '', offset: 0, limit: 50 })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

type AssignRow = { user_id: number | null; assigned_qty: number; reported_qty?: number }

const assign = reactive({
  open: false,
  taskId: null as number | null,
  taskCode: '',
  taskSummary: '',
  plannedQty: 0,
  equipmentId: null as number | null,
  userKeyword: '',
  skillIds: [] as number[],
  rows: [] as AssignRow[],
  saving: false,
  loadingUsers: false,
  users: [] as UserOut[],
  loadingSkills: false,
  skills: [] as { id: number; code: string; name: string }[],
  loadingEquipments: false,
  equipments: [] as { id: number; code: string; name: string }[],
})

const assignAssignedTotal = computed(() =>
  assign.rows.reduce((s, r) => s + (r.user_id ? Number(r.assigned_qty) || 0 : 0), 0),
)

function userLabel(u: UserOut) {
  if (u.full_name) return `${u.full_name}（${u.username}）`
  return u.username
}

function taskStatusLabel(s: string | undefined) {
  if (s === 'pending') return '待开始'
  if (s === 'working') return '进行中'
  if (s === 'done') return '已完成'
  return s || '—'
}

function taskStatusType(s: string | undefined) {
  if (s === 'pending') return 'info'
  if (s === 'working') return 'warning'
  if (s === 'done') return 'success'
  return 'info'
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await productionApi.listTasks({
      keyword: query.keyword.trim() || undefined,
      status: query.status || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items
    selectedTaskIds.value = []
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

function onSelectionChange(rows: TaskOut[]) {
  selectedTaskIds.value = (rows || []).map((x) => x.id)
}

function toggleSelectTask(id: number, checked: boolean) {
  const set = new Set(selectedTaskIds.value)
  if (checked) set.add(id)
  else set.delete(id)
  selectedTaskIds.value = [...set]
}

async function loadUsers(keyword: string) {
  assign.userKeyword = keyword
  assign.loadingUsers = true
  try {
    const res = await productionApi.listDispatchUsers({
      keyword: keyword || undefined,
      skill_ids: assign.skillIds.length ? assign.skillIds.join(',') : undefined,
      match: 'all',
      offset: 0,
      limit: 50,
    })
    assign.users = res.items
  } finally {
    assign.loadingUsers = false
  }
}

function onUserSearch(keyword: string) {
  loadUsers(keyword)
}

async function loadSkills() {
  assign.loadingSkills = true
  try {
    const res = await productionApi.listDispatchSkills({ keyword: undefined })
    assign.skills = res.items ?? []
  } finally {
    assign.loadingSkills = false
  }
}

function reloadUsers() {
  loadUsers(assign.userKeyword || '')
}

function addAssignRow() {
  assign.rows.push({ user_id: null, assigned_qty: 1, reported_qty: 0 })
}

function removeAssignRow(idx: number) {
  assign.rows.splice(idx, 1)
}

async function openAssign(row: TaskOut) {
  assign.taskId = row.id
  assign.taskCode = row.task_code
  assign.taskSummary = [
    row.order?.code,
    row.order?.customer_name,
    row.sku?.display_label || skuRowLabel({ sku: row.sku }),
    processRowLabel({ process: row.process }),
  ]
    .filter(Boolean)
    .join(' · ')
  assign.plannedQty = row.planned_qty
  assign.equipmentId = row.equipment_id ?? null
  assign.skillIds = []
  assign.rows = []
  assign.open = true
  if (!assign.skills.length) loadSkills()
  loadUsers('')
  loadEquipments()
  try {
    const res = await productionApi.getTaskAssignments(row.id)
    assign.plannedQty = res.planned_qty
    assign.rows = (res.items || []).map((x) => ({
      user_id: x.user_id,
      assigned_qty: x.assigned_qty,
      reported_qty: x.reported_qty ?? 0,
    }))
    for (const it of res.items || []) {
      if (it.user && !assign.users.find((u) => u.id === it.user!.id)) {
        assign.users.push({
          id: it.user.id,
          username: it.user.username,
          full_name: it.user.full_name,
        } as UserOut)
      }
    }
  } catch {
    assign.rows = (row.assignments || []).map((x) => ({
      user_id: x.user_id,
      assigned_qty: x.assigned_qty,
      reported_qty: x.reported_qty ?? 0,
    }))
  }
  if (!assign.rows.length) addAssignRow()
}

async function loadEquipments() {
  assign.loadingEquipments = true
  try {
    const resp = await http.request<any>({ url: '/admin/equipment', method: 'GET' })
    assign.equipments = resp?.items ?? []
  } finally {
    assign.loadingEquipments = false
  }
}

async function doAssign() {
  if (!assign.taskId) return
  const items = assign.rows
    .filter((r) => r.user_id)
    .map((r) => ({ user_id: Number(r.user_id), assigned_qty: Number(r.assigned_qty) }))
  const ids = items.map((x) => x.user_id)
  if (new Set(ids).size !== ids.length) {
    ElMessage.warning('同一员工不能重复派工')
    return
  }
  if (assignAssignedTotal.value > assign.plannedQty) {
    ElMessage.warning(`派工合计不能超过计划数 ${assign.plannedQty}`)
    return
  }
  for (const r of assign.rows) {
    if (r.user_id && (r.reported_qty ?? 0) > Number(r.assigned_qty)) {
      ElMessage.warning(`员工#${r.user_id} 派工数不能小于已报工数`)
      return
    }
  }
  assign.saving = true
  try {
    await productionApi.setTaskAssignments(assign.taskId, { items, equipment_id: assign.equipmentId })
    assign.open = false
    ElMessage.success('派工已保存：请打印任务标签，或让员工在 H5「我的任务」查看报工码')
    await reload(false)
  } finally {
    assign.saving = false
  }
}

async function cancelAssign(row: TaskOut) {
  const ok = await ElMessageBox.confirm('确认取消该任务全部派工？', '提示', { type: 'warning' })
    .then(() => true)
    .catch(() => false)
  if (!ok) return
  await productionApi.setTaskAssignments(row.id, { items: [], equipment_id: null })
  await reload(false)
}

async function printLabel(row: TaskOut) {
  const resp = await productionApi.renderTaskLabel(row.id, { template_code: 'task_label' })
  const html = resp?.html || ''
  if (!html) return
  openPrintWindow(html, { title: `task_label_${row.id}`, autoPrint: true })
}

async function exportLabelPdf(row: TaskOut) {
  const res = await productionApi.exportTaskLabelPdf(row.id, { template_code: 'task_label' })
  const blob = await http.request<Blob>({ url: `/files/${res.attachment_id}`, method: 'GET', params: { download: true }, responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = res.filename || `task_label_${row.id}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

async function batchPrintLabels() {
  if (!selectedTaskIds.value.length) return
  const ok = await ElMessageBox.confirm(`确认批量打印 ${selectedTaskIds.value.length} 张任务标签？`, '提示', { type: 'warning' })
    .then(() => true)
    .catch(() => false)
  if (!ok) return
  const res = await productionApi.renderTaskLabelBatch({ task_ids: selectedTaskIds.value, template_code: 'task_label' })
  if (!res?.html) return
  openPrintWindow(res.html, { title: `task_label_batch_${Date.now()}`, autoPrint: true })
}

onMounted(() => reload(true))
</script>
