<template>
  <AdminPage :title="t('system.roles.title')">
    <template #actions>
      <div class="flex items-center gap-2">
          <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
          <el-button type="primary" @click="openCreate">{{ t('system.roles.create') }}</el-button>
        </div>
    </template>

    <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="code" :label="t('system.roles.code')" width="180" />
          <el-table-column prop="name" :label="t('system.roles.name')" width="220" />
          <el-table-column :label="t('system.roles.permissions')">
            <template #default="{ row }">
              <span class="text-[12px] text-gray-700">{{ (row.permission_codes || []).join(', ') || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.roles.operation')" width="260" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('system.roles.edit') }}</el-button>
              <el-button size="small" @click="openPerms(row)">{{ t('system.roles.permission') }}</el-button>
              <el-popconfirm :title="t('system.roles.confirmDelete')" @confirm="onDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger">{{ t('system.roles.delete') }}</el-button>
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
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('system.roles.permission') }}</dt>
              <dd class="text-left text-xs">{{ (row.permission_codes || []).join('、') || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('system.roles.edit') }}</el-button>
              <el-button size="small" @click="openPerms(row)">{{ t('system.roles.permission') }}</el-button>
              <el-popconfirm :title="t('system.roles.confirmDelete')" @confirm="onDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger">{{ t('system.roles.delete') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('system.roles.noData')" />
        </div>
      </div>

    <template #extra>
      <el-dialog v-model="dlg.open" :title="dlg.id ? t('system.roles.editRole') : t('system.roles.createRole')" width="520px" destroy-on-close>
            <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="90px">
              <el-form-item :label="t('system.roles.code')" prop="code">
                <el-input v-model="dlg.form.code" />
              </el-form-item>
              <el-form-item :label="t('system.roles.name')" prop="name">
                <el-input v-model="dlg.form.name" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="dlg.open = false">{{ t('system.roles.cancel') }}</el-button>
              <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('system.roles.save') }}</el-button>
            </template>
          </el-dialog>

      <el-dialog v-model="perm.open" :title="t('system.roles.configPermissions')" width="720px" destroy-on-close>
            <div class="text-[12px] text-gray-600 mb-2">{{ perm.roleLabel }}</div>
            <el-select v-model="perm.permission_codes" multiple filterable style="width: 100%">
              <el-option v-for="p in permissions" :key="p.code" :label="`${p.name}（${p.code}）`" :value="p.code" />
            </el-select>
            <template #footer>
              <el-button @click="perm.open = false">{{ t('system.roles.cancel') }}</el-button>
              <el-button type="primary" :loading="perm.saving" @click="onSavePerms">{{ t('system.roles.save') }}</el-button>
            </template>
          </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi, type PermissionOut, type RoleOut } from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const exporting = ref(false)
const items = ref<RoleOut[]>([])
const permissions = ref<PermissionOut[]>([])

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { code: '', name: '' },
})

const perm = reactive({
  open: false,
  saving: false,
  roleId: null as number | null,
  roleLabel: '',
  permission_codes: [] as string[],
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  code: [{ required: true, message: () => t('system.roles.pleaseInputCode'), trigger: 'blur' }],
  name: [{ required: true, message: () => t('system.roles.pleaseInputName'), trigger: 'blur' }],
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await systemApi.exportRoles()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `roles_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

async function reload() {
  loading.value = true
  try {
    const res = await systemApi.listRoles({ offset: 0, limit: 500 })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

async function loadPermissions() {
  const res = await systemApi.listPermissions({ offset: 0, limit: 1000 })
  permissions.value = res.items
}

function openCreate() {
  dlg.id = null
  dlg.form = { code: '', name: '' }
  dlg.open = true
}

function openEdit(row: RoleOut) {
  dlg.id = row.id
  dlg.form = { code: row.code, name: row.name }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    if (!dlg.id) await systemApi.createRole({ ...dlg.form })
    else await systemApi.updateRole(dlg.id, { ...dlg.form })
    dlg.open = false
    await reload()
  } finally {
    dlg.saving = false
  }
}

function openPerms(row: RoleOut) {
  perm.roleId = row.id
  perm.roleLabel = `${row.name}（${row.code}）`
  perm.permission_codes = [...(row.permission_codes || [])]
  perm.open = true
}

async function onSavePerms() {
  if (!perm.roleId) return
  perm.saving = true
  try {
    await systemApi.setRolePermissions(perm.roleId, { permission_codes: perm.permission_codes })
    perm.open = false
    await reload()
  } finally {
    perm.saving = false
  }
}

async function onDelete(row: RoleOut) {
  await systemApi.deleteRole(row.id)
  await reload()
}

onMounted(async () => {
  await Promise.all([reload(), loadPermissions()])
})
</script>

