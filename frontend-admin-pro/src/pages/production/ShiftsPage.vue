<template>
  <AdminPage :title="t('system.shifts.title')">
    <template #actions>
      <el-button type="primary" @click="openShiftCreate">{{ t('system.shifts.addShift') }}</el-button>
      <el-button @click="openScheduleCreate">{{ t('system.shifts.addSchedule') }}</el-button>
      <el-button @click="openBatchSchedule">{{ t('system.shifts.batchSchedule') }}</el-button>
      <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
    </template>

    <el-tabs v-model="activeTab" class="flex-1 flex flex-col overflow-hidden">
      <!-- 班次管理 -->
      <el-tab-pane :label="t('system.shifts.shiftList')" name="shifts">
        <div v-loading="shiftLoading" class="overflow-auto" style="max-height: calc(100vh - 280px)">
          <el-table class="w-full" :data="shifts" border stripe>
            <el-table-column prop="code" :label="t('system.shifts.code')" width="120" />
            <el-table-column prop="name" :label="t('system.shifts.name')" width="120" />
            <el-table-column :label="t('system.shifts.timeRange')" width="180">
              <template #default="{ row }">{{ row.start_time }} ~ {{ row.end_time }}</template>
            </el-table-column>
            <el-table-column prop="rest_minutes" :label="t('system.shifts.restMinutes')" width="100" />
            <el-table-column :label="t('system.shifts.shiftType')" width="100">
              <template #default="{ row }">{{ shiftTypeLabel(row.shift_type) }}</template>
            </el-table-column>
            <el-table-column :label="t('system.shifts.status')" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status === 'active' ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remark" :label="t('system.shifts.remark')" min-width="120" show-overflow-tooltip />
            <el-table-column :label="t('system.shifts.operation')" width="180" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openShiftEdit(row)">{{ t('system.shifts.edit') }}</el-button>
                <el-popconfirm :title="t('system.shifts.confirmDelete')" @confirm="deleteShift(row.id)">
                  <template #reference>
                    <el-button size="small" type="danger">{{ t('system.shifts.delete') }}</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!shiftLoading && !shifts.length" :description="t('system.shifts.noShifts')" />
        </div>
      </el-tab-pane>

      <!-- 排班管理 -->
      <el-tab-pane :label="t('system.shifts.scheduleList')" name="schedules">
        <div class="flex items-center gap-2 mb-3">
          <el-date-picker
            v-model="scheduleDateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            :start-placeholder="t('system.shifts.startDate')"
            :end-placeholder="t('system.shifts.endDate')"
            @change="loadSchedules"
          />
          <el-select v-model="scheduleUserFilter" clearable filterable :placeholder="t('system.shifts.filterUser')" style="width: 200px" @change="loadSchedules">
            <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </div>
        <div v-loading="scheduleLoading" class="overflow-auto" style="max-height: calc(100vh - 340px)">
          <el-table class="w-full" :data="schedules" border stripe>
            <el-table-column prop="work_date" :label="t('system.shifts.workDate')" width="120" />
            <el-table-column prop="user_name" :label="t('system.shifts.employee')" width="120" />
            <el-table-column prop="shift_name" :label="t('system.shifts.shiftName')" width="120" />
            <el-table-column prop="remark" :label="t('system.shifts.remark')" min-width="120" show-overflow-tooltip />
            <el-table-column :label="t('system.shifts.operation')" width="100" fixed="right">
              <template #default="{ row }">
                <el-popconfirm :title="t('system.shifts.confirmDeleteSchedule')" @confirm="deleteSchedule(row.id)">
                  <template #reference>
                    <el-button size="small" type="danger">{{ t('system.shifts.delete') }}</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!scheduleLoading && !schedules.length" :description="t('system.shifts.noSchedules')" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 班次新增/编辑弹窗 -->
    <el-dialog v-model="shiftDlg.open" :title="shiftDlg.isEdit ? t('system.shifts.editShift') : t('system.shifts.addShift')" width="520px" destroy-on-close>
      <el-form ref="shiftFormRef" :model="shiftDlg.form" :rules="shiftRules" label-width="100px">
        <el-form-item :label="t('system.shifts.code')" prop="code">
          <el-input v-model="shiftDlg.form.code" :disabled="shiftDlg.isEdit" :placeholder="t('system.shifts.codePlaceholder')" clearable />
        </el-form-item>
        <el-form-item :label="t('system.shifts.name')" prop="name">
          <el-input v-model="shiftDlg.form.name" :placeholder="t('system.shifts.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('system.shifts.startTime')" prop="start_time">
          <el-time-picker v-model="shiftDlg.form.start_time" format="HH:mm" value-format="HH:mm" :placeholder="t('system.shifts.startTimePlaceholder')" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('system.shifts.endTime')" prop="end_time">
          <el-time-picker v-model="shiftDlg.form.end_time" format="HH:mm" value-format="HH:mm" :placeholder="t('system.shifts.endTimePlaceholder')" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('system.shifts.restMinutes')" prop="rest_minutes">
          <el-input-number v-model="shiftDlg.form.rest_minutes" :min="0" :max="480" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('system.shifts.shiftType')" prop="shift_type">
          <el-select v-model="shiftDlg.form.shift_type" style="width: 100%">
            <el-option :label="t('system.shifts.typeDay')" value="day" />
            <el-option :label="t('system.shifts.typeNight')" value="night" />
            <el-option :label="t('system.shifts.typeOvertime')" value="overtime" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="shiftDlg.isEdit" :label="t('system.shifts.status')" prop="status">
          <el-select v-model="shiftDlg.form.status" style="width: 100%">
            <el-option :label="t('system.shifts.statusActive')" value="active" />
            <el-option :label="t('system.shifts.statusInactive')" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('system.shifts.remark')" prop="remark">
          <el-input v-model="shiftDlg.form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shiftDlg.open = false">{{ t('system.shifts.cancel') }}</el-button>
        <el-button type="primary" :loading="shiftDlg.saving" @click="saveShift">{{ t('system.shifts.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 单条排班弹窗 -->
    <el-dialog v-model="schedDlg.open" :title="t('system.shifts.addSchedule')" width="480px" destroy-on-close>
      <el-form ref="schedFormRef" :model="schedDlg.form" :rules="schedRules" label-width="80px">
        <el-form-item :label="t('system.shifts.employee')" prop="user_id">
          <el-select v-model="schedDlg.form.user_id" filterable :placeholder="t('system.shifts.selectEmployee')" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('system.shifts.shiftName')" prop="shift_id">
          <el-select v-model="schedDlg.form.shift_id" :placeholder="t('system.shifts.selectShift')" style="width: 100%">
            <el-option v-for="s in shifts" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('system.shifts.workDate')" prop="work_date">
          <el-date-picker v-model="schedDlg.form.work_date" type="date" value-format="YYYY-MM-DD" :placeholder="t('system.shifts.selectDate')" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('system.shifts.remark')" prop="remark">
          <el-input v-model="schedDlg.form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="schedDlg.open = false">{{ t('system.shifts.cancel') }}</el-button>
        <el-button type="primary" :loading="schedDlg.saving" @click="saveSchedule">{{ t('system.shifts.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 批量排班弹窗 -->
    <el-dialog v-model="batchDlg.open" :title="t('system.shifts.batchSchedule')" width="520px" destroy-on-close>
      <el-form ref="batchFormRef" :model="batchDlg.form" :rules="batchRules" label-width="100px">
        <el-form-item :label="t('system.shifts.employees')" prop="user_ids">
          <el-select v-model="batchDlg.form.user_ids" multiple filterable :placeholder="t('system.shifts.selectEmployees')" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('system.shifts.shiftName')" prop="shift_id">
          <el-select v-model="batchDlg.form.shift_id" :placeholder="t('system.shifts.selectShift')" style="width: 100%">
            <el-option v-for="s in shifts" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('system.shifts.dateRange')" prop="start_date">
          <el-date-picker
            v-model="batchDlg.dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            :start-placeholder="t('system.shifts.startDate')"
            :end-placeholder="t('system.shifts.endDate')"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDlg.open = false">{{ t('system.shifts.cancel') }}</el-button>
        <el-button type="primary" :loading="batchDlg.saving" @click="saveBatchSchedule">{{ t('system.shifts.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { shiftApi, type ShiftOut, type ShiftScheduleOut } from '@/api/shift'
import { systemApi, type UserOut } from '@/api/system'
import { previewNextCode } from '@/utils/code'
import { http } from '@/utils/http'

const { t } = useI18n()

const activeTab = ref('shifts')
const exporting = ref(false)

const shifts = ref<ShiftOut[]>([])
const shiftLoading = ref(false)
const schedules = ref<ShiftScheduleOut[]>([])
const scheduleLoading = ref(false)
const users = ref<UserOut[]>([])
const scheduleDateRange = ref<[string, string] | null>(null)
const scheduleUserFilter = ref<number | null>(null)

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await http.downloadBlob({ url: '/admin/shift/export', method: 'GET' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `shifts_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

function shiftTypeLabel(type: string): string {
  if (type === 'day') return '早班'
  if (type === 'night') return '晚班'
  if (type === 'overtime') return '加班'
  return type
}

async function loadUsers() {
  const res = await systemApi.listUsers({ offset: 0, limit: 200, include_inactive: false })
  users.value = res?.items ?? []
}

async function loadShifts() {
  shiftLoading.value = true
  try {
    const res = await shiftApi.listShifts()
    shifts.value = res?.items ?? []
  } finally {
    shiftLoading.value = false
  }
}

async function loadSchedules() {
  scheduleLoading.value = true
  try {
    const params: Record<string, any> = {}
    if (scheduleUserFilter.value) params.user_id = scheduleUserFilter.value
    if (scheduleDateRange.value) {
      params.start_date = scheduleDateRange.value[0]
      params.end_date = scheduleDateRange.value[1]
    }
    const res = await shiftApi.listSchedules(params)
    schedules.value = res?.items ?? []
  } finally {
    scheduleLoading.value = false
  }
}

// ==================== 班次弹窗 ====================

const shiftDlg = reactive({
  open: false,
  saving: false,
  isEdit: false,
  editId: 0,
  form: { code: '', name: '', start_time: '', end_time: '', rest_minutes: 0, shift_type: 'day', status: 'active', remark: '' },
})
const shiftFormRef = ref<FormInstance>()
const shiftRules: FormRules = {
  name: [{ required: true, message: '请输入班次名称', trigger: 'blur' }],
  start_time: [{ required: true, message: '请选择上班时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择下班时间', trigger: 'change' }],
}

async function openShiftCreate() {
  shiftDlg.isEdit = false
  shiftDlg.editId = 0
  shiftDlg.form = {
    code: await previewNextCode('shift'),
    name: '',
    start_time: '',
    end_time: '',
    rest_minutes: 60,
    shift_type: 'day',
    status: 'active',
    remark: '',
  }
  shiftDlg.open = true
}

function openShiftEdit(row: ShiftOut) {
  shiftDlg.isEdit = true
  shiftDlg.editId = row.id
  shiftDlg.form = {
    code: row.code,
    name: row.name,
    start_time: row.start_time,
    end_time: row.end_time,
    rest_minutes: row.rest_minutes,
    shift_type: row.shift_type,
    status: row.status,
    remark: row.remark ?? '',
  }
  shiftDlg.open = true
}

async function saveShift() {
  const ok = await shiftFormRef.value?.validate().catch(() => false)
  if (!ok) return
  shiftDlg.saving = true
  try {
    const payload: any = {
      name: shiftDlg.form.name,
      start_time: shiftDlg.form.start_time,
      end_time: shiftDlg.form.end_time,
      rest_minutes: shiftDlg.form.rest_minutes,
      shift_type: shiftDlg.form.shift_type,
      remark: shiftDlg.form.remark || undefined,
    }
    if (shiftDlg.isEdit) {
      payload.status = shiftDlg.form.status
      await shiftApi.updateShift(shiftDlg.editId, payload)
    } else {
      payload.code = shiftDlg.form.code || undefined
      await shiftApi.createShift(payload)
    }
    shiftDlg.open = false
    ElMessage.success(shiftDlg.isEdit ? '班次已更新' : '班次已创建')
    await loadShifts()
  } finally {
    shiftDlg.saving = false
  }
}

async function deleteShift(id: number) {
  await shiftApi.deleteShift(id)
  ElMessage.success('班次已删除')
  await loadShifts()
}

// ==================== 单条排班弹窗 ====================

const schedDlg = reactive({
  open: false,
  saving: false,
  form: { user_id: undefined as number | undefined, shift_id: undefined as number | undefined, work_date: '', remark: '' },
})
const schedFormRef = ref<FormInstance>()
const schedRules: FormRules = {
  user_id: [{ required: true, message: '请选择员工', trigger: 'change' }],
  shift_id: [{ required: true, message: '请选择班次', trigger: 'change' }],
  work_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
}

function openScheduleCreate() {
  schedDlg.form = { user_id: undefined, shift_id: undefined, work_date: '', remark: '' }
  schedDlg.open = true
}

async function saveSchedule() {
  const ok = await schedFormRef.value?.validate().catch(() => false)
  if (!ok) return
  schedDlg.saving = true
  try {
    await shiftApi.createSchedule({
      user_id: schedDlg.form.user_id!,
      shift_id: schedDlg.form.shift_id!,
      work_date: schedDlg.form.work_date,
      remark: schedDlg.form.remark || undefined,
    })
    schedDlg.open = false
    ElMessage.success('排班已创建')
    await loadSchedules()
  } finally {
    schedDlg.saving = false
  }
}

// ==================== 批量排班弹窗 ====================

const batchDlg = reactive({
  open: false,
  saving: false,
  dateRange: null as [string, string] | null,
  form: { user_ids: [] as number[], shift_id: undefined as number | undefined, start_date: '', end_date: '' },
})
const batchFormRef = ref<FormInstance>()
const batchRules: FormRules = {
  user_ids: [{ required: true, message: '请选择员工', trigger: 'change' }],
  shift_id: [{ required: true, message: '请选择班次', trigger: 'change' }],
}

watch(
  () => batchDlg.dateRange,
  (val) => {
    if (val) {
      batchDlg.form.start_date = val[0]
      batchDlg.form.end_date = val[1]
    } else {
      batchDlg.form.start_date = ''
      batchDlg.form.end_date = ''
    }
  },
)

function openBatchSchedule() {
  batchDlg.dateRange = null
  batchDlg.form = { user_ids: [], shift_id: undefined, start_date: '', end_date: '' }
  batchDlg.open = true
}

async function saveBatchSchedule() {
  const ok = await batchFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!batchDlg.form.start_date || !batchDlg.form.end_date) {
    ElMessage.warning('请选择日期范围')
    return
  }
  batchDlg.saving = true
  try {
    const res = await shiftApi.batchCreateSchedule({
      user_ids: batchDlg.form.user_ids,
      shift_id: batchDlg.form.shift_id!,
      start_date: batchDlg.form.start_date,
      end_date: batchDlg.form.end_date,
    })
    batchDlg.open = false
    ElMessage.success(`已排班 ${res.count} 条`)
    await loadSchedules()
  } finally {
    batchDlg.saving = false
  }
}

async function deleteSchedule(id: number) {
  await shiftApi.deleteSchedule(id)
  ElMessage.success('排班已删除')
  await loadSchedules()
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadShifts(), loadSchedules()])
})
</script>
