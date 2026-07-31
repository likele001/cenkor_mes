<template>
  <AdminPage :title="t('system.users.title')">
          <template #actions>
      <div class="flex items-center gap-2">
          <el-input v-model="query.keyword" :placeholder="t('system.users.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
          <el-switch v-model="query.include_inactive" :active-text="t('system.users.includeInactive')" @change="reload(true)" />
          <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
          <el-button type="primary" @click="openCreate">{{ t('system.users.create') }}</el-button>
        </div>
    </template>

    <AdminDataTable
      :loading="loading"
      :empty="!loading && !items.length"
      :page-size="query.limit"
      :total="fakeTotal"
      :current-page="page"
      @page-change="onPageChange"
    >
      <template #table>
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="username" :label="t('system.users.username')" width="160" />
          <el-table-column prop="full_name" :label="t('system.users.fullName')" width="160" />
          <el-table-column :label="t('system.users.department')" width="180">
            <template #default="{ row }">
              <span>{{ row.department?.name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.users.roles')">
            <template #default="{ row }">
              <span class="text-[12px] text-gray-700">{{ row.roles.map((x:any) => x.name).join('、') || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.users.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('system.users.enabled') : t('system.users.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.users.operation')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('system.users.edit') }}</el-button>
              <el-popconfirm :title="t('system.users.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('system.users.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #mobile>
        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.full_name || row.username }}</div>
                <div class="text-xs text-el-placeholder">{{ row.username }} · #{{ row.id }}</div>
              </div>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('system.users.enabled') : t('system.users.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('system.users.department') }}</dt>
              <dd>{{ row.department?.name || '—' }}</dd>
              <dt>{{ t('system.users.roles') }}</dt>
              <dd class="text-left">{{ row.roles.map((x: any) => x.name).join('、') || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('system.users.edit') }}</el-button>
              <el-popconfirm :title="t('system.users.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('system.users.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </template>
    </AdminDataTable>

    <template #extra>
    <el-dialog v-model="dlg.open" :title="dlg.id ? t('system.users.editUser') : t('system.users.createUser')" width="620px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="100px">
        <el-form-item :label="t('system.users.username')" prop="username">
          <el-input v-model="dlg.form.username" :disabled="Boolean(dlg.id)" />
        </el-form-item>
        <el-form-item :label="t('system.users.fullName')" prop="full_name">
          <el-input v-model="dlg.form.full_name" />
        </el-form-item>
        <el-form-item :label="t('system.users.password')" prop="password">
          <el-input v-model="dlg.form.password" type="password" show-password autocomplete="off" />
        </el-form-item>
        <el-form-item :label="t('system.users.department')" prop="department_id">
          <el-select v-model="dlg.form.department_id" clearable filterable style="width: 100%">
            <el-option v-for="d in departments" :key="d.id" :label="`${d.name}（${d.code}）`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('system.users.roles')" prop="role_ids">
          <el-select v-model="dlg.form.role_ids" multiple filterable style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="`${r.name}（${r.code}）`" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('system.users.isActive')" prop="is_active">
          <el-switch v-model="dlg.form.is_active" />
        </el-form-item>
        <el-form-item :label="t('system.users.isSuperuser')" prop="is_superuser">
          <el-switch v-model="dlg.form.is_superuser" />
        </el-form-item>
        <el-form-item label="计薪方式" prop="salary_type">
          <el-select v-model="dlg.form.salary_type" style="width: 100%">
            <el-option label="计件" value="piece" />
            <el-option label="计时" value="hourly" />
            <el-option label="混合" value="mixed" />
          </el-select>
        </el-form-item>
        <el-form-item label="时薪（元）" prop="hourly_rate" v-if="dlg.form.salary_type !== 'piece'">
          <el-input-number v-model="dlg.form.hourly_rate" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('system.users.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('system.users.save') }}</el-button>
      </template>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi, type DepartmentOut, type RoleOut, type UserOut } from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const exporting = ref(false)
const items = ref<UserOut[]>([])
const roles = ref<RoleOut[]>([])
const departments = ref<DepartmentOut[]>([])
const query = reactive({ keyword: '', offset: 0, limit: 50, include_inactive: false })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: {
    username: '',
    full_name: '',
    password: '',
    department_id: null as number | null,
    role_ids: [] as number[],
    is_active: true,
    is_superuser: false,
    salary_type: 'piece',
    hourly_rate: null as number | null,
  },
})

const formRef = ref<FormInstance>()

const rules: FormRules = {
  username: [{ required: true, message: () => t('system.users.pleaseInputUsername'), trigger: 'blur' }],
  role_ids: [{ type: 'array', required: true, message: () => t('system.users.pleaseSelectRole'), trigger: 'change' }],
  password: [
    {
      validator: (_: any, v: string, cb: any) => {
        if (!dlg.id && !v) cb(new Error(t('system.users.pleaseInputPassword')))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

async function loadOptions() {
  const [r, d] = await Promise.all([
    systemApi.listRoles({ offset: 0, limit: 500 }),
    systemApi.listDepartments({ offset: 0, limit: 500, include_inactive: true }),
  ])
  roles.value = r.items
  departments.value = d.items
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await systemApi.exportUsers()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `users_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await systemApi.listUsers({ ...query })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

function resetForm() {
  dlg.form = {
    username: '',
    full_name: '',
    password: '',
    department_id: null,
    role_ids: [],
    is_active: true,
    is_superuser: false,
    salary_type: 'piece',
    hourly_rate: null,
  }
}

function openCreate() {
  dlg.id = null
  resetForm()
  dlg.open = true
}

function openEdit(row: UserOut) {
  dlg.id = row.id
  dlg.form = {
    username: row.username,
    full_name: row.full_name || '',
    password: '',
    department_id: row.department_id,
    role_ids: row.roles.map((x) => x.id),
    is_active: row.is_active,
    is_superuser: row.is_superuser,
    salary_type: row.salary_type || 'piece',
    hourly_rate: row.hourly_rate ?? null,
  }
  dlg.open = true
}

async function onDisable(row: UserOut) {
  await systemApi.disableUser(row.id)
  await reload(false)
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    if (!dlg.id) {
      await systemApi.createUser({
        username: dlg.form.username,
        full_name: dlg.form.full_name || null,
        password: dlg.form.password,
        department_id: dlg.form.department_id,
        role_ids: dlg.form.role_ids,
        is_active: dlg.form.is_active,
        is_superuser: dlg.form.is_superuser,
        salary_type: dlg.form.salary_type,
        hourly_rate: dlg.form.hourly_rate,
      })
    } else {
      await systemApi.updateUser(dlg.id, {
        full_name: dlg.form.full_name || null,
        password: dlg.form.password ? dlg.form.password : null,
        department_id: dlg.form.department_id,
        role_ids: dlg.form.role_ids,
        is_active: dlg.form.is_active,
        is_superuser: dlg.form.is_superuser,
        salary_type: dlg.form.salary_type,
        hourly_rate: dlg.form.hourly_rate,
      })
    }
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

onMounted(async () => {
  await loadOptions()
  await reload(true)
})
</script>

