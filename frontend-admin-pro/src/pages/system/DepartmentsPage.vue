<template>
  <AdminPage :title="t('system.departments.title')">
          <template #actions>
      <div class="flex items-center gap-2">
          <el-input v-model="query.keyword" :placeholder="t('system.departments.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
          <el-switch v-model="query.include_inactive" :active-text="t('system.departments.includeInactive')" @change="reload(true)" />
          <el-button type="primary" @click="openCreate">{{ t('system.departments.create') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="code" :label="t('system.departments.code')" width="180" />
          <el-table-column prop="name" :label="t('system.departments.name')" width="220" />
          <el-table-column :label="t('system.departments.parentDepartment')">
            <template #default="{ row }">
              <span>{{ parentName(row.parent_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.departments.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('system.departments.enabled') : t('system.departments.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.departments.operation')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('system.departments.edit') }}</el-button>
              <el-popconfirm :title="t('system.departments.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('system.departments.disable') }}</el-button>
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
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('system.departments.enabled') : t('system.departments.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('system.departments.parent') }}</dt>
              <dd>{{ parentName(row.parent_id) }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('system.departments.edit') }}</el-button>
              <el-popconfirm :title="t('system.departments.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('system.departments.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('system.departments.noData')" />
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
    <el-dialog v-model="dlg.open" :title="dlg.id ? t('system.departments.editDepartment') : t('system.departments.createDepartment')" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="100px">
        <el-form-item :label="t('system.departments.code')" prop="code">
          <el-input v-model="dlg.form.code" :disabled="!!dlg.id" :placeholder="t('system.departments.codePlaceholder')" clearable />
        </el-form-item>
        <el-form-item :label="t('system.departments.name')" prop="name">
          <el-input v-model="dlg.form.name" />
        </el-form-item>
        <el-form-item :label="t('system.departments.parentDepartment')" prop="parent_id">
          <el-select v-model="dlg.form.parent_id" clearable filterable style="width: 100%">
            <el-option v-for="d in allDepartments" :key="d.id" :label="`${d.name}（${d.code}）`" :value="d.id" :disabled="d.id === dlg.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('system.departments.status')" prop="is_active">
          <el-switch v-model="dlg.form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('system.departments.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('system.departments.save') }}</el-button>
      </template>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi, type DepartmentOut } from '@/api/system'
import { codeForSubmit, previewNextCode } from '@/utils/code'

const { t } = useI18n()

const loading = ref(false)
const items = ref<DepartmentOut[]>([])
const allDepartments = ref<DepartmentOut[]>([])
const query = reactive({ keyword: '', offset: 0, limit: 200, include_inactive: false })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { code: '', name: '', parent_id: null as number | null, is_active: true },
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  name: [{ required: true, message: () => t('system.departments.pleaseInputName'), trigger: 'blur' }],
}

function parentName(parentId: number | null) {
  if (!parentId) return '-'
  return allDepartments.value.find((x) => x.id === parentId)?.name || `${parentId}`
}

async function loadAll() {
  const res = await systemApi.listDepartments({ offset: 0, limit: 500, include_inactive: true })
  allDepartments.value = res.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await systemApi.listDepartments({ ...query })
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
  dlg.form = { code: await previewNextCode('department'), name: '', parent_id: null, is_active: true }
  dlg.open = true
}

function openEdit(row: DepartmentOut) {
  dlg.id = row.id
  dlg.form = { code: row.code, name: row.name, parent_id: row.parent_id, is_active: row.is_active }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    const payload = { ...dlg.form, code: dlg.id ? dlg.form.code : codeForSubmit(dlg.form.code) }
    if (!dlg.id) {
      await systemApi.createDepartment(payload)
    } else {
      await systemApi.updateDepartment(dlg.id, { ...dlg.form })
    }
    dlg.open = false
    await loadAll()
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: DepartmentOut) {
  await systemApi.disableDepartment(row.id)
  await loadAll()
  await reload(false)
}

onMounted(async () => {
  await loadAll()
  await reload(true)
})
</script>

