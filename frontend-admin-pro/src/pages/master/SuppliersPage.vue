<template>
  <AdminPage :title="t('master.suppliers.title')">
          <template #actions>
      <div class="flex items-center gap-2">
          <el-input v-model="query.keyword" :placeholder="t('master.suppliers.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
          <el-switch v-model="query.include_inactive" :active-text="t('master.suppliers.includeDisabled')" @change="reload(true)" />
          <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
          <el-button type="primary" @click="openCreate">{{ t('master.suppliers.add') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" :label="t('master.common.id')" width="90" />
          <el-table-column prop="code" :label="t('master.suppliers.code')" width="180" />
          <el-table-column prop="name" :label="t('master.suppliers.name')" width="220" />
          <el-table-column prop="contact_name" :label="t('master.suppliers.contactName')" width="160" />
          <el-table-column prop="phone" :label="t('master.suppliers.phone')" width="160" />
          <el-table-column prop="address" :label="t('master.suppliers.address')" min-width="240" />
          <el-table-column prop="remark" :label="t('master.suppliers.remark')" min-width="220" />
          <el-table-column :label="t('master.suppliers.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('master.suppliers.enabled') : t('master.suppliers.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.suppliers.operation')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('master.suppliers.edit') }}</el-button>
              <el-popconfirm :title="t('master.suppliers.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.suppliers.disable') }}</el-button>
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
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('master.suppliers.enabled') : t('master.suppliers.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('master.suppliers.contactName') }}</dt>
              <dd>{{ row.contact_name || '—' }}</dd>
              <dt>{{ t('master.suppliers.phone') }}</dt>
              <dd>{{ row.phone || '—' }}</dd>
              <dt>{{ t('master.suppliers.address') }}</dt>
              <dd>{{ row.address || '—' }}</dd>
              <dt>{{ t('master.suppliers.remark') }}</dt>
              <dd>{{ row.remark || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('master.suppliers.edit') }}</el-button>
              <el-popconfirm :title="t('master.suppliers.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.suppliers.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('master.suppliers.noData')" />
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
    <el-dialog v-model="dlg.open" :title="dlg.id ? t('master.suppliers.editTitle') : t('master.suppliers.addTitle')" width="680px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="90px">
        <el-form-item :label="t('master.suppliers.code')" prop="code">
          <el-input v-model="dlg.form.code" :disabled="!!dlg.id" :placeholder="t('master.suppliers.autoGenerateHint')" clearable />
        </el-form-item>
        <el-form-item :label="t('master.suppliers.name')" prop="name">
          <el-input v-model="dlg.form.name" />
        </el-form-item>
        <el-form-item :label="t('master.suppliers.contactName')" prop="contact_name">
          <el-input v-model="dlg.form.contact_name" />
        </el-form-item>
        <el-form-item :label="t('master.suppliers.phone')" prop="phone">
          <el-input v-model="dlg.form.phone" />
        </el-form-item>
        <el-form-item :label="t('master.suppliers.address')" prop="address">
          <el-input v-model="dlg.form.address" />
        </el-form-item>
        <el-form-item :label="t('master.suppliers.remark')" prop="remark">
          <el-input v-model="dlg.form.remark" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item :label="t('master.suppliers.enable')" prop="is_active">
          <el-switch v-model="dlg.form.is_active" />
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
import { materialsApi, type SupplierOut } from '@/api/materials'
import { codeForSubmit, previewNextCode } from '@/utils/code'

const { t } = useI18n()

const loading = ref(false)
const exporting = ref(false)
const items = ref<SupplierOut[]>([])
const query = reactive({ keyword: '', offset: 0, limit: 50, include_inactive: false })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { code: '', name: '', contact_name: '', phone: '', address: '', remark: '', is_active: true },
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  name: [{ required: true, message: t('master.suppliers.pleaseInputName'), trigger: 'blur' }],
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await materialsApi.listSuppliers({ ...query })
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
  dlg.form = { code: await previewNextCode('supplier'), name: '', contact_name: '', phone: '', address: '', remark: '', is_active: true }
  dlg.open = true
}

function openEdit(row: SupplierOut) {
  dlg.id = row.id
  dlg.form = {
    code: row.code,
    name: row.name,
    contact_name: row.contact_name || '',
    phone: row.phone || '',
    address: row.address || '',
    remark: row.remark || '',
    is_active: row.is_active,
  }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    const payload = {
      code: dlg.id ? dlg.form.code : codeForSubmit(dlg.form.code),
      name: dlg.form.name,
      contact_name: dlg.form.contact_name || null,
      phone: dlg.form.phone || null,
      address: dlg.form.address || null,
      remark: dlg.form.remark || null,
      is_active: dlg.form.is_active,
    }
    if (!dlg.id) await materialsApi.createSupplier(payload)
    else await materialsApi.updateSupplier(dlg.id, payload)
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: SupplierOut) {
  await materialsApi.disableSupplier(row.id)
  await reload(false)
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await materialsApi.exportSuppliers({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `suppliers_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(() => reload(true))
</script>
