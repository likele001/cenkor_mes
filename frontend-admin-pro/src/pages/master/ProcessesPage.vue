<template>
  <AdminPage :title="t('master.processes.title')">
          <template #actions>
      <div class="flex items-center gap-2">
          <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px;margin-right:10px" @change="reload(true)">
          <el-option label="全部行业" value="" />
          <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
        </el-select>
        <el-input v-model="query.keyword" :placeholder="t('master.processes.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
          <el-switch v-model="query.include_inactive" :active-text="t('master.processes.includeDisabled')" @change="reload(true)" />
          <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
          <el-button type="primary" @click="openCreate">{{ t('master.processes.add') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" :label="t('master.common.id')" width="90" />
          <el-table-column prop="code" :label="t('master.processes.code')" width="180" />
          <el-table-column prop="name" :label="t('master.processes.name')" width="220" />
          <el-table-column prop="workshop" :label="t('master.processes.workshop')" width="180" />
          <el-table-column prop="std_minutes" :label="t('master.processes.stdMinutes')" width="140" />
          <el-table-column :label="t('master.processes.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('master.processes.enabled') : t('master.processes.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.processes.operation')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('master.processes.edit') }}</el-button>
              <el-popconfirm :title="t('master.processes.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.processes.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.name }}</div>
                <div class="text-xs text-el-placeholder">{{ row.code }} · #{{ row.id }}</div>
              </div>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('master.processes.enabled') : t('master.processes.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('master.processes.workshop') }}</dt>
              <dd>{{ row.workshop || '—' }}</dd>
              <dt>{{ t('master.processes.stdMinutes') }}</dt>
              <dd>{{ row.std_minutes ?? '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('master.processes.edit') }}</el-button>
              <el-popconfirm :title="t('master.processes.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.processes.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('master.processes.noData')" />
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
    <el-dialog v-model="dlg.open" :title="dlg.id ? t('master.processes.editTitle') : t('master.processes.addTitle')" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="100px">
        <el-form-item :label="t('master.processes.code')" prop="code">
          <el-input v-model="dlg.form.code" :disabled="!!dlg.id" :placeholder="t('master.processes.autoGenerateHint')" clearable />
        </el-form-item>
        <el-form-item :label="t('master.processes.name')" prop="name">
          <el-input v-model="dlg.form.name" />
        </el-form-item>
        <el-form-item :label="t('master.processes.workshop')" prop="workshop">
          <el-input v-model="dlg.form.workshop" />
        </el-form-item>
        <el-form-item :label="t('master.processes.stdMinutes')" prop="std_minutes">
          <el-input-number v-model="dlg.form.std_minutes" :min="0" :controls="false" />
        </el-form-item>
        <el-form-item :label="t('master.processes.enable')" prop="is_active">
          <el-switch v-model="dlg.form.is_active" />
        </el-form-item>
        <el-form-item v-if="dlg.id" :label="t('master.processes.requiredSkills')">
          <el-select v-model="dlg.skill_ids" multiple filterable :placeholder="t('master.processes.skillFilterHint')" style="width: 100%">
            <el-option v-for="s in allSkills" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('master.common.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('master.common.save') }}</el-button>
      </template>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { masterApi, type ProcessOut } from '@/api/master'
import { systemApi } from '@/api/system'
import { codeForSubmit, previewNextCode } from '@/utils/code'

const { t } = useI18n()

const loading = ref(false)
const exporting = ref(false)
const items = ref<ProcessOut[]>([])
const allSkills = ref<Array<{ id: number; name: string }>>([])
const query = reactive({ keyword: '', offset: 0, limit: 50, include_inactive: false })
const industryFilter = ref('')
const activeIndustries = ref<{code:string,name:string}[]>([])

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { code: '', name: '', workshop: '', std_minutes: null as number | null, is_active: true },
  skill_ids: [] as number[],
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  name: [{ required: true, message: t('master.processes.pleaseInputName'), trigger: 'blur' }],
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await masterApi.listProcesses({
          ...query,
          industry_code: industryFilter.value || undefined
        })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

async function openCreate() {
  dlg.id = null
  dlg.form = { code: await previewNextCode('process'), name: '', workshop: '', std_minutes: null, is_active: true }
  dlg.open = true
}

function openEdit(row: ProcessOut) {
  dlg.id = row.id
  dlg.form = { code: row.code, name: row.name, workshop: row.workshop || '', std_minutes: row.std_minutes, is_active: row.is_active }
  dlg.skill_ids = []
  dlg.open = true
  masterApi.getProcessSkills(row.id).then((res) => {
    dlg.skill_ids = (res.items || []).map((x) => x.id)
  }).catch(() => {})
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    const payload = {
      code: dlg.id ? dlg.form.code : codeForSubmit(dlg.form.code),
      name: dlg.form.name,
      workshop: dlg.form.workshop || null,
      std_minutes: dlg.form.std_minutes,
      is_active: dlg.form.is_active,
    }
    if (!dlg.id) await masterApi.createProcess(payload)
    else {
      await masterApi.updateProcess(dlg.id, payload)
      await masterApi.setProcessSkills(dlg.id, dlg.skill_ids)
    }
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: ProcessOut) {
  await masterApi.disableProcess(row.id)
  await reload(false)
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await masterApi.exportProcesses({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `processes_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(async () => {
  try {
    const sk = await systemApi.listSkills({ offset: 0, limit: 200 })
    allSkills.value = (sk.items || []).map((x: { id: number; name: string }) => ({ id: x.id, name: x.name }))
  } catch {
    allSkills.value = []
  }
  await reload(true)
})
</script>
