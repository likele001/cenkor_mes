<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { http } from '@/utils/http'
import { codeForSubmit, previewNextCode } from '@/utils/code'

const { t } = useI18n()

interface Warehouse {
  id: number
  code: string
  name: string
  address: string
}

const loading = ref(false)
const exporting = ref(false)
const items = ref<Warehouse[]>([])
const keyword = ref('')

const dlg = reactive({
  open: false,
  saving: false,
  id: 0 as number | 0,
  form: { code: '', name: '', address: '' },
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  name: [{ required: true, message: () => t('warehouse.warehouses.nameRequired'), trigger: 'blur' }],
}

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter((x) => {
    const a = (x.code || '').toLowerCase()
    const b = (x.name || '').toLowerCase()
    return a.includes(kw) || b.includes(kw)
  })
})

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await http.downloadBlob({ url: '/admin/warehouse/warehouses/export', method: 'GET' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `warehouses_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

async function loadList() {
  loading.value = true
  try {
    const res = await http.request<{ items: Warehouse[] }>({
      url: '/admin/warehouse/warehouses',
      method: 'GET',
    })
    items.value = res.items ?? []
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  dlg.id = 0
  dlg.form = { code: await previewNextCode('warehouse'), name: '', address: '' }
  dlg.open = true
}

function openEdit(row: Warehouse) {
  dlg.id = row.id
  dlg.form = { code: row.code, name: row.name, address: row.address }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    if (dlg.id) {
      await http.request({
        url: `/admin/warehouse/warehouses/${dlg.id}`,
        method: 'PUT',
        params: { ...dlg.form },
      })
    } else {
      await http.request({
        url: '/admin/warehouse/warehouses',
        method: 'POST',
        data: { ...dlg.form, code: codeForSubmit(dlg.form.code) },
      })
    }
    dlg.open = false
    ElMessage.success(dlg.id ? t('warehouse.warehouses.editSuccess') : t('warehouse.warehouses.createSuccess'))
    await loadList()
  } finally {
    dlg.saving = false
  }
}

onMounted(() => loadList())
</script>


<template>
  <AdminPage :title="t('warehouse.warehouses.title')">
    <el-card shadow="never">
      <template #header><span class="font-medium">{{ t('warehouse.warehouses.title') }}</span></template>

      <div class="flex items-center gap-2 flex-wrap">
        <el-input
          v-model="keyword"
          :placeholder="t('warehouse.warehouses.searchPlaceholder')"
          style="width: 220px"
          clearable
          @keyup.enter="loadList"
        />
        <el-button type="primary" @click="loadList">{{ t('warehouse.warehouses.search') }}</el-button>
        <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
        <el-button type="primary" @click="openCreate">{{ t('warehouse.warehouses.createNew') }}</el-button>
      </div>

      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="filtered" stripe style="width: 100%">
          <el-table-column prop="code" :label="t('warehouse.warehouses.code')" width="180" />
          <el-table-column prop="name" :label="t('warehouse.warehouses.name')" width="200" />
          <el-table-column prop="address" :label="t('warehouse.warehouses.address')" min-width="260" />
          <el-table-column :label="t('warehouse.warehouses.actions')" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('warehouse.warehouses.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in filtered" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.name }}</div>
                <div class="text-xs text-el-placeholder">{{ row.code }}</div>
              </div>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('warehouse.warehouses.address') }}</dt>
              <dd class="text-left">{{ row.address || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('warehouse.warehouses.edit') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !filtered.length" :description="t('warehouse.warehouses.empty')" />
        </div>
      </div>
    </el-card>

    <el-dialog
      v-model="dlg.open"
      :title="dlg.id ? t('warehouse.warehouses.editTitle') : t('warehouse.warehouses.createTitle')"
      width="500px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="80px">
        <el-form-item :label="t('warehouse.warehouses.code')" prop="code">
          <el-input v-model="dlg.form.code" :disabled="!!dlg.id" :placeholder="t('warehouse.warehouses.codePlaceholder')" clearable />
        </el-form-item>
        <el-form-item :label="t('warehouse.warehouses.name')" prop="name">
          <el-input v-model="dlg.form.name" :placeholder="t('warehouse.warehouses.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('warehouse.warehouses.address')" prop="address">
          <el-input v-model="dlg.form.address" :placeholder="t('warehouse.warehouses.addressPlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('warehouse.warehouses.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('warehouse.warehouses.save') }}</el-button>
      </template>
    </el-dialog>  </AdminPage>
</template>
