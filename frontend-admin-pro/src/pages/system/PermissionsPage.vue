<template>
  <AdminPage :title="t('system.permissions.title')">
          <template #actions>
      <div class="flex items-center gap-2">
          <el-button type="primary" @click="openCreate">{{ t('system.permissions.create') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="code" :label="t('system.permissions.code')" width="260" />
          <el-table-column prop="name" :label="t('system.permissions.name')" />
          <el-table-column :label="t('system.permissions.operation')" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('system.permissions.edit') }}</el-button>
              <el-popconfirm :title="t('system.permissions.confirmDelete')" @confirm="onDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger">{{ t('system.permissions.delete') }}</el-button>
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
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('system.permissions.edit') }}</el-button>
              <el-popconfirm :title="t('system.permissions.confirmDelete')" @confirm="onDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger">{{ t('system.permissions.delete') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('system.permissions.noData')" />
        </div>
      </div>
    <template #extra>
    <el-dialog v-model="dlg.open" :title="dlg.id ? t('system.permissions.editPermission') : t('system.permissions.createPermission')" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="90px">
        <el-form-item :label="t('system.permissions.code')" prop="code">
          <el-input v-model="dlg.form.code" />
        </el-form-item>
        <el-form-item :label="t('system.permissions.name')" prop="name">
          <el-input v-model="dlg.form.name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('system.permissions.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('system.permissions.save') }}</el-button>
      </template>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi, type PermissionOut } from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const items = ref<PermissionOut[]>([])

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { code: '', name: '' },
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  code: [{ required: true, message: () => t('system.permissions.pleaseInputCode'), trigger: 'blur' }],
  name: [{ required: true, message: () => t('system.permissions.pleaseInputName'), trigger: 'blur' }],
}

async function reload() {
  loading.value = true
  try {
    const res = await systemApi.listPermissions({ offset: 0, limit: 1000 })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dlg.id = null
  dlg.form = { code: '', name: '' }
  dlg.open = true
}

function openEdit(row: PermissionOut) {
  dlg.id = row.id
  dlg.form = { code: row.code, name: row.name }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    if (!dlg.id) await systemApi.createPermission({ ...dlg.form })
    else await systemApi.updatePermission(dlg.id, { ...dlg.form })
    dlg.open = false
    await reload()
  } finally {
    dlg.saving = false
  }
}

async function onDelete(row: PermissionOut) {
  await systemApi.deletePermission(row.id)
  await reload()
}

onMounted(reload)
</script>

