<template>
  <AdminPage :title="t('production.equipment.title')">
    <el-card class="flex-1 flex flex-col overflow-hidden" body-class="flex-1 overflow-hidden !p-0">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-[16px] font-semibold">{{ t('production.equipment.title') }}</span>
          <div class="flex items-center gap-2">
            <el-input
              v-model="searchQuery"
              :placeholder="t('production.equipment.searchPlaceholder')"
              clearable
              style="width: 240px"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
            <el-button type="primary" @click="openCreate">{{ t('production.equipment.addEquipment') }}</el-button>
          </div>
        </div>
      </template>

      <div class="flex-1 overflow-auto p-3 min-h-0">
        <div v-loading="loading">
          <el-table class="hidden lg:block w-full" :data="filteredItems" stripe border style="width: 100%">
            <el-table-column prop="code" :label="t('production.equipment.code')" width="120" />
            <el-table-column prop="name" :label="t('production.equipment.name')" min-width="140" />
            <el-table-column prop="model" :label="t('production.equipment.model')" width="120" />
            <el-table-column prop="workshop" :label="t('production.equipment.workshop')" width="100" />
            <el-table-column prop="status" :label="t('production.equipment.status')" width="100">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_maintenance_date" :label="t('production.equipment.lastMaintenance')" width="120" />
            <el-table-column prop="next_maintenance_date" :label="t('production.equipment.nextMaintenance')" width="120" />
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openEdit(row)">{{ t('production.equipment.edit') }}</el-button>
                <el-button size="small" type="primary" plain @click="openMaintenance(row)">{{ t('production.equipment.maintenance') }}</el-button>
                <el-button size="small" type="success" @click="doCheck(row)">{{ t('production.equipment.check') }}</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="lg:hidden space-y-3">
            <div v-for="row in filteredItems" :key="row.id" class="admin-mobile-row">
              <div class="admin-mobile-row__head">
                <div class="min-w-0">
                  <div class="font-semibold text-el-primary">{{ row.name }}</div>
                  <div class="text-xs text-el-placeholder">{{ row.code }}</div>
                </div>
                <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </div>
              <dl class="admin-mobile-kv">
                <dt>{{ t('production.equipment.modelLabel') }}</dt>
                <dd>{{ row.model || '—' }}</dd>
                <dt>{{ t('production.equipment.workshopLabel') }}</dt>
                <dd>{{ row.workshop || '—' }}</dd>
                <dt>{{ t('production.equipment.maintenanceLabel') }}</dt>
                <dd class="text-left text-xs">{{ row.last_maintenance_date || '—' }} → {{ row.next_maintenance_date || '—' }}</dd>
              </dl>
              <div class="admin-mobile-actions">
                <el-button size="small" @click="openEdit(row)">{{ t('production.equipment.edit') }}</el-button>
                <el-button size="small" type="primary" plain @click="openMaintenance(row)">{{ t('production.equipment.maintenance') }}</el-button>
                <el-button size="small" type="success" @click="doCheck(row)">{{ t('production.equipment.check') }}</el-button>
              </div>
            </div>
            <el-empty v-if="!loading && !filteredItems.length" description="暂无设备" />
          </div>
        </div>
      </div>
    </el-card>

    <!-- 新增/编辑设备 -->
    <el-dialog v-model="dlg.open" :title="dlg.isEdit ? t('production.equipment.editDevice') : t('production.equipment.addDevice')" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="formRules" label-width="80px">
        <el-form-item :label="t('production.equipment.code')" prop="code">
          <el-input v-model="dlg.form.code" :disabled="dlg.isEdit" :placeholder="t('production.equipment.codePlaceholder')" clearable />
        </el-form-item>
        <el-form-item :label="t('production.equipment.name')" prop="name">
          <el-input v-model="dlg.form.name" :placeholder="t('production.equipment.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('production.equipment.model')" prop="model">
          <el-input v-model="dlg.form.model" :placeholder="t('production.equipment.modelPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('production.equipment.workshop')" prop="workshop">
          <el-input v-model="dlg.form.workshop" :placeholder="t('production.equipment.workshopPlaceholder')" />
        </el-form-item>
        <el-form-item v-if="dlg.isEdit" :label="t('production.equipment.status')" prop="status">
          <el-select v-model="dlg.form.status" :placeholder="t('production.equipment.statusPlaceholder')" style="width: 100%">
            <el-option label="正常" value="active" />
            <el-option label="维修中" value="repair" />
            <el-option label="已退役" value="retired" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="save">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 保养管理抽屉 -->
    <el-drawer v-model="maint.open" size="760px" :title="`保养管理：${maint.equipment?.name || ''}`" destroy-on-close>
      <div v-loading="maint.loading" class="space-y-4">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-medium">{{ t('production.equipment.maintenancePlan') }}</span>
              <el-button type="primary" size="small" @click="openPlanCreate">{{ t('production.equipment.addPlan') }}</el-button>
            </div>
          </template>
          <el-table :data="maint.plans" border size="small">
            <el-table-column label="类型" width="90">
              <template #default="{ row }">{{ planTypeLabel(row.plan_type) }}</template>
            </el-table-column>
            <el-table-column prop="interval_days" label="周期(天)" width="90" />
            <el-table-column prop="next_date" label="下次日期" width="120" />
            <el-table-column prop="check_items" label="检查项" min-width="140" show-overflow-tooltip />
            <el-table-column label="负责人" width="100">
              <template #default="{ row }">{{ userName(row.responsible_user_id) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openPlanEdit(row)">{{ t('production.equipment.edit') }}</el-button>
                <el-button size="small" type="success" @click="openLogCreate(row)">执行</el-button>
                <el-popconfirm title="确认删除该计划？" @confirm="deletePlan(row.id)">
                  <template #reference>
                    <el-button size="small" type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!maint.loading && !maint.plans.length" description="暂无保养计划" />
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-medium">{{ t('production.equipment.maintenanceLog') }}</span>
              <el-button size="small" @click="openLogCreate()">{{ t('production.equipment.registerMaintenance') }}</el-button>
            </div>
          </template>
          <el-table :data="maint.logs" border size="small">
            <el-table-column label="结果" width="90">
              <template #default="{ row }">
                <el-tag :type="logResultType(row.check_result)" size="small">{{ logResultLabel(row.check_result) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="说明" min-width="160" show-overflow-tooltip />
            <el-table-column label="关联计划" width="100">
              <template #default="{ row }">{{ row.plan_id ? `#${row.plan_id}` : '—' }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="170" />
          </el-table>
          <el-empty v-if="!maint.loading && !maint.logs.length" description="暂无保养记录" />
        </el-card>
      </div>
    </el-drawer>

    <!-- 保养计划弹窗 -->
    <el-dialog v-model="planDlg.open" :title="planDlg.isEdit ? '编辑保养计划' : '新增保养计划'" width="520px" destroy-on-close>
      <el-form ref="planFormRef" :model="planDlg.form" :rules="planRules" label-width="90px">
        <el-form-item label="计划类型" prop="plan_type">
          <el-select v-model="planDlg.form.plan_type" style="width: 100%">
            <el-option label="日检" value="daily" />
            <el-option label="周检" value="weekly" />
            <el-option label="月检" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item label="周期(天)" prop="interval_days">
          <el-input-number v-model="planDlg.form.interval_days" :min="1" :max="3650" style="width: 100%" />
        </el-form-item>
        <el-form-item label="下次日期" prop="next_date">
          <el-date-picker v-model="planDlg.form.next_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="负责人" prop="responsible_user_id">
          <el-select v-model="planDlg.form.responsible_user_id" clearable filterable placeholder="可选" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="检查项" prop="check_items">
          <el-input v-model="planDlg.form.check_items" type="textarea" :rows="3" placeholder="检查项说明，可多行" />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="planDlg.form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDlg.open = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="planDlg.saving" @click="savePlan">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 保养登记弹窗 -->
    <el-dialog v-model="logDlg.open" title="登记保养" width="480px" destroy-on-close>
      <el-form ref="logFormRef" :model="logDlg.form" :rules="logRules" label-width="90px">
        <el-form-item label="关联计划">
          <el-select v-model="logDlg.form.plan_id" clearable placeholder="可选" style="width: 100%">
            <el-option v-for="p in maint.plans" :key="p.id" :label="`${planTypeLabel(p.plan_type)} #${p.id}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="保养结果" prop="check_result">
          <el-select v-model="logDlg.form.check_result" style="width: 100%">
            <el-option label="合格" value="ok" />
            <el-option label="不合格" value="fail" />
            <el-option label="部分完成" value="partial" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" prop="description">
          <el-input v-model="logDlg.form.description" type="textarea" :rows="3" placeholder="保养内容、异常说明等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="logDlg.open = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="logDlg.saving" @click="saveLog">{{ t('production.equipment.submit') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import {
  equipmentApi,
  type EquipmentMaintenanceLogOut,
  type EquipmentMaintenancePlanOut,
  type EquipmentOut,
} from '@/api/equipment'
import { systemApi, type UserOut } from '@/api/system'
import { codeForSubmit, previewNextCode } from '@/utils/code'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const { label: statusLabel, type: statusTagType } = useStatus('equipment')
const loading = ref(false)
const exporting = ref(false)
const items = ref<EquipmentOut[]>([])
const users = ref<UserOut[]>([])
const searchQuery = ref('')

const filteredItems = computed(() => {
  const kw = searchQuery.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter((e) => e.code.toLowerCase().includes(kw) || e.name.toLowerCase().includes(kw))
})

async function loadUsers() {
  const res = await systemApi.listUsers({ offset: 0, limit: 200, include_inactive: false })
  users.value = res?.items ?? []
}

function userName(userId: number | null) {
  if (!userId) return '—'
  const u = users.value.find((x) => x.id === userId)
  return u?.full_name || u?.username || `#${userId}`
}

async function load() {
  loading.value = true
  try {
    const resp = await equipmentApi.list()
    items.value = resp?.items ?? []
  } finally {
    loading.value = false
  }
}

function planTypeLabel(t: string) {
  if (t === 'daily') return '日检'
  if (t === 'weekly') return '周检'
  if (t === 'monthly') return '月检'
  return t
}

function logResultLabel(r: string) {
  if (r === 'ok') return '合格'
  if (r === 'fail') return '不合格'
  if (r === 'partial') return '部分完成'
  return r
}

function logResultType(r: string): '' | 'success' | 'danger' | 'warning' {
  if (r === 'ok') return 'success'
  if (r === 'fail') return 'danger'
  return 'warning'
}

const dlg = reactive({
  open: false,
  saving: false,
  isEdit: false,
  editId: 0,
  form: { code: '', name: '', model: '', workshop: '', status: 'active' },
})
const formRef = ref<FormInstance>()
const formRules: FormRules = {
  name: [{ required: true, message: t('production.equipment.pleaseInputName'), trigger: 'blur' }],
}

function resetForm() {
  dlg.form = { code: '', name: '', model: '', workshop: '', status: 'active' }
}

async function openCreate() {
  dlg.isEdit = false
  dlg.editId = 0
  resetForm()
  dlg.form.code = await previewNextCode('equipment')
  dlg.open = true
}

function openEdit(row: EquipmentOut) {
  dlg.isEdit = true
  dlg.editId = row.id
  dlg.form = {
    code: row.code,
    name: row.name,
    model: row.model ?? '',
    workshop: row.workshop ?? '',
    status: row.status,
  }
  dlg.open = true
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    if (dlg.isEdit) {
      await equipmentApi.update(dlg.editId, {
        name: dlg.form.name,
        model: dlg.form.model || undefined,
        workshop: dlg.form.workshop || undefined,
        status: dlg.form.status,
      })
    } else {
      await equipmentApi.create({
        code: codeForSubmit(dlg.form.code),
        name: dlg.form.name,
        model: dlg.form.model || undefined,
        workshop: dlg.form.workshop || undefined,
      })
    }
    dlg.open = false
    ElMessage.success(dlg.isEdit ? t('production.equipment.deviceUpdated') : t('production.equipment.deviceCreated'))
    await load()
  } finally {
    dlg.saving = false
  }
}

async function doCheck(eq: EquipmentOut) {
  await equipmentApi.check(eq.id, { check_type: 'daily', result: 'ok' })
  ElMessage.success(t('production.equipment.checkComplete'))
  load()
}

const maint = reactive({
  open: false,
  loading: false,
  equipment: null as EquipmentOut | null,
  plans: [] as EquipmentMaintenancePlanOut[],
  logs: [] as EquipmentMaintenanceLogOut[],
})

async function loadMaintenanceData() {
  if (!maint.equipment) return
  maint.loading = true
  try {
    const [plansRes, logsRes] = await Promise.all([
      equipmentApi.listMaintenancePlans({ equipment_id: maint.equipment.id }),
      equipmentApi.listMaintenanceLogs({ equipment_id: maint.equipment.id }),
    ])
    maint.plans = plansRes?.items ?? []
    maint.logs = logsRes?.items ?? []
  } finally {
    maint.loading = false
  }
}

async function openMaintenance(row: EquipmentOut) {
  maint.equipment = row
  maint.open = true
  await loadMaintenanceData()
}

const planDlg = reactive({
  open: false,
  saving: false,
  isEdit: false,
  editId: 0,
  form: {
    plan_type: 'monthly',
    interval_days: 30,
    next_date: '',
    responsible_user_id: undefined as number | undefined,
    check_items: '',
    remark: '',
  },
})
const planFormRef = ref<FormInstance>()
const planRules: FormRules = {
  plan_type: [{ required: true, message: t('production.equipment.pleaseSelectPlanType'), trigger: 'change' }],
  interval_days: [{ required: true, message: t('production.equipment.pleaseInputCycle'), trigger: 'blur' }],
}

function resetPlanForm() {
  planDlg.form = {
    plan_type: 'monthly',
    interval_days: 30,
    next_date: '',
    responsible_user_id: undefined,
    check_items: '',
    remark: '',
  }
}

function openPlanCreate() {
  planDlg.isEdit = false
  planDlg.editId = 0
  resetPlanForm()
  planDlg.open = true
}

function openPlanEdit(row: EquipmentMaintenancePlanOut) {
  planDlg.isEdit = true
  planDlg.editId = row.id
  planDlg.form = {
    plan_type: row.plan_type,
    interval_days: row.interval_days ?? 30,
    next_date: row.next_date ?? '',
    responsible_user_id: row.responsible_user_id ?? undefined,
    check_items: row.check_items ?? '',
    remark: row.remark ?? '',
  }
  planDlg.open = true
}

async function savePlan() {
  const ok = await planFormRef.value?.validate().catch(() => false)
  if (!ok || !maint.equipment) return
  planDlg.saving = true
  try {
    const payload = {
      plan_type: planDlg.form.plan_type,
      interval_days: planDlg.form.interval_days,
      next_date: planDlg.form.next_date || undefined,
      responsible_user_id: planDlg.form.responsible_user_id,
      check_items: planDlg.form.check_items || undefined,
      remark: planDlg.form.remark || undefined,
    }
    if (planDlg.isEdit) {
      await equipmentApi.updateMaintenancePlan(planDlg.editId, payload)
    } else {
      await equipmentApi.createMaintenancePlan({ equipment_id: maint.equipment.id, ...payload })
    }
    planDlg.open = false
    ElMessage.success(planDlg.isEdit ? t('production.equipment.planUpdated') : t('production.equipment.planCreated'))
    await Promise.all([loadMaintenanceData(), load()])
  } finally {
    planDlg.saving = false
  }
}

async function deletePlan(planId: number) {
  await equipmentApi.deleteMaintenancePlan(planId)
  ElMessage.success(t('production.equipment.planDeleted'))
  await loadMaintenanceData()
}

const logDlg = reactive({
  open: false,
  saving: false,
  form: { plan_id: undefined as number | undefined, check_result: 'ok', description: '' },
})
const logFormRef = ref<FormInstance>()
const logRules: FormRules = {
  check_result: [{ required: true, message: t('production.equipment.pleaseSelectResult'), trigger: 'change' }],
}

function openLogCreate(plan?: EquipmentMaintenancePlanOut) {
  logDlg.form = {
    plan_id: plan?.id,
    check_result: 'ok',
    description: '',
  }
  logDlg.open = true
}

async function saveLog() {
  const ok = await logFormRef.value?.validate().catch(() => false)
  if (!ok || !maint.equipment) return
  logDlg.saving = true
  try {
    await equipmentApi.createMaintenanceLog({
      equipment_id: maint.equipment.id,
      plan_id: logDlg.form.plan_id,
      check_result: logDlg.form.check_result,
      description: logDlg.form.description || undefined,
    })
    logDlg.open = false
    ElMessage.success(t('production.equipment.maintenanceRegistered'))
    await Promise.all([loadMaintenanceData(), load()])
  } finally {
    logDlg.saving = false
  }
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await equipmentApi.exportEquipment({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `equipment_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(async () => {
  await Promise.all([loadUsers(), load()])
})
</script>
