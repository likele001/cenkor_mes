<template>
  <AdminPage :title="t('master.materials.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-input v-model="query.keyword" :placeholder="t('master.materials.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
          <el-select v-model="query.supplier_id" clearable filterable :placeholder="t('master.materials.supplier')" style="width: 220px" @change="reload(true)">
            <el-option v-for="s in suppliers" :key="s.id" :label="partyOptionLabel(s)" :value="s.id" />
          </el-select>
          <el-switch v-model="query.include_inactive" :active-text="t('master.materials.includeDisabled')" @change="reload(true)" />
          <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
          <el-button type="primary" @click="openCreate">{{ t('master.materials.add') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" :label="t('master.common.id')" width="90" />
          <el-table-column prop="code" :label="t('master.materials.code')" width="180" />
          <el-table-column prop="name" :label="t('master.materials.name')" width="220" />
          <el-table-column :label="t('master.materials.supplier')" width="220">
            <template #default="{ row }">
              <span>{{ supplierLabel(row.supplier_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="unit" :label="t('master.materials.unit')" width="120" />
          <el-table-column prop="spec" :label="t('master.materials.spec')" min-width="220" />
          <el-table-column prop="remark" :label="t('master.materials.remark')" min-width="220" />
          <el-table-column :label="t('master.materials.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('master.materials.enabled') : t('master.materials.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.materials.operation')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('master.materials.edit') }}</el-button>
              <el-popconfirm :title="t('master.materials.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.materials.disable') }}</el-button>
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
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('master.materials.enabled') : t('master.materials.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('master.materials.supplier') }}</dt>
              <dd>{{ supplierLabel(row.supplier_id) }}</dd>
              <dt>{{ t('master.materials.unit') }}</dt>
              <dd>{{ row.unit || '—' }}</dd>
              <dt>{{ t('master.materials.spec') }}</dt>
              <dd>{{ row.spec || '—' }}</dd>
              <dt>{{ t('master.materials.remark') }}</dt>
              <dd>{{ row.remark || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('master.materials.edit') }}</el-button>
              <el-popconfirm :title="t('master.materials.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.materials.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('master.materials.noData')" />
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
    <el-dialog v-model="dlg.open" :title="dlg.id ? t('master.materials.editTitle') : t('master.materials.addTitle')" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="90px">
        <el-form-item :label="t('master.materials.code')" prop="code">
          <el-input v-model="dlg.form.code" :disabled="!!dlg.id" :placeholder="t('master.materials.autoGenerateHint')" clearable />
        </el-form-item>
        <el-form-item :label="t('master.materials.name')" prop="name">
          <el-input v-model="dlg.form.name" />
        </el-form-item>
        <el-form-item :label="t('master.materials.supplier')" prop="supplier_id">
          <el-select v-model="dlg.form.supplier_id" clearable filterable :placeholder="t('master.materials.pleaseSelectSupplier')" style="width: 100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="partyOptionLabel(s)" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('master.materials.unit')" prop="unit">
          <el-input v-model="dlg.form.unit" />
        </el-form-item>
        <el-form-item :label="t('master.materials.spec')" prop="spec">
          <el-input v-model="dlg.form.spec" />
        </el-form-item>
        <el-form-item :label="t('master.materials.remark')" prop="remark">
          <el-input v-model="dlg.form.remark" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item :label="t('master.materials.enable')" prop="is_active">
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
import { materialsApi, type MaterialOut, type SupplierOut } from '@/api/materials'
import { codeForSubmit, previewNextCode } from '@/utils/code'
import { partyOptionLabel } from '@/utils/display'

const { t } = useI18n()

const loading = ref(false)
const exporting = ref(false)
const items = ref<MaterialOut[]>([])
const suppliers = ref<SupplierOut[]>([])

const query = reactive({
  keyword: '',
  supplier_id: null as number | null,
  offset: 0,
  limit: 50,
  include_inactive: false,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const supMap = computed(() => new Map(suppliers.value.map((s) => [s.id, s])))
function supplierLabel(id: number | null) {
  if (!id) return '-'
  const s = supMap.value.get(id)
  if (!s) return String(id)
  return partyOptionLabel(s)
}

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { code: '', name: '', supplier_id: null as number | null, unit: '', spec: '', remark: '', is_active: true },
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  name: [{ required: true, message: t('master.materials.pleaseInputName'), trigger: 'blur' }],
}

async function loadSuppliers() {
  const res = await materialsApi.listSuppliers({ keyword: '', offset: 0, limit: 200, include_inactive: true })
  suppliers.value = res.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await materialsApi.listMaterials({
      keyword: query.keyword || undefined,
      supplier_id: query.supplier_id || undefined,
      offset: query.offset,
      limit: query.limit,
      include_inactive: query.include_inactive,
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
  dlg.form = { code: await previewNextCode('material'), name: '', supplier_id: null, unit: '', spec: '', remark: '', is_active: true }
  dlg.open = true
}

function openEdit(row: MaterialOut) {
  dlg.id = row.id
  dlg.form = {
    code: row.code,
    name: row.name,
    supplier_id: row.supplier_id,
    unit: row.unit || '',
    spec: row.spec || '',
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
      supplier_id: dlg.form.supplier_id || null,
      unit: dlg.form.unit || null,
      spec: dlg.form.spec || null,
      remark: dlg.form.remark || null,
      is_active: dlg.form.is_active,
    }
    if (!dlg.id) await materialsApi.createMaterial(payload)
    else await materialsApi.updateMaterial(dlg.id, payload)
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: MaterialOut) {
  await materialsApi.disableMaterial(row.id)
  await reload(false)
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await materialsApi.exportMaterials({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `materials_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(async () => {
  await loadSuppliers()
  await reload(true)
})
</script>
